"""连通性测试命令"""

import asyncio
import click
from pypssh.core.connectivity import ConnectivityTester
from pypssh.ui.formatter import OutputFormatter
from pypssh.commands.execute import _get_target_configs


@click.command()
@click.option("--namespace", "-n", default="default", help="命名空间")
@click.option("--hosts", "-h", help="主机选择表达式")
@click.option("--selector", "-s", help="标签选择表达式")
@click.option("--group", "-g", help="服务器组名称")
@click.option("--server", multiple=True, help="指定服务器名称")
@click.option("--max-concurrent", "-c", default=50, help="最大并发数")
@click.option("--timeout", "-t", default=5.0, help="连接超时时间")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["default", "json", "yaml", "template", "none"]),
    default="default",
    help="输出格式",
)
@click.option("--template", "-T", help="自定义输出模板")
def ping_command(
    namespace, hosts, selector, group, server, max_concurrent, timeout, output, template
):
    """测试主机连通性"""

    # 获取目标服务器配置
    configs = _get_target_configs(
        namespace, hosts, selector, group, server, 30.0, timeout
    )

    if not configs:
        click.echo(f"No hosts selected for ping test in namespace '{namespace}'")
        return

    click.echo(
        f"Testing connectivity to {len(configs)} hosts in namespace '{namespace}'..."
    )

    # 执行连通性测试
    asyncio.run(_ping_async(configs, max_concurrent, output, template))


async def _ping_async(configs, max_concurrent, output_format, template):
    """异步连通性测试"""

    def progress_callback(completed, total, result):
        if result.status.name == "REACHABLE":
            icon = "🟢"
        elif result.status.name == "TIMEOUT":
            icon = "🟡"
        elif result.status.name == "AUTH_FAILED":
            icon = "🔑"
        else:
            icon = "🔴"

        ssh_status = "SSH:✅" if result.ssh_available else "SSH:❌"
        click.echo(
            f"{icon} {result.host}:{result.port} ({result.response_time:.3f}s) {ssh_status}"
        )

    # 创建连通性测试器
    tester = ConnectivityTester(
        max_concurrent=max_concurrent,
        progress_callback=progress_callback if output_format == "default" else None,
    )

    # 执行测试
    results = await tester.test_parallel(configs)

    # 格式化输出
    if output_format != "none":
        formatter = OutputFormatter(output_format, template)
        if output_format in ["json", "yaml", "template"]:
            output = formatter.format_connectivity_results(results)
            click.echo(output)
        elif output_format == "default":
            formatter.print_results(results, "Connectivity Test Results")

    # 显示统计信息
    total = len(results)
    reachable = len([r for r in results if r.status.name == "REACHABLE"])
    unreachable = len([r for r in results if r.status.name == "UNREACHABLE"])
    timeout = len([r for r in results if r.status.name == "TIMEOUT"])
    auth_failed = len([r for r in results if r.status.name == "AUTH_FAILED"])

    click.echo(
        f"\nSummary: {reachable}/{total} reachable, {unreachable} unreachable, {timeout} timeout, {auth_failed} auth failed"
    )
