"""文件传输命令"""

import asyncio
import click
from pathlib import Path
from pypssh.core.transfer import FileTransfer
from pypssh.ui.formatter import OutputFormatter
from pypssh.commands.execute import _get_target_configs


@click.group()
def file_command():
    """文件传输命令"""
    pass


@file_command.command("upload")
@click.argument("local_path")
@click.argument("remote_path")
@click.option("--namespace", "-n", default="default", help="命名空间")
@click.option("--hosts", "-h", help="主机选择表达式")
@click.option("--selector", "-s", help="标签选择表达式")
@click.option("--group", "-g", help="服务器组名称")
@click.option("--server", multiple=True, help="指定服务器名称")
@click.option("--max-concurrent", "-c", default=10, help="最大并发传输数")
@click.option("--recursive", "-r", is_flag=True, help="递归传输目录")
@click.option("--preserve", "-p", is_flag=True, default=True, help="保持文件属性")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["default", "json", "yaml", "template", "none"]),
    default="default",
    help="输出格式",
)
@click.option("--template", "-T", help="自定义输出模板")
def upload(
    local_path,
    remote_path,
    namespace,
    hosts,
    selector,
    group,
    server,
    max_concurrent,
    recursive,
    preserve,
    output,
    template,
):
    """上传文件到远程主机"""

    # 检查本地文件是否存在
    local_file = Path(local_path)
    if not local_file.exists():
        click.echo(f"Error: Local file '{local_path}' does not exist")
        return

    # 获取目标服务器配置
    configs = _get_target_configs(namespace, hosts, selector, group, server, 30.0, 10.0)

    if not configs:
        click.echo(f"No hosts selected for upload in namespace '{namespace}'")
        return

    click.echo(
        f"Uploading '{local_path}' to {len(configs)} hosts in namespace '{namespace}'..."
    )

    # 执行上传
    asyncio.run(
        _upload_async(
            configs,
            local_path,
            remote_path,
            max_concurrent,
            recursive,
            preserve,
            output,
            template,
        )
    )


@file_command.command("download")
@click.argument("remote_path")
@click.argument("local_dir")
@click.option("--namespace", "-n", default="default", help="命名空间")
@click.option("--hosts", "-h", help="主机选择表达式")
@click.option("--selector", "-s", help="标签选择表达式")
@click.option("--group", "-g", help="服务器组名称")
@click.option("--server", multiple=True, help="指定服务器名称")
@click.option("--max-concurrent", "-c", default=10, help="最大并发传输数")
@click.option("--recursive", "-r", is_flag=True, help="递归下载目录")
@click.option("--preserve", "-p", is_flag=True, default=True, help="保持文件属性")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["default", "json", "yaml", "template", "none"]),
    default="default",
    help="输出格式",
)
@click.option("--template", "-T", help="自定义输出模板")
def download(
    remote_path,
    local_dir,
    namespace,
    hosts,
    selector,
    group,
    server,
    max_concurrent,
    recursive,
    preserve,
    output,
    template,
):
    """从远程主机下载文件"""

    # 创建本地目录
    local_directory = Path(local_dir)
    local_directory.mkdir(parents=True, exist_ok=True)

    # 获取目标服务器配置
    configs = _get_target_configs(namespace, hosts, selector, group, server, 30.0, 10.0)

    if not configs:
        click.echo(f"No hosts selected for download in namespace '{namespace}'")
        return

    click.echo(
        f"Downloading '{remote_path}' from {len(configs)} hosts in namespace '{namespace}'..."
    )

    # 执行下载
    asyncio.run(
        _download_async(
            configs,
            remote_path,
            local_dir,
            max_concurrent,
            recursive,
            preserve,
            output,
            template,
        )
    )


async def _upload_async(
    configs,
    local_path,
    remote_path,
    max_concurrent,
    recursive,
    preserve,
    output_format,
    template,
):
    """异步上传文件"""

    def progress_callback(completed, total, result):
        status_icon = "✅" if result.status.name == "SUCCESS" else "❌"
        click.echo(
            f"{status_icon} {result.host} ({result.transfer_time:.2f}s, {result.transferred_bytes} bytes)"
        )

    # 创建传输器
    transfer = FileTransfer(
        max_concurrent=max_concurrent,
        progress_callback=progress_callback if output_format == "default" else None,
    )

    # 执行上传
    results = await transfer.upload_parallel(
        configs, local_path, remote_path, recursive, preserve
    )

    # 格式化输出
    if output_format != "none":
        formatter = OutputFormatter(output_format, template)
        if output_format in ["json", "yaml", "template"]:
            output = formatter.format_transfer_results(results)
            click.echo(output)
        elif output_format == "default":
            formatter.print_results(results, "Upload Results")


async def _download_async(
    configs,
    remote_path,
    local_dir,
    max_concurrent,
    recursive,
    preserve,
    output_format,
    template,
):
    """异步下载文件"""

    def progress_callback(completed, total, result):
        status_icon = "✅" if result.status.name == "SUCCESS" else "❌"
        click.echo(
            f"{status_icon} {result.host} ({result.transfer_time:.2f}s, {result.transferred_bytes} bytes)"
        )

    # 创建传输器
    transfer = FileTransfer(
        max_concurrent=max_concurrent,
        progress_callback=progress_callback if output_format == "default" else None,
    )

    # 执行下载
    results = await transfer.download_parallel(
        configs, remote_path, local_dir, recursive, preserve
    )

    # 格式化输出
    if output_format != "none":
        formatter = OutputFormatter(output_format, template)
        if output_format in ["json", "yaml", "template"]:
            output = formatter.format_transfer_results(results)
            click.echo(output)
        elif output_format == "default":
            formatter.print_results(results, "Download Results")
