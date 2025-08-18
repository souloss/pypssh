import os
import socket
import threading
import paramiko
from paramiko import ServerInterface, SFTPServer, SFTPServerInterface, Transport
from paramiko.sftp_si import SFTPServerInterface
from paramiko.sftp_si import SFTPServerInterface
from io import BytesIO
import traceback


# 模拟文件系统
class MockFileSystem:
    def __init__(self):
        self.files = {
            "/": {"type": "dir", "content": {}},
            "/tmp": {"type": "dir", "content": {}},
            "/home": {"type": "dir", "content": {}},
        }

    def exists(self, path):
        return path in self.files

    def isdir(self, path):
        return self.files.get(path, {}).get("type") == "dir"

    def isfile(self, path):
        return self.files.get(path, {}).get("type") == "file"

    def mkdir(self, path):
        parent = os.path.dirname(path)
        if parent not in self.files:
            self.mkdir(parent)
        self.files[path] = {"type": "dir", "content": {}}

    def listdir(self, path):
        if not self.isdir(path):
            return []
        return [name for name in self.files[path]["content"]]

    def open(self, path, mode="r"):
        if "w" in mode or "a" in mode:
            if not self.exists(path):
                parent = os.path.dirname(path)
                if parent and not self.exists(parent):
                    self.mkdir(parent)
                self.files[path] = {"type": "file", "content": BytesIO()}
            return self.files[path]["content"]
        else:
            if not self.exists(path):
                raise FileNotFoundError(path)
            return self.files[path]["content"]


