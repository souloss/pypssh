from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

class TransferMode(Enum):
    UPLOAD = "upload"
    DOWNLOAD = "download"


class ConnectivityStatus(Enum):
    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"
    TIMEOUT = "timeout"
    AUTH_FAILED = "auth_failed"


@dataclass
class BaseEndpoint:
    """所有与主机相关的结构都继承的基类"""

    host: str
    port: int = 22
    username: Optional[str] = None
    password: Optional[str] = None
    private_key: Optional[str] = None
    private_key_path: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class BaseResult:
    """所有执行结果的基类"""

    host: str
    status: ExecutionStatus
    error_message: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class Host(BaseEndpoint):
    """主机类"""

    namespace: Optional[str] = None
    connect_timeout: float = 10.0
    command_timeout: float = 30.0
    name: Optional[str] = None

    def __post_init__(self):
        # 如果 name 为空（None 或空字符串），就复用 host
        if not self.name:
            self.name = f"{ self.username if self.username else "root" }@{self.host}:{self.port if self.port else "22"}"

@dataclass
class ServerGroup:
    """服务器组配置"""

    name: str
    namespace: str = None
    description: str = ""
    ip_expression: str = None
    label_expression: str = None
    default_username: str = None
    default_password: str = None
    default_private_key: str = None
    default_private_key_path: str = None
    default_labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ConfigDatabase:
    """配置数据库模型"""

    servers: Dict[str, Host] = field(default_factory=dict)
    groups: Dict[str, ServerGroup] = field(default_factory=dict)


@dataclass
class TransferResult(BaseResult):
    mode: TransferMode = None
    local_path: str = ""
    remote_path: str = ""
    transferred_bytes: int = 0
    transfer_time: float = 0.0

@dataclass
class ConnectionConfig(BaseEndpoint):
    """运行时连接参数"""

    name: Optional[str] = None  # 仅用于日志
    known_hosts: Optional[str] = None
    connect_timeout: float = 10.0
    command_timeout: float = 30.0


@dataclass
class ExecutionResult(BaseResult):
    port: int = 22
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    execution_time: float = 0.0

@dataclass
class ConnectivityResult(BaseResult):
    port: int = 22
    response_time: float = 0.0
    ssh_available: bool = False
