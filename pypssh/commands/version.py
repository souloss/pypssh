import os
import ssl
import sys
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

def get_resource_path(relative_path: str):
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_build_git_sha():
    filename = get_resource_path("BUILD_GITSHA")
    if not os.path.exists(filename):
        return "unknown"
    with open(filename) as fh:
        return fh.read().strip()


def get_build_repo():
    filename = get_resource_path("BUILD_GITREPO")
    if not os.path.exists(filename):
        return "unknown"
    with open(filename) as fh:
        repolist = [tuple(i.split()) for i in fh.read().strip().split("\n")]
        return repolist


def get_build_date():
    filename = get_resource_path("BUILD_DATE")
    if not os.path.exists(filename):
        return "unknown"
    with open(filename) as fh:
        return fh.read().strip()


def get_last_commit_date():
    filename = get_resource_path("BUILD_LASTCOMMITDATE")
    if not os.path.exists(filename):
        return "unknown"
    with open(filename) as fh:
        return fh.read().strip()

def get_git_tag():
    filename = get_resource_path("BUILD_GITTAG")
    if not os.path.exists(filename):
        return "dev"
    with open(filename) as fh:
        return fh.read().strip()

def print_version():
    """
    print version
    """
    addr = "https://github.com/souloss/pypssh"
    # version definition
    vno = get_git_tag()
    interrupt_version = "Python " + " ".join(sys.version.split("\n"))
    click.echo(
        "\n".join(
            [
                f"Github: {addr}",
                f"Version: {vno}",
                f"Running-Interrupt-Version: {interrupt_version}",
                f"Running-Platform: {sys.platform}",
                f"OpenSSL version: {ssl.OPENSSL_VERSION}",
                f"BUILD_DATE: {get_build_date()}",
                f"BUILD_GIT_SHA: {get_build_git_sha()}",
                f"BUID_LAST_COMMIT_DATE: {get_last_commit_date()}",
                f"BUILD_GIT_REPO: {get_build_repo()}",
            ]
        )
    )


def print_version_by_rich():
    """
    使用 Rich 库输出美观的版本信息
    """
    console = Console()

    # 获取版本数据
    build_date = get_build_date()
    git_sha = get_build_git_sha()
    last_commit = get_last_commit_date()
    repos = get_build_repo()

    # 创建主表格
    table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    table.add_column("Key", style="cyan bold", width=20)
    table.add_column("Value", style="white")

    # 程序信息
    table.add_row("Program", "pypssh", style="on blue")
    table.add_row("Version", get_git_tag(), style="bright_green")
    table.add_row("Repository", "https://github.com/souloss/pypssh")

    # 环境信息
    table.add_row("Python", " ".join(sys.version.split("\n")))
    table.add_row("Platform", sys.platform)
    table.add_row("OpenSSL", ssl.OPENSSL_VERSION)

    # 构建信息
    table.add_row("Build Date", build_date)
    table.add_row("Git SHA", git_sha)
    table.add_row("Last Commit", last_commit)

    # 创建标题面板
    title_panel = Panel(
        Text(f"pypssh {get_git_tag()}", justify="center", style="bold yellow on dark_blue"),
        subtitle=f"Built on {build_date}",
        subtitle_align="right",
        style="blue",
    )

    # 创建状态面板
    status_table = Table.grid(padding=(0, 2))
    status_table.add_column(style="cyan")
    status_table.add_column(style="white")

    # 添加状态信息
    status_table.add_row("Status", "[green]✓ Stable")
    status_table.add_row("License", "MIT")
    status_table.add_row("Maintainer", "souloss")

    status_panel = Panel(
        status_table,
        title="[b]Project Status[/b]",
        border_style="green",
        box=box.ROUNDED,
    )

    # 组合输出
    console.print()
    console.print(title_panel)
    console.print()
    console.print(Panel(table, title="[b]Version Details[/b]", border_style="yellow"))
    console.print()
    console.print(status_panel)
    console.print()


@click.command()
@click.option("--simple", "-s", is_flag=True, default=False, help="简化版输出")
def version_command(simple):
    """
    打印版本信息
    """
    if simple:
        print_version()
    else:
        print_version_by_rich()
