"""命令执行命令"""

import asyncio
from pathlib import Path
import click
from typing import List, Optional
from pypssh.config.storage import ConfigStorage
from pypssh.core.models import ConnectionConfig, ExecutionStatus, Host
from pypssh.core.executor import SSHExecutor
from pypssh.selector.ip_selector import IPSelector
from pypssh.selector.label_selector import LabelSelector, select_servers
from pypssh.ui.progress import ProgressDisplay, create_progress_callback
from pypssh.ui.formatter import OutputFormatter


@click.command()
@click.argument("command")
@click.option("--namespace", "-n", default="default", help="命名空间")
@click.option("--hosts", "-h", help="主机选择表达式 (IP表达式)")
@click.option("--selector", "-s", help="标签选择表达式")
@click.option("--group", "-g", help="服务器组名称")
@click.option("--server", multiple=True, help="指定服务器名称")
@click.option("--max-concurrent", "-c", default=50, help="最大并发数")
@click.option("--timeout", "-t", default=30.0, help="命令超时时间")
@click.option("--connect-timeout", default=10.0, help="连接超时时间")
@click.option("--needpty", is_flag=True, help="分配伪终端")
@click.option("--sudo", is_flag=True, help="使用sudo执行")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["default", "json", "yaml", "template", "none"]),
    default="default",
    help="输出格式",
)
@click.option("--output-file", "-f", help="输出文件路径")
@click.option("--template", "-T", help="自定义输出模板")
@click.option("--quiet", "-q", is_flag=True, help="静默模式，不显示中间输出")
@click.option("--stop-on-error", is_flag=True, help="遇到错误时停止")
@click.option("--show-progress", is_flag=True, default=True, help="显示进度")
def execute_command(
    command,
    namespace,
    hosts,
    selector,
    group,
    server,
    max_concurrent,
    timeout,
    connect_timeout,
    needpty,
    sudo,
    output,
    output_file,
    template,
    quiet,
    stop_on_error,
    show_progress,
):
    """在选定的主机上执行命令"""

    # 构建最终命令
    final_command = command
    if sudo:
        final_command = f"sudo {command}"

    # 获取目标服务器配置
    configs = _get_target_configs(
        namespace, hosts, selector, group, server, timeout, connect_timeout
    )

    if not configs:
        click.echo(f"No hosts selected for execution in namespace '{namespace}'")
        return

    # 如果不是默认输出格式，自动启用静默模式
    if output != "default" and not quiet:
        quiet = True

    if not quiet:
        click.echo(
            f"Executing command on {len(configs)} hosts in namespace '{namespace}'..."
        )

    # 执行命令
    asyncio.run(
        _execute_async(
            configs,
            final_command,
            max_concurrent,
            needpty,
            output,
            template,
            output_file,
            quiet,
            stop_on_error,
            show_progress,
        )
    )


async def _execute_async(
    configs: List[ConnectionConfig],
    command: str,
    max_concurrent: int,
    needpty: bool,
    output_format: str,
    template: str,
    output_file: Optional[str],
    quiet: bool,
    stop_on_error: bool,
    show_progress: bool,
):
    """异步执行命令"""

    # 创建进度显示
    display = None
    progress_callback = None

    if not quiet and show_progress and output_format != "none":
        display = ProgressDisplay(show_details=True)
        progress_callback = create_progress_callback(display)
        display.start_execution(len(configs), command)

    # 创建执行器
    executor = SSHExecutor(
        max_concurrent=max_concurrent, progress_callback=progress_callback
    )

    # 执行命令
    if needpty:
        # 需要PTY的情况下，使用PTY执行
        results = await _execute_with_pty(
            executor,
            configs,
            command,
            stop_on_error,
        )
    else:
        results = await executor.execute_parallel(configs, command, stop_on_error)

    # 完成进度显示
    if display:
        display.finish_execution()

    # 格式化输出
    formatter = OutputFormatter(output_format, template)

    if output_format == "none":
        return
    elif output_format in ["json", "yaml", "template"]:
        output_content = formatter.format_execution_results(results)
        if output_file:
            # 输出到文件
            file_path = Path(output_file)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                f.write(output_content)
            if not quiet:
                click.echo(f"Results saved to {output_file}")
        else:
            # 输出到标准输出
            click.echo(output_content)
    else:
        if not quiet:
            formatter.print_results(results, "Command Execution Results")


