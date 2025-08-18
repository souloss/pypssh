# pypssh
[![Language](https://img.shields.io/badge/Language-Python-blue.svg)](https://www.python.org/)
[![Github Workflow Status](https://img.shields.io/github/workflow/status/souloss/pypssh/pypsshci)](https://github.com/souloss/pypssh/actions/workflows/pypsshci.yml)
[![Version](https://img.shields.io/github/v/release/souloss/pypssh?include_prereleases)](https://github.com/souloss/pypssh/releases)
[![LICENSE](https://img.shields.io/github/license/souloss/pypssh)](LICENSE)

[![Github issues](https://img.shields.io/github/issues/souloss/pypssh)](https://github.com/souloss/pypssh/issues)
[![Github forks](https://img.shields.io/github/forks/souloss/pypssh)](https://github.com/souloss/pypssh/network/members)
[![Github stars](https://img.shields.io/github/stars/souloss/pypssh)](https://github.com/souloss/pypssh/stargazers)
![Page Views](https://views.whatilearened.today/views/github/souloss/pypssh.svg)
[![Release Download Total](https://img.shields.io/github/downloads/souloss/pypssh/total)](https://github.com/souloss/pypssh/releases)

> **PyPSSH** 是一个功能强大、易于使用的并行 SSH 客户端，专为大规模服务器管理而设计。它支持命令批量执行、文件并行传输、连通性测试、标签化主机选择、命名空间隔离等特性，帮助运维工程师大幅提升工作效率。

--- 

- [中文](./README_zh-CN.md).
- [English](./README.md)

## ✨ 核心特性

| 特性 | 描述 |
|---|---|
| 🚀 **并行执行** | 支持数千台服务器并行命令执行与文件传输 |
| 🎯 **智能选择** | 通过 IP 表达式、标签表达式、服务器组灵活选择目标主机 |
| 🔐 **命名空间** | 多环境（测试、预发、生产）配置隔离 |
| 🖥️ **交互友好** | 彩色进度条、实时输出、失败详情 |
| 📦 **格式丰富** | 支持 JSON / YAML / 模板化 / 静默输出 |
| 🔧 **易于扩展** | 模块化设计，方便二次开发 |


## 🏁 快速开始
### 1. 安装
可以从 [GitHub 发布页面](https://github.com/souloss/pypssh/releases) 下载适用于 CentOS 8(主要依赖于高版本的GLIBC) 的预构建二进制文件。  
您也可以通过编译安装 `pypssh`：
```bash
$ git clone  https://github.com/souloss/pypssh 
$ cd pypssh
$ uv sync
$ ./script/build/package_exec # 使用 pyinstaller 构建单个二进制文件
$ ./dist/pypssh --version
```

### 2. 添加一台服务器
```bash
pypssh config add-server 192.168.1.10 \
  --name web1 \
  --username root \
  --password 123456 \
  --label env=prod,role=web
```
### 3. 批量执行命令
```bash
pypssh exec --hosts "192.168.1.0/24" --sudo "systemctl restart nginx"
```

### 4. 上传文件
```bash
pypssh file upload ./dist.tar.gz /opt/web/ \
  --group web-servers \
  --recursive \
  --preserve
```

### 5. 连通性测试
```bash
pypssh ping --selector "env=prod" --max-concurrent 100
```

## 📖 详细使用指南
### 1. 配置管理
```bash
# 创建命名空间
pypssh config create-namespace prod --description "Production Environment"

# 查看命名空间
pypssh config list-namespaces

# 删除命名空间
pypssh config delete-namespace test --force
```

### 2. 添加服务器
```bash
# 添加
pypssh config add-server 10.0.0.21 --name db1 --username ubuntu --private-key-path ~/.ssh/id_rsa

# 查看
pypssh config list-servers --namespace prod

# 更新
pypssh config update-server web1 --add-label region=us-east-1 --remove-label temp=true

# 删除
pypssh config delete-server web1 --force
```

### 3. 服务器组
```bash
# 创建
pypssh config add-group web-servers \
  --description "All web nodes" \
  --ip-expression "192.168.1.[10:50]" \
  --label-expression "role=web" \
  --default-username deploy

# 使用
pypssh exec --group web-servers "uptime"
```

### 4. 命令执行
| 选项                 | 示例值                             | 说明      |
| ------------------ | ------------------------------- | ------- |
| `--hosts`          | `192.168.1.0/24,!192.168.1.100` | IP 表达式  |
| `--selector`       | `env=prod,role=web`             | 标签表达式   |
| `--group`          | `web-servers`                   | 服务器组    |
| `--server`         | `web1`                          | 指定单个服务器 |
| `--max-concurrent` | `100`                           | 并发数     |
| `--timeout`        | `30`                            | 命令超时    |
| `--output`         | `json`                          | 输出格式    |
| `--template`       | `"${host}: ${stdout}"`          | 自定义模板   |

```bash
pypssh exec \
  --namespace prod \
  --selector "env=prod,role=web,!maintenance" \
  --sudo \
  --output json \
  --output-file results.json \
  "apt update && apt upgrade -y"
```

## 🗂️ 配置导入导出
```bash
# 导出单个命名空间
pypssh config export prod.yml --namespace prod

# 导出全部
pypssh config export all.yml

# 导入
pypssh config import prod.yml --namespace prod
```

## ⚙️ IP & 标签表达式语法
### IP 表达式
| 示例                              | 说明   |
| ------------------------------- | ---- |
| `192.168.1.10`                  | 单 IP |
| `192.168.1.0/24`                | CIDR |
| `192.168.1.10-192.168.1.20`     | 连续范围 |
| `192.168.1.10,192.168.1.15`     | 列表   |
| `192.168.1.0/24 !192.168.1.100` | 排除   |
| `192.168.[1:3].[10:20]`         | 字段范围 |

### 标签表达式
| 示例                            | 说明   |
| ----------------------------- | ---- |
| `env=prod`                    | 等于   |
| `role!=db`                    | 不等于  |
| `env in (prod,staging)`       | 包含   |
| `region notin (cn-north-1)`   | 不包含  |
| `has(sshd)`                   | 存在标签 |
| `count(disk) > 2`             | 计数比较 |
| `startswith(hostname, "web")` | 前缀匹配 |
| `regex(hostname, "web-\d+")`  | 正则匹配 |


### 参考文档
[ssh-protocol - SSH.COM](https://www.ssh.com/academy/ssh/protocol)  
[tenacity document](https://tenacity.readthedocs.io/en/latest/index.html)  
[click document](https://click.palletsprojects.com/en/7.x/)  


## 许可证
这个项目是在 MIT 许可证下的。有关完整的许可证文本，请参阅 [LICENSE](./LICENSE) 文件。

## 感谢
- [shields](img.shields.io): 提供了精美的标签
- [axiom](repobeats.axiom.co): 提供了精美的仓库分析图
- [ipcalc](https://jodies.de/ipcalc)