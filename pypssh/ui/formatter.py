"""输出格式化模块"""

import json
import yaml
from typing import Any, Dict, List, Optional
from string import Template
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from ..core.models import ConnectivityStatus, ExecutionStatus, TransferResult

from ..core.models import ExecutionResult
from ..core.models import TransferMode
from ..core.models import ConnectivityResult


class OutputFormatter:
    """输出格式化器"""

    def __init__(self, format_type: str = "default", template: str = None):
        self.format_type = format_type.lower()
        self.template = template
        self.console = Console()

    def format_execution_results(self, results: List[ExecutionResult]) -> str:
        """格式化执行结果"""
        if self.format_type == "none":
            return ""
        elif self.format_type == "json":
            return self._format_json(results)
        elif self.format_type == "yaml":
            return self._format_yaml(results)
        elif self.format_type == "template" and self.template:
            return self._format_template(results)
        else:
            return self._format_default_execution(results)

    def format_transfer_results(self, results: List[TransferResult]) -> str:
        """格式化传输结果"""
        if self.format_type == "none":
            return ""
        elif self.format_type == "json":
            return self._format_json(results)
        elif self.format_type == "yaml":
            return self._format_yaml(results)
        elif self.format_type == "template" and self.template:
            return self._format_template(results)
        else:
            return self._format_default_transfer(results)

    def format_connectivity_results(self, results: List[ConnectivityResult]) -> str:
        """格式化连通性测试结果"""
        if self.format_type == "none":
            return ""
        elif self.format_type == "json":
            return self._format_json(results)
        elif self.format_type == "yaml":
            return self._format_yaml(results)
        elif self.format_type == "template" and self.template:
            return self._format_template(results)
        else:
            return self._format_default_connectivity(results)

    def _format_json(self, results: List[Any]) -> str:
        """格式化为JSON"""
        data = []
        for result in results:
            if hasattr(result, "__dict__"):
                item = result.__dict__.copy()
                # 转换枚举值
                for key, value in item.items():
                    if hasattr(value, "value"):
                        item[key] = value.value
                data.append(item)
            else:
                data.append(result)

        return json.dumps(data, indent=2, ensure_ascii=False)

    def _format_yaml(self, results: List[Any]) -> str:
        """格式化为YAML"""
        data = []
        for result in results:
            if hasattr(result, "__dict__"):
                item = result.__dict__.copy()
                # 转换枚举值
                for key, value in item.items():
                    if hasattr(value, "value"):
                        item[key] = value.value
                data.append(item)
            else:
                data.append(result)

        return yaml.dump(data, indent=2, allow_unicode=True)

    def _format_template(self, results: List[Any]) -> str:
        """使用模板格式化"""
        output_lines = []
        template = Template(self.template)

        for result in results:
            if hasattr(result, "__dict__"):
                context = result.__dict__.copy()
                # 转换枚举值
                for key, value in context.items():
                    if hasattr(value, "value"):
                        context[key] = value.value

                try:
                    output_lines.append(template.substitute(context))
                except KeyError as e:
                    output_lines.append(
                        f"Template error for {result.host}: Missing key {e}"
                    )
            else:
                output_lines.append(str(result))

        return "\n".join(output_lines)

    def _format_default_execution(self, results: List[ExecutionResult]) -> str:
        """默认格式化执行结果"""
        output_lines = []

        for result in results:
            # 主机头部
            status_icon = "✅" if result.status == ExecutionStatus.SUCCESS else "❌"
            header = f"\n{status_icon} {result.host} ({result.execution_time:.2f}s)"
            output_lines.append(header)

            # 标准输出
            if result.stdout:
                output_lines.append("STDOUT:")
                output_lines.append(result.stdout.rstrip())

            # 错误输出
            if result.stderr:
                output_lines.append("STDERR:")
                output_lines.append(result.stderr.rstrip())

            # 错误信息
            if result.error_message:
                output_lines.append(f"ERROR: {result.error_message}")

            # 退出码
            if result.exit_code is not None:
                output_lines.append(f"EXIT CODE: {result.exit_code}")

            output_lines.append("-" * 50)

        return "\n".join(output_lines)

    def _format_default_transfer(self, results: List[TransferResult]) -> str:
        """默认格式化传输结果"""
        output_lines = []

        for result in results:
            status_icon = "✅" if result.status == ExecutionStatus.SUCCESS else "❌"
            mode_icon = "⬆️" if result.mode == TransferMode.UPLOAD else "⬇️"

            header = (
                f"{status_icon} {mode_icon} {result.host} "
                f"({result.transfer_time:.2f}s, {result.transferred_bytes} bytes)"
            )
            output_lines.append(header)

            output_lines.append(f"  Local:  {result.local_path}")
            output_lines.append(f"  Remote: {result.remote_path}")

            if result.error_message:
                output_lines.append(f"  ERROR: {result.error_message}")

            output_lines.append("")

        return "\n".join(output_lines)

    def _format_default_connectivity(self, results: List[ConnectivityResult]) -> str:
        """默认格式化连通性测试结果"""
        output_lines = []

        for result in results:
            if result.status == ConnectivityStatus.REACHABLE:
                icon = "🟢"
            elif result.status == ConnectivityStatus.TIMEOUT:
                icon = "🟡"
            elif result.status == ConnectivityStatus.AUTH_FAILED:
                icon = "🔑"
            else:
                icon = "🔴"

            line = (
                f"{icon} {result.host}:{result.port} "
                f"({result.response_time:.3f}s) - {result.status.value}"
            )

            if result.ssh_available:
                line += " [SSH OK]"

            if result.error_message:
                line += f" - {result.error_message}"

            output_lines.append(line)

        return "\n".join(output_lines)

    def print_results(self, results: List[Any], title: str = None):
        """使用Rich打印格式化结果"""
        if self.format_type in ["json", "yaml", "template"]:
            # 对于结构化格式，直接打印
            formatted = (
                self.format_execution_results(results)
                if isinstance(results[0], ExecutionResult)
                else (
                    self.format_transfer_results(results)
                    if isinstance(results[0], TransferResult)
                    else self.format_connectivity_results(results)
                )
            )
            print(formatted)
        else:
            # 对于默认格式，使用Rich美化输出
            if isinstance(results[0], ExecutionResult):
                self._print_execution_results_rich(results, title)
            elif isinstance(results[0], TransferResult):
                self._print_transfer_results_rich(results, title)
            elif isinstance(results[0], ConnectivityResult):
                self._print_connectivity_results_rich(results, title)

    def _print_execution_results_rich(
        self, results: List[ExecutionResult], title: str = None
    ):
        """使用Rich打印执行结果"""
        for result in results:
            # 确定面板颜色
            if result.status == ExecutionStatus.SUCCESS:
                border_style = "green"
                status_text = "[green]✅ SUCCESS[/green]"
            elif result.status == ExecutionStatus.ERROR:
                border_style = "red"
                status_text = "[red]❌ ERROR[/red]"
            elif result.status == ExecutionStatus.TIMEOUT:
                border_style = "yellow"
                status_text = "[yellow]⏰ TIMEOUT[/yellow]"
            else:
                border_style = "white"
                status_text = "[white]❓ UNKNOWN[/white]"

            # 构建内容
            content_lines = []
            content_lines.append(f"{status_text} ({result.execution_time:.2f}s)")

            if result.exit_code is not None:
                content_lines.append(f"Exit Code: {result.exit_code}")

            if result.stdout:
                content_lines.append("\n[bold]STDOUT:[/bold]")
                content_lines.append(result.stdout.rstrip())

            if result.stderr:
                content_lines.append("\n[bold red]STDERR:[/bold red]")
                content_lines.append(f"[red]{result.stderr.rstrip()}[/red]")

            if result.error_message:
                content_lines.append(
                    f"\n[bold red]ERROR:[/bold red] [red]{result.error_message}[/red]"
                )

            # 显示面板
            self.console.print(
                Panel(
                    "\n".join(content_lines),
                    title=f"[bold]{result.host}[/bold]",
                    border_style=border_style,
                    expand=False,
                )
            )

    def _print_transfer_results_rich(
        self, results: List[TransferResult], title: str = None
    ):
        """使用Rich打印传输结果"""
        table = Table(title=title or "Transfer Results")
        table.add_column("Host", style="cyan")
        table.add_column("Mode", style="blue")
        table.add_column("Status", style="white")
        table.add_column("Size", style="green")
        table.add_column("Time", style="yellow")
        table.add_column("Error", style="red")

        for result in results:
            status_text = "✅" if result.status == ExecutionStatus.SUCCESS else "❌"
            mode_text = (
                "⬆️ Upload" if result.mode == TransferMode.UPLOAD else "⬇️ Download"
            )
            size_text = f"{result.transferred_bytes:,} bytes"
            time_text = f"{result.transfer_time:.2f}s"
            error_text = (
                result.error_message[:50] + "..."
                if len(result.error_message) > 50
                else result.error_message
            )

            table.add_row(
                result.host, mode_text, status_text, size_text, time_text, error_text
            )

        self.console.print(table)

    def _print_connectivity_results_rich(
        self, results: List[ConnectivityResult], title: str = None
    ):
        """使用Rich打印连通性测试结果"""
        table = Table(title=title or "Connectivity Test Results")
        table.add_column("Host", style="cyan")
        table.add_column("Port", style="blue")
        table.add_column("Status", style="white")
        table.add_column("Response Time", style="green")
        table.add_column("SSH", style="yellow")
        table.add_column("Error", style="red")

        for result in results:
            if result.status == ConnectivityStatus.REACHABLE:
                status_text = "[green]🟢 Reachable[/green]"
            elif result.status == ConnectivityStatus.TIMEOUT:
                status_text = "[yellow]🟡 Timeout[/yellow]"
            elif result.status == ConnectivityStatus.AUTH_FAILED:
                status_text = "[blue]🔑 Auth Failed[/blue]"
            else:
                status_text = "[red]🔴 Unreachable[/red]"

            ssh_text = "✅" if result.ssh_available else "❌"
            response_text = f"{result.response_time:.3f}s"
            error_text = (
                result.error_message[:30] + "..."
                if len(result.error_message) > 30
                else result.error_message
            )

            table.add_row(
                result.host,
                str(result.port),
                status_text,
                response_text,
                ssh_text,
                error_text,
            )

        self.console.print(table)
