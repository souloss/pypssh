"""主命令行接口"""

import click
from pathlib import Path

from .commands.config import config_command
from .commands.execute import execute_command
from .commands.file import file_command
from .commands.ping import ping_command

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

# 为了向后兼容，添加一些直接命令别名
@cli.command()
@click.argument("command")
@click.option("--hosts", "-h", help="主机列表文件或IP范围")
@click.option("--user", "-u", help="SSH用户名")
@click.option("--port", "-p", default=22, help="SSH端口")
@click.option("--timeout", "-t", default=30, help="超时时间")
@click.option("--max-concurrent", "-c", default=50, help="最大并发数")
@click.option("--needpty", is_flag=True, help="分配伪终端")
@click.option("--sudo", is_flag=True, help="使用sudo执行")
@click.option("--output", "-o", type=click.Choice(['none', 'template', 'json', 'yaml']), 
              default='none', help="输出格式")
@click.option("--template", "-T", help="输出模板")
def run(command, hosts, user, port, timeout, max_concurrent, needpty, sudo, output, template):
    """直接执行命令 (兼容原版接口)"""
    
    # 这里需要适配原始的主机列表格式
    # 暂时使用简单的实现
    
    if hosts:
        if Path(hosts).exists():
            # 从文件读取主机列表
            with open(hosts) as f:
                host_list = [line.strip() for line in f if line.strip()]
        else:
            # 直接使用IP表达式
            host_list = hosts.split(',')
        
        # 为每个主机创建临时配置并执行
        from .core.models import Host
        from .commands.execute import _server_config_to_connection_config
        import asyncio
        from .core.executor import SSHExecutor
        from .ui.formatter import OutputFormatter
        
        configs = []
        for host in host_list:
            server_config = Host(
                name=host,
                host=host,
                port=port,
                username=user,
                command_timeout=timeout
            )
            config = _server_config_to_connection_config(server_config, timeout, 10.0)
            configs.append(config)
        
        # 构建最终命令
        final_command = command
        if sudo:
            final_command = f"sudo {command}"
        
        # 执行命令
        async def execute():
            executor = SSHExecutor(max_concurrent=max_concurrent)
            results = await executor.execute_parallel(configs, final_command)
            
            # 格式化输出
            formatter = OutputFormatter(output or 'default', template)
            if output == 'none':
                return
            elif output in ['json', 'yaml', 'template']:
                output_str = formatter.format_execution_results(results)
                click.echo(output_str)
            else:
                formatter.print_results(results)
        
        asyncio.run(execute())
    else:
        click.echo("Error: --hosts option is required")

def main():
    """主入口函数"""
    cli()

if __name__ == "__main__":
    main()