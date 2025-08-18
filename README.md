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


> **PyPSSH** is a powerful and easy-to-use parallel SSH client designed for large-scale server management. It supports features such as batch command execution, parallel file transfer, connectivity testing, labeled host selection, and namespace isolation, helping operations engineers significantly improve work efficiency.  
--- 
- [Chinese](./README_zh-CN.md).
- [English](./README.md)
## ✨ Core Features
| Feature | Description |
|---|---|
| 🚀 **Parallel Execution** | Supports parallel command execution and file transfer across thousands of servers |
| 🎯 **Smart Selection** | Flexibly select target hosts through IP expressions, label expressions, and server groups |
| 🔐 **Namespaces** | Configuration isolation for multiple environments (testing, staging, production) |
| 🖥️ **User-Friendly Interface** | Colored progress bars, real-time output, failure details |
| 📦 **Rich Output Formats** | Supports JSON / YAML / templated / silent output |
| 🔧 **Easy to Extend** | Modular design, convenient for secondary development |

## 🏁 Quick Start
### 1. Installation
You can download pre-built binaries for CentOS 8 (mainly depends on a higher version of GLIBC) from the [GitHub releases page](https://github.com/souloss/pypssh/releases).  
You can also install `pypssh` by compiling:
```bash
$ git clone  https://github.com/souloss/pypssh    
$ cd pypssh
$ uv sync
$ ./script/build/package_exec # Build a single binary using pyinstaller
$ ./dist/pypssh --version
```


### 2. Add a Server
```bash
pypssh config add-server 192.168.1.10 \
  --name web1 \
  --username root \
  --password 123456 \
  --label env=prod,role=web
```
### 3. Bulk Command Execution
```bash
pypssh exec --hosts "192.168.1.0/24" --sudo "systemctl restart nginx"
```

### 4. Upload Files
```bash
pypssh file upload ./dist.tar.gz /opt/web/ \
  --group web-servers \
  --recursive \
  --preserve
```

### 5. Connectivity Test
```bash
pypssh ping --selector "env=prod" --max-concurrent 100
```

## 📖 Detailed Usage Guide
### 1.Configuration Management
```bash
# Create a namespace
pypssh config create-namespace prod --description "Production Environment"

# List namespaces
pypssh config list-namespaces

# Delete a namespace
pypssh config delete-namespace test --force
```

### 2. Server Groups
```bash
# Add
pypssh config add-server 10.0.0.21 --name db1 --username ubuntu --private-key-path ~/.ssh/id_rsa

# List
pypssh config list-servers --namespace prod

# Update
pypssh config update-server web1 --add-label region=us-east-1 --remove-label temp=true

# Delete
pypssh config delete-server web1 --force
```

### 3. Server Groups
```bash
# Create
pypssh config add-group web-servers \
  --description "All web nodes" \
  --ip-expression "192.168.1.[10:50]" \
  --label-expression "role=web" \
  --default-username deploy

# Use
pypssh exec --group web-servers "uptime"
```

### 4.Command Execution
| Option             | Example                         | Description       |
| ------------------ | ------------------------------- | ----------------- |
| `--hosts`          | `192.168.1.0/24,!192.168.1.100` | IP expression     |
| `--selector`       | `env=prod,role=web`             | Label expression  |
| `--group`          | `web-servers`                   | Server group      |
| `--server`         | `web1`                          | Single server     |
| `--max-concurrent` | `100`                           | Concurrency level |
| `--timeout`        | `30`                            | Command timeout   |
| `--output`         | `json`                          | Output format     |
| `--template`       | `"${host}: ${stdout}"`          | Custom template   |


```bash
pypssh exec \
  --namespace prod \
  --selector "env=prod,role=web,!maintenance" \
  --sudo \
  --output json \
  --output-file results.json \
  "apt update && apt upgrade -y"
```

## 🗂️ Import & Export Configurations
```bash
# Export one namespace
pypssh config export prod.yml --namespace prod

# Export all
pypssh config export all.yml

# Import
pypssh config import prod.yml --namespace prod  
```

## ⚙️ IP & Label Expression Syntax
### IP Expressions
| Example                         | Description |
| ------------------------------- | ----------- |
| `192.168.1.10`                  | Single IP   |
| `192.168.1.0/24`                | CIDR        |
| `192.168.1.10-192.168.1.20`     | Range       |
| `192.168.1.10,192.168.1.15`     | List        |
| `192.168.1.0/24 !192.168.1.100` | Exclude     |
| `192.168.[1:3].[10:20]`         | Field range |


### Label Expressions
| Example                       | Description      |
| ----------------------------- | ---------------- |
| `env=prod`                    | Equals           |
| `role!=db`                    | Not equals       |
| `env in (prod,staging)`       | Inclusion        |
| `region notin (cn-north-1)`   | Exclusion        |
| `has(sshd)`                   | Tag existence    |
| `count(disk) > 2`             | Count comparison |
| `startswith(hostname, "web")` | Prefix match     |
| `regex(hostname, "web-\d+")`  | Regex match      |



### References
[ssh-protocol - SSH.COM](https://www.ssh.com/academy/ssh/protocol)  
[tenacity document](https://tenacity.readthedocs.io/en/latest/index.html)  
[click document](https://click.palletsprojects.com/en/7.x/)  


## License
This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for the full license text.

## Acknowledgments
- [shields](img.shields.io): for beautiful badges
- [axiom](repobeats.axiom.co): for awesome repo analytics
- [ipcalc](https://jodies.de/ipcalc)