# 模拟SFTP服务器（保持不变）
class MockSFTP(SFTPServerInterface):
    def __init__(self, server, *args, **kwargs):
        self.server = server
        self.fs = server.fs
        super().__init__(*args, **kwargs)

    def list_folder(self, path):
        path = self._canonicalize(path)
        if not self.fs.isdir(path):
            return paramiko.SFTP_NO_SUCH_FILE
        return [
            paramiko.SFTPAttributes.from_stat(
                fstat=os.stat_result((0, 0, 0, 0, 0, 0, 0, 0, 0, 0)), filename=name
            )
            for name in self.fs.listdir(path)
        ]

    def stat(self, path):
        path = self._canonicalize(path)
        if not self.fs.exists(path):
            return paramiko.SFTP_NO_SUCH_FILE
        return paramiko.SFTPAttributes.from_stat(
            fstat=os.stat_result((0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        )

    def open(self, path, flags, attr):
        path = self._canonicalize(path)
        if flags & os.O_WRONLY:
            return MockHandle(self.fs.open(path, "wb"), path)
        else:
            return MockHandle(self.fs.open(path, "rb"), path)


class MockHandle:
    def __init__(self, file, path):
        self.file = file
        self.path = path

    def read(self, size):
        return self.file.read(size)

    def write(self, data):
        return self.file.write(data)

    def close(self):
        return self.file.close()

    def stat(self):
        return paramiko.SFTPAttributes.from_stat(
            fstat=os.stat_result((0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        )


# 扩展的Mock SSH服务器（添加PTY和shell支持）
class MockSSHServer(ServerInterface):
    def __init__(self, credentials, commands, fs):
        self.credentials = credentials  # {username: password}
        self.commands = commands  # 预定义的命令和响应
        self.fs = fs  # 文件系统
        self.shell_active = False  # shell会话状态

    def check_auth_password(self, username, password):
        if username in self.credentials and self.credentials[username] == password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    # 新增：处理PTY请求
    def check_channel_pty_request(
        self, channel, term, width, height, pixelwidth, pixelheight, modes
    ):
        print(f"PTY request: term={term}, width={width}, height={height}")
        return True

    # 新增：处理shell请求
    def check_channel_shell_request(self, channel):
        print("Shell request received")
        self.shell_active = True
        # 启动一个线程来处理shell会话
        threading.Thread(target=self.handle_shell, args=(channel,), daemon=True).start()
        return True

    # 新增：处理shell会话
    def handle_shell(self, channel):
        try:
            # 发送欢迎信息
            channel.send("Welcome to Mock SSH Server!\n")
            channel.send("This is a simulated shell environment.\n")
            channel.send("Available commands: ls, whoami, pwd, date, exit\n")
            channel.send("$ ")

            while self.shell_active and not channel.closed:
                # 读取用户输入
                command = ""
                while not command.endswith("\r") and not command.endswith("\n"):
                    chunk = channel.recv(1024)
                    if not chunk:
                        break
                    command += chunk.decode("utf-8")

                # 处理命令
                command = command.strip()
                if command == "exit":
                    channel.send("Goodbye!\n")
                    channel.send_exit_status(0)
                    self.shell_active = False
                    break

                # 执行命令并返回结果
                if command in self.commands:
                    response = self.commands[command]
                elif command.startswith("echo "):
                    response = command[5:] + "\n"
                elif not command:
                    response = ""
                else:
                    response = f"Command not found: {command}\n"

                if response:
                    channel.send(response)

                # 发送新的提示符
                if self.shell_active:
                    channel.send("$ ")

        except Exception as e:
            print(f"Shell error: {e}")
            traceback.print_exc()
        finally:
            channel.close()

    def check_channel_subsystem_request(self, channel, name):
        if name == "sftp":
            transport = channel.get_transport()
            transport.set_subsystem_handler("sftp", SFTPServer, sftp_si=MockSFTP(self))
            return True
        return False

    def check_channel_exec_request(self, channel, command):
        # 处理命令执行
        command_str = command.decode("utf-8")
        print(f"Exec request: {command_str}")

        if command_str in self.commands:
            response = self.commands[command_str]
        elif command_str.startswith("echo "):
            response = command_str[5:] + "\n"
        else:
            response = f"Command executed: {command_str}\n"

        channel.send(response)
        channel.send_exit_status(0)
        return True


def start_mock_server(port, credentials, commands):
    try:
        fs = MockFileSystem()
        server = MockSSHServer(credentials, commands, fs)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.listen(100)

        print(f"Mock SSH server started on port {port}")

        while True:
            try:
                client, addr = sock.accept()
                print(f"Connection from {addr}")
                transport = Transport(client)
                transport.add_server_key(paramiko.RSAKey.generate(2048))
                transport.start_server(server=server)
            except Exception as e:
                print(f"Error handling connection: {e}")
                traceback.print_exc()
    except Exception as e:
        print(f"Failed to start server on port {port}: {e}")
        traceback.print_exc()


# 定义不同服务器的认证信息和命令响应
server_configs = [
    {
        "port": 3000,
        "credentials": {"admin": "admin123", "user": "user123"},
        "commands": {
            "ls": "file1.txt\nfile2.txt\ndir1\ndir2\n",
            "whoami": "admin\n",
            "pwd": "/home/admin\n",
            "date": "Mon Jan 1 12:00:00 UTC 2023\n",
            "exit": "",  # 特殊命令，用于退出shell
        },
    },
    {
        "port": 3001,
        "credentials": {"root": "rootpass", "guest": "guestpass"},
        "commands": {
            "ls": "document.txt\nimage.jpg\n",
            "whoami": "root\n",
            "pwd": "/root\n",
            "uname": "Linux\n",
            "exit": "",
        },
    },
    # 可以添加更多服务器配置...
]

# 启动所有Mock SSH服务器
threads = []
for config in server_configs:
    thread = threading.Thread(
        target=start_mock_server,
        args=(config["port"], config["credentials"], config["commands"]),
    )
    thread.daemon = True  # 设置为守护线程，主线程退出时自动结束
    thread.start()
    threads.append(thread)
    print(f"Started thread for port {config['port']}")

# 保持主线程运行
try:
    for thread in threads:
        thread.join()
except KeyboardInterrupt:
    print("Shutting down servers...")
