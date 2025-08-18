"""文件传输模块"""

import asyncio
import asyncssh
from pathlib import Path
from typing import List, Callable
import time

from pypssh.core.models import (
    ConnectionConfig,
    TransferMode,
    TransferResult,
    ExecutionStatus,
)

class FileTransfer:
    """文件传输管理器"""

    def __init__(self, max_concurrent: int = 10, progress_callback: Callable = None):
        self.max_concurrent = max_concurrent
        self.progress_callback = progress_callback
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def upload_parallel(
        self,
        configs: List[ConnectionConfig],
        local_path: str,
        remote_path: str,
        recursive: bool = False,
        preserve: bool = True,
    ) -> List[TransferResult]:
        """并行上传文件到多个主机"""

        tasks = []
        for config in configs:
            task = asyncio.create_task(
                self._upload_single(
                    config, local_path, remote_path, recursive, preserve
                )
            )
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

    async def download_parallel(
        self,
        configs: List[ConnectionConfig],
        remote_path: str,
        local_dir: str,
        recursive: bool = False,
        preserve: bool = True,
    ) -> List[TransferResult]:
        """并行从多个主机下载文件"""

        tasks = []
        for config in configs:
            # 为每个主机创建单独的本地目录
            host_local_dir = Path(local_dir) / config.host
            host_local_dir.mkdir(parents=True, exist_ok=True)

            task = asyncio.create_task(
                self._download_single(
                    config, remote_path, str(host_local_dir), recursive, preserve
                )
            )
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

    async def _upload_single(
        self,
        config: ConnectionConfig,
        local_path: str,
        remote_path: str,
        recursive: bool,
        preserve: bool,
    ) -> TransferResult:
        """上传文件到单个主机"""

        result = TransferResult(
            host=config.host,
            mode=TransferMode.UPLOAD,
            local_path=local_path,
            remote_path=remote_path,
            status=ExecutionStatus.PENDING,
            start_time=time.time(),
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

                # 建立连接并传输文件
                async with asyncssh.connect(**connect_kwargs) as conn:
                    async with conn.start_sftp_client() as sftp:
                        if Path(local_path).is_dir() and recursive:
                            await sftp.put(
                                local_path, remote_path, recurse=True, preserve=preserve
                            )
                        else:
                            await sftp.put(local_path, remote_path, preserve=preserve)

                # 计算传输的字节数
                local_path_obj = Path(local_path)
                if local_path_obj.is_file():
                    result.transferred_bytes = local_path_obj.stat().st_size
                elif local_path_obj.is_dir() and recursive:
                    result.transferred_bytes = sum(
                        f.stat().st_size
                        for f in local_path_obj.rglob("*")
                        if f.is_file()
                    )

                result.status = ExecutionStatus.SUCCESS

            except asyncio.TimeoutError:
                result.status = ExecutionStatus.TIMEOUT
                result.error_message = (
                    f"Transfer timeout after {config.connect_timeout}s"
                )

            except asyncssh.Error as e:
                result.status = ExecutionStatus.ERROR
                result.error_message = f"SSH Error: {str(e)}"

            except Exception as e:
                result.status = ExecutionStatus.ERROR
                result.error_message = f"Transfer error: {str(e)}"

            finally:
                result.end_time = time.time()
                result.transfer_time = result.end_time - result.start_time

        return result

    async def _download_single(
        self,
        config: ConnectionConfig,
        remote_path: str,
        local_dir: str,
        recursive: bool,
        preserve: bool,
    ) -> TransferResult:
        """从单个主机下载文件"""

        local_path = Path(local_dir) / Path(remote_path).name

        result = TransferResult(
            host=config.host,
            mode=TransferMode.DOWNLOAD,
            local_path=str(local_path),
            remote_path=remote_path,
            status=ExecutionStatus.PENDING,
            start_time=time.time(),
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

                # 建立连接并传输文件
                async with asyncssh.connect(**connect_kwargs) as conn:
                    async with conn.start_sftp_client() as sftp:
                        await sftp.get(
                            remote_path,
                            str(local_path),
                            recurse=recursive,
                            preserve=preserve,
                        )

                # 计算传输的字节数
                if local_path.is_file():
                    result.transferred_bytes = local_path.stat().st_size
                elif local_path.is_dir():
                    result.transferred_bytes = sum(
                        f.stat().st_size for f in local_path.rglob("*") if f.is_file()
                    )

                result.status = ExecutionStatus.SUCCESS

            except asyncio.TimeoutError:
                result.status = ExecutionStatus.TIMEOUT
                result.error_message = (
                    f"Transfer timeout after {config.connect_timeout}s"
                )

            except asyncssh.Error as e:
                result.status = ExecutionStatus.ERROR
                result.error_message = f"SSH Error: {str(e)}"

            except Exception as e:
                result.status = ExecutionStatus.ERROR
                result.error_message = f"Transfer error: {str(e)}"

            finally:
                result.end_time = time.time()
                result.transfer_time = result.end_time - result.start_time

        return result
