"""主命令行接口"""

import click
from pathlib import Path

from pypssh.commands.config import config_command
from pypssh.commands.execute import execute_command
from pypssh.commands.file import file_command
from pypssh.commands.ping import ping_command
from pypssh.commands.version import version_command

@click.group()
@click.version_option(version="2.0.0")
@click.option("--config-dir", type=click.Path(), help="配置目录路径")
@click.pass_context
def cli(ctx, config_dir):
    """PyPSSH - Advanced Parallel SSH Client
    
    A powerful tool for executing commands, transferring files, and managing 
    SSH connections across multiple hosts with smart selection capabilities.
    """
    ctx.ensure_object(dict)
    if config_dir:
        ctx.obj['config_dir'] = Path(config_dir)

# 注册子命令
cli.add_command(config_command, name="config")
cli.add_command(execute_command, name="exec")
cli.add_command(file_command, name="file")
cli.add_command(ping_command, name="ping")
cli.add_command(version_command, name="version")


def main():
    """主入口函数"""
    cli()

if __name__ == "__main__":
    main()
