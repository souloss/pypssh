"""配置管理命令"""

from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pypssh.config.storage import ConfigStorage
from pypssh.core.models import Host, ServerGroup

console = Console()


@click.group()
def config_command():
    """配置管理命令"""
    pass


@config_command.command("create-namespace")
@click.argument("name")
@click.option("--description", "-d", help="命名空间描述")
def create_namespace(name, description):
    """创建命名空间"""

    storage = ConfigStorage()
    try:
        namespace_id = storage.create_namespace(name, description)
        console.print(
            f"[green]✅ Namespace '{name}' created successfully (ID: {namespace_id})[/green]"
        )
    except Exception as e:
        console.print(f"[red]❌ Failed to create namespace: {e}[/red]")


@config_command.command("list-namespaces")
def list_namespaces():
    """列出所有命名空间"""

    storage = ConfigStorage()
    namespaces = storage.list_namespaces()

    if not namespaces:
        console.print("[yellow]No namespaces found[/yellow]")
        return

    table = Table(title="Namespaces")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Created At", style="green")

    for ns in namespaces:
        table.add_row(ns["name"], ns["description"] or "N/A", ns["created_at"] or "N/A")

    console.print(table)


@config_command.command("delete-namespace")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="强制删除，不询问确认")
def delete_namespace(name, force):
    """删除命名空间（会删除其中的所有资源）"""

    if not force:
        if not click.confirm(
            f"Are you sure you want to delete namespace '{name}' and all its resources?"
        ):
            console.print("[yellow]Operation cancelled[/yellow]")
            return

    storage = ConfigStorage()
    if storage.delete_namespace(name):
        console.print(f"[green]✅ Namespace '{name}' deleted successfully[/green]")
    else:
        console.print(f"[red]❌ Namespace '{name}' not found[/red]")


@config_command.command("add-server")
@click.argument("host")
@click.option("--name", default=None, help="主机名称")
@click.option("--namespace", "-n", default="default", help="命名空间")
@click.option("--port", "-p", default=22, help="SSH端口")
@click.option("--username", "-u", default="root", help="用户名")
@click.option("--password", "--pass", help="密码")
@click.option("--private-key", "-k", help="私钥内容")
@click.option("--private-key-path", "-K", help="私钥文件路径")
@click.option("--label", "-l", multiple=True, help="标签，格式: key=value")
@click.option("--connect-timeout", default=10.0, help="连接超时时间")
@click.option("--command-timeout", default=30.0, help="命令超时时间")
def add_server(
    host,
    name,
    namespace,
    port,
    username,
    password,
    private_key,
    private_key_path,
    label,
    connect_timeout,
    command_timeout,
):
    """添加服务器配置"""

    # 解析标签
    labels = {}
    for l in label:
        if "=" in l:
            key, value = l.split("=", 1)
            labels[key.strip()] = value.strip()

    config = Host(
        name=name,
        host=host,
        port=port,
        username=username,
        password=password,
        namespace=namespace,
        private_key=private_key,
        private_key_path=private_key_path,
        labels=labels,
        connect_timeout=connect_timeout,
        command_timeout=command_timeout,
    )

    storage = ConfigStorage()
    try:
        server_id = storage.add_server(config, namespace)
        console.print(
            f"[green]✅ Server '{name}' added successfully in namespace '{namespace}' (ID: {server_id})[/green]"
        )
    except Exception as e:
        console.print(f"[red]❌ Failed to add server: {e}[/red]")


@config_command.command("list-servers")
@click.option("--namespace", "-n", default="default", help="命名空间")
@click.option("--pattern", "-p", help="名称匹配模式")
def list_servers(namespace, pattern):
    """列出服务器配置"""

    storage = ConfigStorage()
    servers = storage.list_servers(namespace, pattern)

    if not servers:
        console.print(f"[yellow]No servers found in namespace '{namespace}'[/yellow]")
        return

    table = Table(title=f"Server Configurations in '{namespace}'")
    table.add_column("Name", style="cyan")
    table.add_column("Host", style="green")
    table.add_column("Port", style="blue")
    table.add_column("Username", style="yellow")
    table.add_column("Labels", style="magenta")

    for server in servers:
        labels_str = ", ".join([f"{k}={v}" for k, v in server.labels.items()])
        table.add_row(
            server.name,
            server.host,
            str(server.port),
            server.username or "N/A",
            labels_str or "N/A",
        )

    console.print(table)


@config_command.command("show-server")
@click.argument("name")
@click.option("--namespace", "-n", default="default", help="命名空间")
def show_server(name, namespace):
    """显示服务器详细配置"""

    storage = ConfigStorage()
    server = storage.get_server(name, namespace)

    if not server:
        console.print(
            f"[red]❌ Server '{name}' not found in namespace '{namespace}'[/red]"
        )
        return

    content = f"""
[bold]Namespace:[/bold] {namespace}
[bold]Host:[/bold] {server.host}
[bold]Port:[/bold] {server.port}
[bold]Username:[/bold] {server.username or 'N/A'}
[bold]Private Key Path:[/bold] {server.private_key_path or 'N/A'}
[bold]Connect Timeout:[/bold] {server.connect_timeout}s
[bold]Command Timeout:[/bold] {server.command_timeout}s
[bold]Labels:[/bold]
"""

    if server.labels:
        for key, value in server.labels.items():
            content += f"  • {key} = {value}\n"
    else:
        content += "  No labels\n"

    console.print(
        Panel(
            content.strip(),
            title=f"[bold blue]Server: {server.name}[/bold blue]",
            border_style="blue",
        )
    )


