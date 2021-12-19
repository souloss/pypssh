# pypssh
[![Language](https://img.shields.io/badge/Language-Python-blue.svg)](https://www.python.org/)
[![Github Workflow Status](https://img.shields.io/github/workflow/status/witchc/pypssh/pypsshci)](https://github.com/witchc/pypssh/actions/workflows/pypsshci.yml)
[![Version](https://img.shields.io/github/v/release/witchc/pypssh?include_prereleases)](https://github.com/witchc/pypssh/releases)
[![LICENSE](https://img.shields.io/github/license/witchc/pypssh)](LICENSE)

[![Github issues](https://img.shields.io/github/issues/witchc/pypssh)](https://github.com/witchc/pypssh/issues)
[![Github forks](https://img.shields.io/github/forks/witchc/pypssh)](https://github.com/witchc/pypssh/network/members)
[![Github stars](https://img.shields.io/github/stars/witchc/pypssh)](https://github.com/witchc/pypssh/stargazers)
![Page Views](https://views.whatilearened.today/views/github/witchc/pypssh.svg)
[![Release Download Total](https://img.shields.io/github/downloads/witchc/pypssh/total)](https://github.com/witchc/pypssh/releases)

pypssh 是一个高性能且用户友好的 ssh 工具，它可以高效地执行命令、执行脚本文件、传输文件等。

- [中文](./README_zh-CN.md).
- [English](./README.md)

## 特征
- 支持 ssh 的四种常见用法：
  - `execute`: 远程执行单行命令;
  - `execfile`: 远程执行本地脚本;
  - `put`: 批量上传文件;
  - `get`: 批量下载文件;
- 支持 `sudo`;
- 支持在配置文件中用列表和切片的方式声明多台主机;
- 支持基于主机名，标签，标签逻辑表达式的主机选择;
- 所有子命令的输出都支持 jinja2 模版重定义;
- 支持对选中的主机进行端口测试，ssh连接测试;

## 安装
可以从 [GitHub 发布页面](https://github.com/witchc/pypssh/releases) 下载适用于 CentOS 8(主要依赖于高版本的GLIBC) 的预构建二进制文件。  
您也可以通过编译安装 `pypssh`：
```bash
$ git clone  https://github.com/witchc/pypssh 
$ cd pypssh
$ python3 -m venv .venv  # 需要 python 3.7
$ source .venv/bin/activate
$ pip install -r requirement.txt
$ ./script/build/package_exec # 使用 pyinstaller 构建单个二进制文件
$ ./dist/pypssh --version
```

## 用法
```bash
$ pypssh --help
Usage: pypssh [OPTIONS] COMMAND [ARGS]...

Options:
  -i, --inventory PATH            inventory.yaml path
  -l, --log-level [NOTSET|DEBUG|INFO|WARN|ERROR|FATAL]
  -t, --target TEXT               Host IP address or label expression
  --help                          Show this message and exit.

Commands:
  config    config management
  execfile  execute script file
  execute   execute command
  key       key management
  ls        list host
  ping      ping hosts
  pull      download file example: pypssh -t 192.168.31.1 put...
  put       upload file example: pypssh -t 192.168.31.1 put /etc/yum.conf...
  version   print version

# 首先通过以下命令创建一个的配置文件
$ pypssh config dump-default
# 或者根据老式配置文件转换为新式配置文件
$ pypssh config convert config/old_inventory.conf  > /root/.pypssh/inventory/inventory.yaml
# 选择特定主机执行命令
$ pypssh -t 192.168.1.100 execute -e NAME=peter 'echo hello $NAME'
# 根据主机切片表达式选择配置中存在的主机
$ pypssh -t 192.168.3[2:90].10[5:9] ls
# 根据主机切片和逗号表达式选择配置中存在的主机
$ pypssh -t 192.168.32.1[5:9,32,35,38] ls
# 根据标签选择特定主机上传文件
$ pypssh -t master put [localfile] [remotefile]
# 根据简单的标签表达式获取文件
$ pypssh -t mysql==master get [remotefile] [localdir]
# 根据复杂的标签表达式执行脚本
$ pypssh -t 'ds01 and (redis==master or mysql)' execfile test.py
```

## 配置
示例配置：  
```yaml
192.168.31.133:
  port: 22
  username: mysql
  password: bXlzcWwkMTIz
  tags:
    mysql: master
# 192.168.31.135 ~ 192.168.31.138
192.168.31.13[5:9]:
  port: 22
  username: mysql
  password: bXlzcWwkMTIz
  tags:
    mysql: master
# 192.(22~25).(95~98).(95~98)
192.[22:26].[95:99].[95:99]:
  port: 22
  username: mysql
  pkfile: "/root/.ssh/id_rsa"
  pkpasswd: ""
  sudo: false
  tags:
    mysql: master
# 相当于 192.168.31.[21,22,23,24,28,29]
192.168.31.2[1:5,8,9]:
  port: 22
  username: mysql
  pkfile: "/root/.ssh/id_rsa"
  pkpasswd: ""
  sudo: false
  tags:
    mysql: master
```

## pypssh 开发者相关
### 依赖
运行时依赖：  
- paramiko/scp: 提供 ssh/scp 客户端支持；
- jinja2: 提供输出命令结果时的模版渲染支持；
- marshmallow_dataclass: 提供对数据类转dict的支持;
- click: 提供 cli 支持；
- PyYAML: 提供 yaml 配置文件解析支持；
- tenacity: 提供重试支持；

开发时依赖：
- altgraph: 提供 alt 模块调试支持。
- autopep8: 提供代码格式化支持。
- PyInstaller：提供二进制程序发布支持。

### 约定
- import 语句按照以下规范编写：
  - 内置包排在依赖包前面
  - 包名短的排在长的前面
  - import ... 排在 from ... import 前面
- 默认使用 `~/.pypssh/` 作为数据目录存放自己的数据和配置文件。
- 所有子命令的输出暂时都使用 `click.echo(yaml.dump({{result}}, allow_unicode=True))` 的形式，这样既能保证人类可读也便于其它程序调用和解析，之后再使用模板封装输出函数。
- 任务函数中使用 `get_ssh_logger(host)` 获取日志实例，这样能在每条日志头部打印主机名。

### 参考文档
[ssh-protocol - SSH.COM](https://www.ssh.com/academy/ssh/protocol)  
[tenacity document](https://tenacity.readthedocs.io/en/latest/index.html)  
[click document](https://click.palletsprojects.com/en/7.x/)  


## 许可证
这个项目是在 MIT 许可证下的。有关完整的许可证文本，请参阅 [LICENSE](./LICENSE) 文件。

## 感谢
- [shields](img.shields.io): 提供了精美的标签
- [axiom](repobeats.axiom.co): 提供了精美的仓库分析图
