import asyncio
import asyncssh
import time
from typing import List, Callable
import logging

from pypssh.core.models import ConnectionConfig, ExecutionResult, ExecutionStatus


class SSHExecutor:
    """优化的SSH并行执行器"""

    def __init__(self, max_concurrent: int = 50, progress_callback: Callable = None):
        self.max_concurrent = max_concurrent
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def execute_parallel(
        self, configs: List[ConnectionConfig], command: str, stop_on_error: bool = False
    ) -> List[ExecutionResult]:
        """并行执行SSH命令"""

        tasks = []
        results = []

        for config in configs:
            task = asyncio.create_task(self._execute_single(config, command))
            tasks.append((config.host, task))

        completed = 0
        total = len(tasks)

        # 等待所有任务完成
        for host, task in tasks:
            try:
                result = await task
                results.append(result)
                completed += 1

                if self.progress_callback:
                    self.progress_callback(completed, total, result)

                # 如果设置了遇错停止且当前任务失败
                if stop_on_error and result.status == ExecutionStatus.ERROR:
                    # 取消剩余任务
                    for _, remaining_task in tasks[completed:]:
                        remaining_task.cancel()
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Unexpected error for {host}: {e}")
                results.append(
                    ExecutionResult(
                        host=host, status=ExecutionStatus.ERROR, error_message=str(e)
                    )
                )

        return results

    async def _execute_single(
        self, config: ConnectionConfig, command: str
    ) -> ExecutionResult:
        """在单个主机上执行命令"""

        result = ExecutionResult(
            host=config.host, status=ExecutionStatus.PENDING, start_time=time.time()
        )

        async with self._semaphore:
            try:
                result.status = ExecutionStatus.RUNNING

                # 准备连接参数
                connect_kwargs = {
                    "host": config.host,
                    "port": config.port,
                    "username": config.username,
                    "connect_timeout": config.connect_timeout,
                    "known_hosts": config.known_hosts,
                }

                if config.password:
                    connect_kwargs["password"] = config.password
                elif config.private_key:
                    connect_kwargs["client_keys"] = [config.private_key]
                elif config.private_key_path:
                    connect_kwargs["client_keys"] = [config.private_key_path]

                # 建立连接并执行命令
                async with asyncssh.connect(**connect_kwargs) as conn:
                    ssh_result = await asyncio.wait_for(
                        conn.run(command, check=False), timeout=config.command_timeout
                    )

                    result.stdout = ssh_result.stdout
                    result.stderr = ssh_result.stderr
                    result.exit_code = ssh_result.exit_status
                    result.status = (
                        ExecutionStatus.SUCCESS
                        if ssh_result.exit_status == 0
                        else ExecutionStatus.ERROR
                    )

            except asyncio.TimeoutError:
                result.status = ExecutionStatus.TIMEOUT
                result.error_message = (
                    f"Command timeout after {config.command_timeout}s"
                )
                self.logger.warning(f"Timeout executing command on {config.host}")

            except asyncssh.Error as e:
                result.status = ExecutionStatus.ERROR
                result.error_message = f"SSH Error: {str(e)}"
                self.logger.error(f"SSH error for {config.host}: {e}")

            except Exception as e:
                result.status = ExecutionStatus.ERROR
                result.error_message = f"Unexpected error: {str(e)}"
                self.logger.error(f"Unexpected error for {config.host}: {e}")

            finally:
                result.end_time = time.time()
                result.execution_time = result.end_time - result.start_time

        return result
