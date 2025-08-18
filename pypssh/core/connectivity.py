"""连通性测试模块"""

import asyncio
import asyncssh
import time
from typing import List, Callable

from pypssh.core.models import (
    ConnectivityResult,
    ConnectivityStatus,
    ConnectionConfig,
)


class ConnectivityTester:
    """连通性测试器"""

    def __init__(self, max_concurrent: int = 50, progress_callback: Callable = None):
        self.max_concurrent = max_concurrent
        self.progress_callback = progress_callback
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def test_parallel(
        self, configs: List[ConnectionConfig]
    ) -> List[ConnectivityResult]:
        """并行测试连通性"""

        tasks = []
        for config in configs:
            task = asyncio.create_task(self._test_single(config))
            tasks.append(task)

        results = []
        completed = 0
        total = len(tasks)

        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            completed += 1

            if self.progress_callback:
                self.progress_callback(completed, total, result)

        return results

    async def _test_single(self, config: ConnectionConfig) -> ConnectivityResult:
        """测试单个主机连通性"""

        result = ConnectivityResult(
            host=config.host,
            port=config.port,
            status=ConnectivityStatus.UNREACHABLE,
            start_time=time.time(),
        )

        async with self._semaphore:
            try:
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

                # 尝试建立SSH连接
                async with asyncssh.connect(**connect_kwargs) as conn:
                    # 执行简单命令测试
                    ssh_result = await asyncio.wait_for(
                        conn.run('echo "connectivity_test"', check=False), timeout=5.0
                    )

                    if ssh_result.exit_status == 0:
                        result.status = ConnectivityStatus.REACHABLE
                        result.ssh_available = True
                    else:
                        result.status = ConnectivityStatus.REACHABLE
                        result.ssh_available = False
                        result.error_message = (
                            "SSH connection established but command execution failed"
                        )

            except asyncio.TimeoutError:
                result.status = ConnectivityStatus.TIMEOUT
                result.error_message = (
                    f"Connection timeout after {config.connect_timeout}s"
                )

            except asyncssh.PermissionDenied:
                result.status = ConnectivityStatus.AUTH_FAILED
                result.error_message = "Authentication failed"

            except asyncssh.Error as e:
                result.status = ConnectivityStatus.UNREACHABLE
                result.error_message = f"SSH Error: {str(e)}"

            except Exception as e:
                result.status = ConnectivityStatus.UNREACHABLE
                result.error_message = f"Connection error: {str(e)}"

            finally:
                result.end_time = time.time()
                result.response_time = result.end_time - result.start_time

        return result