@config_command.command("update-server")
@click.argument("name")
@click.option("--namespace", "-n", default="default", help="命名空间")
@click.option("--host", help="更新主机地址")
@click.option("--port", type=int, help="更新端口")
@click.option("--username", help="更新用户名")
@click.option("--password", help="更新密码")
@click.option("--private-key-path", help="更新私钥路径")
@click.option("--add-label", multiple=True, help="添加标签，格式: key=value")
@click.option("--remove-label", multiple=True, help="移除标签键")
def update_server(
    name,
    namespace,
    host,
    port,
    username,
    password,
    private_key_path,
    add_label,
    remove_label,
):
    """更新服务器配置"""

    storage = ConfigStorage()
    server = storage.get_server(name, namespace)

    if not server:
        console.print(
            f"[red]❌ Server '{name}' not found in namespace '{namespace}'[/red]"
        )
        return

    updates = {}

    if host:
        updates["host"] = host
    if port:
        updates["port"] = port
    if username:
        updates["username"] = username
    if password:
        updates["password"] = password
    if private_key_path:
        updates["private_key_path"] = private_key_path

    # 处理标签更新
    if add_label or remove_label:
        labels = server.labels.copy()

        # 添加标签
        for label in add_label:
            if "=" in label:
                key, value = label.split("=", 1)
                labels[key.strip()] = value.strip()

        # 移除标签
        for key in remove_label:
            labels.pop(key.strip(), None)

        updates["labels"] = labels

    if updates:
        if storage.update_server(name, updates, namespace):
            console.print(
                f"[green]✅ Server '{name}' updated successfully in namespace '{namespace}'[/green]"
            )
        else:
            console.print(f"[red]❌ Failed to update server '{name}'[/red]")
    else:
        console.print("[yellow]No updates specified[/yellow]")


@config_command.command("delete-server")
@click.argument("name")
@click.option("--namespace", "-n", default="default", help="命名空间")
@click.option("--force", "-f", is_flag=True, help="强制删除，不询问确认")
def delete_server(name, namespace, force):
    """删除服务器配置"""

    if not force:
        if not click.confirm(
            f"Are you sure you want to delete server '{name}' in namespace '{namespace}'?"
        ):
            console.print("[yellow]Operation cancelled[/yellow]")
            return

    storage = ConfigStorage()
    if storage.delete_server(name, namespace):
        console.print(
            f"[green]✅ Server '{name}' deleted successfully from namespace '{namespace}'[/green]"
        )
    else:
        console.print(
            f"[red]❌ Server '{name}' not found in namespace '{namespace}'[/red]"
        )


@config_command.command("add-group")
@click.argument("name")
@click.option("--namespace", "-n", default="default", help="命名空间")
@click.option("--description", "-d", help="组描述")
@click.option("--ip-expression", "-i", help="IP选择表达式")
@click.option("--label-expression", "-l", help="标签选择表达式")
@click.option("--username", "-u", help="默认用户名")
@click.option("--password", "--pass", help="默认密码")
@click.option("--private-key-path", "-k", help="默认私钥路径")
@click.option("--label", multiple=True, help="默认标签，格式: key=value")
def add_group(
    name,
    namespace,
    description,
    ip_expression,
    label_expression,
    username,
    password,
    private_key_path,
    label,
):
    """添加服务器组"""

    # 解析标签
    labels = {}
    for l in label:
        if "=" in l:
            key, value = l.split("=", 1)
            labels[key.strip()] = value.strip()

    group = ServerGroup(
        name=name,
        description=description or "",
        ip_expression=ip_expression,
        label_expression=label_expression,
        default_username=username,
        default_password=password,
        default_private_key_path=private_key_path,
        default_labels=labels,
    )

    storage = ConfigStorage()
    try:
        group_id = storage.add_server_group(group, namespace)
        console.print(
            f"[green]✅ Server group '{name}' added successfully in namespace '{namespace}' (ID: {group_id})[/green]"
        )
    except Exception as e:
        console.print(f"[red]❌ Failed to add server group: {e}[/red]")


@config_command.command("list-groups")
@click.option("--namespace", "-n", default="default", help="命名空间")
def list_groups(namespace):
    """列出服务器组"""

    storage = ConfigStorage()
    groups = storage.list_server_groups(namespace)

    if not groups:
        console.print(
            f"[yellow]No server groups found in namespace '{namespace}'[/yellow]"
        )
        return

    table = Table(title=f"Server Groups in '{namespace}'")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("IP Expression", style="green")
    table.add_column("Label Expression", style="blue")

    for group in groups:
        table.add_row(
            group.name,
            group.description or "N/A",
            group.ip_expression or "N/A",
            group.label_expression or "N/A",
        )

    console.print(table)


@config_command.command("export")
@click.argument("output_file")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    help="导出格式",
)
@click.option("--namespace", "-n", help="导出特定命名空间（不指定则导出所有）")
def export_config(output_file, format, namespace):
    """导出配置"""

    storage = ConfigStorage()
    try:
        storage.export_config(Path(output_file), format, namespace)
        if namespace:
            console.print(
                f"[green]✅ Configuration for namespace '{namespace}' exported to {output_file}[/green]"
            )
        else:
            console.print(
                f"[green]✅ All configurations exported to {output_file}[/green]"
            )
    except Exception as e:
        console.print(f"[red]❌ Export failed: {e}[/red]")


@config_command.command("import")
@click.argument("input_file")
@click.option(
    "--namespace", "-n", help="导入到特定命名空间（不指定则使用配置文件中的命名空间）"
)
def import_config(input_file, namespace):
    """导入配置"""

    storage = ConfigStorage()
    try:
        storage.import_config(Path(input_file), namespace)
        if namespace:
            console.print(
                f"[green]✅ Configuration imported from {input_file} to namespace '{namespace}'[/green]"
            )
        else:
            console.print(f"[green]✅ Configuration imported from {input_file}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Import failed: {e}[/red]")
