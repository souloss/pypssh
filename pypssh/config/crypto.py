import os
import base64
from typing import Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import keyring
import getpass

Bytes = bytes


class ConfigCrypto:
    """配置加密解密管理器"""

    def __init__(self, password: str = None):
        self.password = password
        self._fernet = None
        self._init_encryption()

    def _init_encryption(self):
        """初始化加密器"""
        if not self.password:
            # 尝试从系统keyring获取密码
            stored_password = keyring.get_password("pypssh", "config_password")
            if stored_password:
                self.password = stored_password
            else:
                # 首次使用，要求设置密码
                self.password = getpass.getpass(
                    "Set password for configuration encryption: "
                )
                confirm_password = getpass.getpass("Confirm password: ")

                if self.password != confirm_password:
                    raise ValueError("Passwords do not match")

                # 保存到系统keyring
                keyring.set_password("pypssh", "config_password", self.password)

        # 生成密钥
        salt = b"pypssh_salt_v1"  # 在生产中应使用随机salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password.encode()))
        self._fernet = Fernet(key)

    def encrypt(self, data: Union[str, Bytes]) -> str:
        """加密数据"""
        if isinstance(data, str):
            data = data.encode("utf-8")

        encrypted = self._fernet.encrypt(data)
        return base64.urlsafe_b64encode(encrypted).decode("utf-8")

    def decrypt(self, encrypted_data: str) -> str:
        """解密数据"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode("utf-8"))
            decrypted = self._fernet.decrypt(encrypted_bytes)
            return decrypted.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {e}")

    @classmethod
    def change_password(cls):
        """更改加密密码"""
        old_password = getpass.getpass("Enter current password: ")
        new_password = getpass.getpass("Enter new password: ")
        confirm_password = getpass.getpass("Confirm new password: ")

        if new_password != confirm_password:
            raise ValueError("New passwords do not match")

        # 验证旧密码并重新加密配置
        old_crypto = cls(old_password)
        new_crypto = cls(new_password)

        # 更新keyring中的密码
        keyring.set_password("pypssh", "config_password", new_password)

        return old_crypto, new_crypto
