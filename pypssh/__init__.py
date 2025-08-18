"""PyPSSH - Advanced Parallel SSH Client"""

__version__ = "2.0.0"
__author__ = "PyPSSH Team"
__email__ = "pypssh@example.com"

from .core.executor import SSHExecutor
from .core.transfer import FileTransfer
from .core.connectivity import ConnectivityTester
from .selector.ip_selector import IPSelector
from .selector.label_selector import LabelSelector
from .config.storage import ConfigStorage
from .core.models import (
    ConnectionConfig,
    ConnectivityResult,
    ExecutionResult,
    Host,
    ServerGroup,
    TransferResult,
)

__all__ = [
    "SSHExecutor",
    "ExecutionResult",
    "ConnectionConfig",
    "FileTransfer",
    "TransferResult",
    "ConnectivityTester",
    "ConnectivityResult",
    "IPSelector",
    "LabelSelector",
    "ConfigStorage",
    "Host",
    "ServerGroup",
]
