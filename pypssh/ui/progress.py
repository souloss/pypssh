import sys
import time
from typing import List, Optional
from rich.console import Console
from rich.progress import (
    Progress,
    TaskID,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from dataclasses import dataclass

from ..core.models import ExecutionStatus

from ..core.models import ExecutionResult


@dataclass
class ProgressStats:
    total: int = 0
    completed: int = 0
    success: int = 0
    error: int = 0
    timeout: int = 0
    running: int = 0


class ProgressDisplay:
    """友好的进度显示界面"""

    def __init__(self, show_details: bool = True):
        self.console = Console()
        self.show_details = show_details
        self.stats = ProgressStats()
        self.results: List[ExecutionResult] = []
        self.start_time = time.time()

    def start_execution(self, total_hosts: int, command: str):
        """开始执行显示"""
        self.stats.total = total_hosts
        self.start_time = time.time()

        self.console.print(
            Panel(
                f"[bold blue]Executing command on {total_hosts} hosts[/bold blue]\n"
                f"Command: [yellow]{command}[/yellow]",
                title="SSH Parallel Execution",
                border_style="blue",
            )
        )

    def update_progress(self, completed: int, total: int, result: ExecutionResult):
        """更新进度"""
        self.stats.completed = completed
        self.results.append(result)

        # 更新统计
        if result.status == ExecutionStatus.SUCCESS:
            self.stats.success += 1
        elif result.status == ExecutionStatus.ERROR:
            self.stats.error += 1
        elif result.status == ExecutionStatus.TIMEOUT:
            self.stats.timeout += 1

        self.stats.running = total - completed

        # 显示当前结果
        self._display_result(result)

        # 显示进度条
        progress_percent = (completed / total) * 100
        elapsed = time.time() - self.start_time

        self.console.print(
            f"Progress: [{progress_percent:5.1f}%] "
            f"({completed}/{total}) "
            f"✓{self.stats.success} "
            f"✗{self.stats.error} "
            f"⏱{self.stats.timeout} "
            f"⚡{elapsed:.1f}s"
        )

    def _display_result(self, result: ExecutionResult):
        """显示单个执行结果"""
        status_icons = {
            ExecutionStatus.SUCCESS: "✅",
            ExecutionStatus.ERROR: "❌",
            ExecutionStatus.TIMEOUT: "⏰",
        }

        icon = status_icons.get(result.status, "❓")

        if result.status == ExecutionStatus.SUCCESS:
            color = "green"
        elif result.status == ExecutionStatus.ERROR:
            color = "red"
        elif result.status == ExecutionStatus.TIMEOUT:
            color = "yellow"
        else:
            color = "white"

        self.console.print(
            f"{icon} [{color}]{result.host}[/{color}] "
            f"({result.execution_time:.2f}s)"
        )

        if self.show_details and result.status != ExecutionStatus.SUCCESS:
            if result.stderr:
                self.console.print(f"   [red]Error: {result.stderr.strip()}[/red]")
            if result.error_message:
                self.console.print(f"   [red]Message: {result.error_message}[/red]")

    def finish_execution(self):
        """完成执行显示"""
        elapsed = time.time() - self.start_time

        # 创建汇总表格
        table = Table(title="Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="white")
        table.add_column("Percentage", style="white")

        total = self.stats.total
        table.add_row("Total Hosts", str(total), "100.0%")
        table.add_row(
            "✅ Success",
            str(self.stats.success),
            f"{(self.stats.success/total)*100:.1f}%",
        )
        table.add_row(
            "❌ Errors", str(self.stats.error), f"{(self.stats.error/total)*100:.1f}%"
        )
        table.add_row(
            "⏰ Timeouts",
            str(self.stats.timeout),
            f"{(self.stats.timeout/total)*100:.1f}%",
        )
        table.add_row("⚡ Total Time", f"{elapsed:.2f}s", "-")

        self.console.print(table)

        # 显示失败的主机详情
        if self.stats.error > 0 or self.stats.timeout > 0:
            self._show_failed_hosts()

    def _show_failed_hosts(self):
        """显示失败主机的详细信息"""
        failed_results = [
            r
            for r in self.results
            if r.status in [ExecutionStatus.ERROR, ExecutionStatus.TIMEOUT]
        ]

        if not failed_results:
            return

        self.console.print("\n[bold red]Failed Hosts Details:[/bold red]")

        for result in failed_results:
            self.console.print(
                Panel(
                    f"[red]Host: {result.host}[/red]\n"
                    f"Status: {result.status.value}\n"
                    f"Error: {result.error_message or 'N/A'}\n"
                    f"Stderr: {result.stderr or 'N/A'}",
                    border_style="red",
                )
            )


def create_progress_callback(display: ProgressDisplay):
    """创建进度回调函数"""

    def callback(completed: int, total: int, result: ExecutionResult):
        display.update_progress(completed, total, result)

    return callback