async def _execute_with_pty(
    executor: SSHExecutor,
    configs: List[ConnectionConfig],
    command: str,
    stop_on_error: bool,
):
    """使用PTY执行命令"""
    from ..core.models import ExecutionResult

    # 创建信号量来控制并发数
    semaphore = asyncio.Semaphore(executor.max_concurrent)
    tasks = []

    # 为每个连接创建任务
    for config in configs:
        task = asyncio.create_task(
            _execute_single_with_pty(
                semaphore,
                config,
                command,
                stop_on_error,
            )
        )
        tasks.append(task)

    # 等待所有任务完成或被取消
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        # 取消所有任务
        for task in tasks:
            if not task.done():
                task.cancel()

        # 等待所有任务完成取消
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    # 处理结果
    execution_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # 处理异常
            execution_results.append(
                ExecutionResult(
                    host=configs[i].host,
                    port=configs[i].port,
                    status=ExecutionStatus.ERROR,
                    stdout="",
                    stderr=str(result),
                    exit_code=1,
                    execution_time=0.0,
                )
            )
        else:
            execution_results.append(result)

    return execution_results


async def _execute_single_with_pty(
    semaphore: asyncio.Semaphore,
    config: ConnectionConfig,
    command: str,
    stop_on_error: bool,
):
    """在单个连接上使用PTY执行命令"""
    import asyncssh
    import signal
    from ..core.models import ExecutionResult

    async with semaphore:
        start_time = asyncio.get_event_loop().time()
        stdout_data = []
        stderr_data = []
        exit_code = None
        status = ExecutionStatus.SUCCESS
        error_msg = ""
        process = None

        try:
            # 准备连接参数
            connect_kwargs = {
                "host": config.host,
                "port": config.port,
                "username": config.username,
                "connect_timeout": config.connect_timeout,
            }

            # 添加密码认证
            if config.password:
                connect_kwargs["password"] = config.password

            # 添加私钥认证
            if config.private_key:
                connect_kwargs["client_keys"] = [config.private_key]
            elif config.private_key_path:
                # 如果是私钥文件路径，读取文件内容
                try:
                    with open(config.private_key_path, "r") as f:
                        private_key = f.read()
                    connect_kwargs["client_keys"] = [private_key]
                except Exception as e:
                    raise RuntimeError(f"Failed to read private key file: {e}")

            # 创建SSH连接
            async with asyncssh.connect(**connect_kwargs) as conn:
                # 创建PTY会话
                process = await conn.create_process(
                    command,
                    term_type="xterm-256color",
                    encoding=None,
                )

                # 创建任务来读取stdout和stderr
                stdout_task = asyncio.create_task(
                    _read_stream(process.stdout, stdout_data, config.name)
                )
                stderr_task = asyncio.create_task(
                    _read_stream(process.stderr, stderr_data, config.name)
                )

                # 创建一个任务来等待进程完成
                wait_task = asyncio.create_task(process.wait())

                # 等待进程完成或任务被取消
                done, pending = await asyncio.wait(
                    [wait_task, stdout_task, stderr_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # 如果进程已经完成，获取退出码
                if wait_task in done:
                    exit_code = wait_task.result()

                    # 等待所有输出读取完成
                    await asyncio.gather(*pending, return_exceptions=True)

                    # 检查退出码
                    if exit_code != 0:
                        status = ExecutionStatus.FAILED
                        error_msg = f"Command exited with code {exit_code}"
                else:
                    # 进程仍在运行，等待直到被取消
                    try:
                        # 无限等待，直到任务被取消
                        await asyncio.wait_for(asyncio.gather(*pending), timeout=None)
                    except asyncio.CancelledError:
                        # 任务被取消，尝试终止进程
                        try:
                            process.send_signal(signal.SIGTERM)
                            # 等待进程终止
                            try:
                                exit_code = await asyncio.wait_for(
                                    process.wait(), timeout=5
                                )
                            except asyncio.TimeoutError:
                                # 如果SIGTERM无效，尝试SIGKILL
                                process.send_signal(signal.SIGKILL)
                                exit_code = await asyncio.wait_for(
                                    process.wait(), timeout=2
                                )
                        except:
                            pass
                        status = ExecutionStatus.CANCELLED
                        error_msg = "Execution was cancelled"
                        raise

        except asyncio.CancelledError as ex:
            status = ExecutionStatus.CANCELLED
            error_msg = "Execution was cancelled"
            # 尝试终止进程
            if process:
                try:
                    process.send_signal(signal.SIGTERM)
                except:
                    pass
            raise
        except Exception as e:
            status = ExecutionStatus.ERROR
            error_msg = str(e)

        # 计算执行时间
        execution_time = asyncio.get_event_loop().time() - start_time

        # 创建结果对象
        result = ExecutionResult(
            host=config.host,
            port=config.port,
            status=status,
            stdout=b"".join(stdout_data).decode("utf-8", errors="replace"),
            stderr=b"".join(stderr_data).decode("utf-8", errors="replace"),
            exit_code=exit_code or 0,
            execution_time=execution_time,
        )

        # 如果需要停止错误且执行失败，抛出异常
        if stop_on_error and status != ExecutionStatus.SUCCESS:
            raise RuntimeError(
                f"Command failed on {config.host}:{config.port}: {error_msg}"
            )

        return result


async def _read_stream(
    stream: Optional[asyncio.StreamReader],
    buffer: List[bytes],
    name: str,
):
    """读取流数据"""
    if stream is None:
        return

    prefix = f"[{name}] "

    try:
        while True:
            # 读取数据，设置超时以避免无限等待
            try:
                data = await asyncio.wait_for(stream.read(4096), timeout=1.0)
            except asyncio.TimeoutError:
                # 超时后继续尝试，不要退出
                continue

            if not data:
                break

            buffer.append(data)

            text = data.decode("utf-8", errors="replace")
            click.echo(f"{prefix}{text.rstrip()}")

    except asyncio.CancelledError:
        # 任务被取消，这是正常的退出方式
        raise
    except Exception as e:
        # 读取错误时记录但继续
        click.echo(f"Error reading stream: {e}", err=True)


def _get_target_configs(
    namespace: str,
    hosts: Optional[str],
    selector: Optional[str],
    group: Optional[str],
    server_names: tuple,
    timeout: float,
    connect_timeout: float,
) -> List[ConnectionConfig]:
    """获取目标服务器配置"""

    storage = ConfigStorage()
    configs = []

    # 通过服务器名称选择
    if server_names:
        for name in server_names:
            server_config = storage.get_server(name, namespace)
            if server_config:
                config = _server_config_to_connection_config(
                    server_config, timeout, connect_timeout
                )
                configs.append(config)

    # 通过服务器组选择
    elif group:
        server_group = storage.get_server_group(group, namespace)
        if server_group:
            # 获取命名空间中的所有服务器
            all_servers = storage.list_servers(namespace)

            # 转换为Server对象
            servers = [
                Host(
                    name=s.name,
                    host=s.host,
                    port=s.port,
                    username=s.username,
                    labels=s.labels,
                )
                for s in all_servers
            ]

            # 应用组的选择条件
            selected_servers = select_servers(
                servers, server_group.ip_expression, server_group.label_expression
            )

            # 转换为ConnectionConfig
            for server in selected_servers:
                # 找到对应的服务器配置
                server_config = next(
                    (
                        s
                        for s in all_servers
                        if s.host == server.host and s.port == server.port
                    ),
                    None,
                )
                if server_config:
                    config = _server_config_to_connection_config(
                        server_config, timeout, connect_timeout
                    )
                    configs.append(config)

    # 通过表达式选择
    else:
        # 获取命名空间中的所有服务器
        all_servers = storage.list_servers(namespace)

        # 转换为Server对象
        servers = [
            Host(
                name=s.name,
                host=s.host,
                port=s.port,
                username=s.username,
                labels=s.labels,
                namespace=s.namespace,
            )
            for s in all_servers
        ]

        # 应用选择条件
        selected_servers = select_servers(servers, hosts, selector)

        # 转换为ConnectionConfig
        for server in selected_servers:
            server_config = next(
                (
                    s
                    for s in all_servers
                    if s.host == server.host and s.port == server.port
                ),
                None,
            )
            if server_config:
                config = _server_config_to_connection_config(
                    server_config, timeout, connect_timeout
                )
                configs.append(config)

    return configs


def _server_config_to_connection_config(
    server_config: Host, command_timeout: float, connect_timeout: float
) -> ConnectionConfig:
    """转换服务器配置为连接配置"""
    return ConnectionConfig(
        host=server_config.host,
        port=server_config.port,
        name=server_config.name,
        username=server_config.username,
        password=server_config.password,
        private_key=server_config.private_key,
        private_key_path=server_config.private_key_path,
        connect_timeout=connect_timeout,
        command_timeout=command_timeout,
        labels=server_config.labels,
    )
