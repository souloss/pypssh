"""配置存储管理"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import asdict
import sqlite3
from contextlib import contextmanager
from pypssh.core.models import Host, ServerGroup


class ConfigStorage:
    """配置存储管理器（明文存储）"""

    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path.home() / ".pypssh"
        self.config_dir.mkdir(exist_ok=True)

        self.db_path = self.config_dir / "pypssh.db"
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        with self._get_connection() as conn:
            # 创建命名空间表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS namespaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # 创建服务器配置表（明文字段）
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER DEFAULT 22,
                    username TEXT,
                    password TEXT,  -- 明文存储
                    private_key TEXT,  -- 明文存储
                    private_key_path TEXT,
                    labels TEXT,  -- JSON格式的标签
                    connect_timeout REAL DEFAULT 10.0,
                    command_timeout REAL DEFAULT 30.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(namespace_id, name),
                    FOREIGN KEY (namespace_id) REFERENCES namespaces(id) ON DELETE CASCADE
                )
            """
            )

            # 创建服务器组表（明文字段）
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS server_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    ip_expression TEXT,
                    label_expression TEXT,
                    default_username TEXT,
                    default_password TEXT,  -- 明文存储
                    default_private_key TEXT,  -- 明文存储
                    default_private_key_path TEXT,
                    default_labels TEXT,  -- JSON格式的默认标签
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(namespace_id, name),
                    FOREIGN KEY (namespace_id) REFERENCES namespaces(id) ON DELETE CASCADE
                )
            """
            )

            # 创建默认命名空间
            conn.execute(
                """
                INSERT OR IGNORE INTO namespaces (name, description) 
                VALUES ('default', 'Default namespace')
            """
            )

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # 命名空间管理方法
    def create_namespace(self, name: str, description: str = None) -> int:
        """创建命名空间"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO namespaces (name, description) VALUES (?, ?)
            """,
                (name, description),
            )
            conn.commit()
            return cursor.lastrowid

    def get_namespace(self, name: str) -> Optional[Dict[str, Any]]:
        """获取命名空间"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM namespaces WHERE name = ?", (name,)
            ).fetchone()

            if not row:
                return None

            return dict(row)

    def list_namespaces(self) -> List[Dict[str, Any]]:
        """列出所有命名空间"""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM namespaces ORDER BY name").fetchall()

            return [dict(row) for row in rows]

    def delete_namespace(self, name: str) -> bool:
        """删除命名空间（会级联删除其中的所有资源）"""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM namespaces WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0

    def _get_namespace_id(self, namespace: str) -> Optional[int]:
        """获取命名空间ID"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM namespaces WHERE name = ?", (namespace,)
            ).fetchone()

            if not row:
                return None

            return row["id"]

    # 服务器管理方法
    def add_server(self, config: Host, namespace: str = "default") -> int:
        """添加服务器配置"""
        namespace_id = self._get_namespace_id(namespace)
        if not namespace_id:
            raise ValueError(f"Namespace '{namespace}' does not exist")

        with self._get_connection() as conn:
            labels_json = json.dumps(config.labels or {})

            cursor = conn.execute(
                """
                INSERT INTO servers (
                    namespace_id, name, host, port, username, password,
                    private_key, private_key_path, labels,
                    connect_timeout, command_timeout
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    namespace_id,
                    config.name,
                    config.host,
                    config.port,
                    config.username,
                    config.password,
                    config.private_key,
                    config.private_key_path,
                    labels_json,
                    config.connect_timeout,
                    config.command_timeout,
                ),
            )

            conn.commit()
            return cursor.lastrowid

    def get_server(self, name: str, namespace: str = "default") -> Optional[Host]:
        """获取服务器配置"""
        namespace_id = self._get_namespace_id(namespace)
        if not namespace_id:
            return None

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM servers WHERE namespace_id = ? AND name = ?",
                (namespace_id, name),
            ).fetchone()

            if not row:
                return None

            return self._row_to_server_config(row)

    def list_servers(
        self, namespace: str = "default", name_pattern: str = None
    ) -> List[Host]:
        """列出服务器配置"""
        namespace_id = self._get_namespace_id(namespace)
        if not namespace_id:
            return []

        with self._get_connection() as conn:
            if name_pattern:
                rows = conn.execute(
                    "SELECT * FROM servers WHERE namespace_id = ? AND name LIKE ? ORDER BY name",
                    (namespace_id, f"%{name_pattern}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM servers WHERE namespace_id = ? ORDER BY name",
                    (namespace_id,),
                ).fetchall()

            return [self._row_to_server_config(row) for row in rows]

    def update_server(
        self, name: str, updates: Dict[str, Any], namespace: str = "default"
    ) -> bool:
        """更新服务器配置"""
        namespace_id = self._get_namespace_id(namespace)
        if not namespace_id:
            return False

        server = self.get_server(name, namespace)
        if not server:
            return False

        if "labels" in updates:
            updates["labels"] = json.dumps(updates["labels"] or {})

        # 构建更新SQL
        set_clauses = []
        values = []
        for key, value in updates.items():
            set_clauses.append(f"{key} = ?")
            values.append(value)

        values.append(namespace_id)
        values.append(name)

        with self._get_connection() as conn:
            conn.execute(
                f"""
                UPDATE servers 
                SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
                WHERE namespace_id = ? AND name = ?
            """,
                values,
            )
            conn.commit()

        return True

    def delete_server(self, name: str, namespace: str = "default") -> bool:
        """删除服务器配置"""
        namespace_id = self._get_namespace_id(namespace)
        if not namespace_id:
            return False

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM servers WHERE namespace_id = ? AND name = ?",
                (namespace_id, name),
            )
            conn.commit()
            return cursor.rowcount > 0

    # 服务器组管理方法
    def add_server_group(self, group: ServerGroup, namespace: str = "default") -> int:
        """添加服务器组"""
        namespace_id = self._get_namespace_id(namespace)
        if not namespace_id:
            raise ValueError(f"Namespace '{namespace}' does not exist")

        with self._get_connection() as conn:
            labels_json = json.dumps(group.default_labels or {})

            cursor = conn.execute(
                """
                INSERT INTO server_groups (
                    namespace_id, name, description, ip_expression, label_expression,
                    default_username, default_password,
                    default_private_key, default_private_key_path,
                    default_labels
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    namespace_id,
                    group.name,
                    group.description,
                    group.ip_expression,
                    group.label_expression,
                    group.default_username,
                    group.default_password,
                    group.default_private_key,
                    group.default_private_key_path,
                    labels_json,
                ),
            )

            conn.commit()
            return cursor.lastrowid

    def get_server_group(
        self, name: str, namespace: str = "default"
    ) -> Optional[ServerGroup]:
        """获取服务器组"""
        namespace_id = self._get_namespace_id(namespace)
        if not namespace_id:
            return None

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM server_groups WHERE namespace_id = ? AND name = ?",
                (namespace_id, name),
            ).fetchone()

            if not row:
                return None

            return self._row_to_server_group(row)

    def list_server_groups(
        self, namespace: str = "default", name_pattern: str = None
    ) -> List[ServerGroup]:
        """列出服务器组"""
        namespace_id = self._get_namespace_id(namespace)
        if not namespace_id:
            return []

        with self._get_connection() as conn:
            if name_pattern:
                rows = conn.execute(
                    "SELECT * FROM server_groups WHERE namespace_id = ? AND name LIKE ? ORDER BY name",
                    (namespace_id, f"%{name_pattern}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM server_groups WHERE namespace_id = ? ORDER BY name",
                    (namespace_id,),
                ).fetchall()

            return [self._row_to_server_group(row) for row in rows]

    def delete_server_group(self, name: str, namespace: str = "default") -> bool:
        """删除服务器组"""
        namespace_id = self._get_namespace_id(namespace)
        if not namespace_id:
            return False

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM server_groups WHERE namespace_id = ? AND name = ?",
                (namespace_id, name),
            )
            conn.commit()
            return cursor.rowcount > 0

    # 辅助方法
    def _row_to_server_config(self, row) -> Host:
        """数据库行转换为服务器配置"""
        labels = json.loads(row["labels"] or "{}")

        return Host(
            name=row["name"],
            host=row["host"],
            port=row["port"],
            username=row["username"],
            password=row["password"],  # 直接读取明文
            private_key=row["private_key"],  # 直接读取明文
            private_key_path=row["private_key_path"],
            labels=labels,
            connect_timeout=row["connect_timeout"],
            command_timeout=row["command_timeout"],
        )

    def _row_to_server_group(self, row) -> ServerGroup:
        """数据库行转换为服务器组"""
        default_labels = json.loads(row["default_labels"] or "{}")

        return ServerGroup(
            name=row["name"],
            description=row["description"],
            ip_expression=row["ip_expression"],
            label_expression=row["label_expression"],
            default_username=row["default_username"],
            default_password=row["default_password"],  # 直接读取明文
            default_private_key=row["default_private_key"],  # 直接读取明文
            default_private_key_path=row["default_private_key_path"],
            default_labels=default_labels,
        )

    # 导入导出方法
    def export_config(
        self, output_file: Path, format: str = "yaml", namespace: str = None
    ) -> None:
        """导出配置"""
        if namespace:
            # 导出特定命名空间
            servers = self.list_servers(namespace)
            groups = self.list_server_groups(namespace)
            namespace_info = self.get_namespace(namespace)

            data = {
                "namespace": namespace_info,
                "servers": [asdict(server) for server in servers],
                "groups": [asdict(group) for group in groups],
            }
        else:
            # 导出所有命名空间
            namespaces = self.list_namespaces()
            data = {"namespaces": namespaces, "servers": [], "groups": []}

            for ns in namespaces:
                ns_name = ns["name"]
                servers = self.list_servers(ns_name)
                groups = self.list_server_groups(ns_name)

                data["servers"].extend(
                    [{**asdict(server), "namespace": ns_name} for server in servers]
                )
                data["groups"].extend(
                    [{**asdict(group), "namespace": ns_name} for group in groups]
                )

        with open(output_file, "w") as f:
            if format.lower() == "json":
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:  # yaml
                yaml.dump(data, f, indent=2, allow_unicode=True)

    def import_config(self, input_file: Path, namespace: str = None) -> None:
        """导入配置"""
        with open(input_file, "r") as f:
            if input_file.suffix.lower() == ".json":
                data = json.load(f)
            else:  # yaml
                data = yaml.safe_load(f)

        # 处理命名空间
        if "namespace" in data:
            # 单个命名空间导入
            ns_data = data["namespace"]
            ns_name = ns_data["name"]

            # 创建命名空间（如果不存在）
            if not self.get_namespace(ns_name):
                self.create_namespace(ns_name, ns_data.get("description"))

            # 导入服务器配置
            for server_data in data.get("servers", []):
                server = Host(
                    **{k: v for k, v in server_data.items() if k != "namespace"}
                )
                try:
                    self.add_server(server, ns_name)
                except Exception as e:
                    print(
                        f"Failed to import server {server.name} in namespace {ns_name}: {e}"
                    )

            # 导入服务器组
            for group_data in data.get("groups", []):
                group = ServerGroup(
                    **{k: v for k, v in group_data.items() if k != "namespace"}
                )
                try:
                    self.add_server_group(group, ns_name)
                except Exception as e:
                    print(
                        f"Failed to import group {group.name} in namespace {ns_name}: {e}"
                    )

        elif "namespaces" in data:
            # 多命名空间导入
            for ns_data in data["namespaces"]:
                ns_name = ns_data["name"]

                # 创建命名空间（如果不存在）
                if not self.get_namespace(ns_name):
                    self.create_namespace(ns_name, ns_data.get("description"))

            # 导入服务器配置
            for server_data in data.get("servers", []):
                ns_name = server_data.get("namespace", "default")
                server = Host(
                    **{k: v for k, v in server_data.items() if k != "namespace"}
                )
                try:
                    self.add_server(server, ns_name)
                except Exception as e:
                    print(
                        f"Failed to import server {server.name} in namespace {ns_name}: {e}"
                    )

            # 导入服务器组
            for group_data in data.get("groups", []):
                ns_name = group_data.get("namespace", "default")
                group = ServerGroup(
                    **{k: v for k, v in group_data.items() if k != "namespace"}
                )
                try:
                    self.add_server_group(group, ns_name)
                except Exception as e:
                    print(
                        f"Failed to import group {group.name} in namespace {ns_name}: {e}"
                    )
