## pypssh
`pypssh` 命令行程序是一款简易易用的 ssh 批处理工具，它支持直接通过命令行或者配置文件的方式对多台主机进行操作。

## 用户指南
`pypssh` 的大多数帮助文档或示例都可以通过 `--help` 进行获取，所以这里仅对 `pypssh` 做一个简单的介绍。

### 关于基本使用
```bash
# 首先通过以下命令创建一个的配置文件
pypssh config dump-default
# 或者根据老式配置文件转换为新式配置文件
pypssh config convert config/old_inventory.conf  > /root/.pypssh/inventory/inventory.yaml
# 选择特定主机执行命令
pypssh -t 192.168.1.100 execute -e NAME=peter 'echo hello $NAME'
# 根据主机切片表达式选择配置中存在的主机
pypssh -t 192.168.3[2:90].10[5:9] ls
# 根据主机切片和逗号表达式选择配置中存在的主机
pypssh -t 192.168.32.1[5:9,32,35,38] ls
# 根据标签选择特定主机上传文件
pypssh -t master put [localfile] [remotefile]
# 根据简单的标签表达式获取文件
pypssh -t mysql==master get [remotefile] [localdir]
# 根据复杂的标签表达式执行脚本
pypssh -t 'ds01 and (redis==master or mysql)' execfile test.py
```

但对于中大规模的主机数量而言，没有配置文件不便于管理，所以 `pypssh` 提供配置的方式建立会话进行操作。配置文件为了便于解析和扩展我们采用了数据类对象转储的形式进行存储，数据类对象可以转储为 `json`，`yaml` 等格式。配置文件内容示例如下：

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

~~我们可以通过 命令行操作 或者 手动编写 两种形式进行配置。 【未实现】~~  
命令行的配置方式：
```bash
# 添加主机 192.168.1.100 并且为该主机设置账户密码以及端口和标签 test1 和 test2
pypssh config add-host 192.168.1.100 -u root -p 'root$123' -P 22 -t test1=x1 -t test2=x2
# 删除主机 192.168.1.100
pypssh config del-host 192.168.1.100
# 删除包含 test 标签，并且 ip 为 192.168.1.100 的主机
pypssh config del-host 192.168.1.100 -t test
```

### 关于能力
`pypssh` 提供以下子命令：
- config：提供配置的命令行接口
- execute：批量远程执行命令
- put：批量上传文件
- get：批量下载文件
- test：测试 ssh 是否可用
- execfile：将脚本上传到远程并执行
- version：版本/发行信息

## pypssh 开发者指南
### 基本介绍和约定
该项目主要基于以下依赖：  
- concurrent(python3自带): 为子命令提供并发支持；
- paramiko/scp: 提供 ssh/scp 客户端支持；
- jinja2: 提供输出命令结果时的模版渲染支持；
- yaml: 提供输出命令结果时的 yaml 格式支持；
- marshmallow_dataclass: 提供对数据类转dict的支持;
- click: 提供 cli 支持；
- PyYAML: 提供 yaml 配置文件解析支持；
- PyInstaller: 提供二进制程序发布支持； 
开发时依赖如下：
- altgraph: alt 模块调试
- autopep8: 代码格式化
- PyInstaller：二进制打包

约定：
- import 语句按照以下规范编写：
  - 内置包排在依赖包前面
  - 包名短的排在长的前面
  - import ... 排在 from ... import 前面
- 默认使用 `~/.pypssh/` 作为数据目录存放自己的数据和配置文件。
- 所有子命令的输出暂时都使用 `click.echo(yaml.dump({{result}}, allow_unicode=True))` 的形式，这样既能保证人类可读也便于其它程序调用和解析，之后再使用模板封装输出函数。
- 任务函数中使用 `get_ssh_logger(host)` 获取日志实例，这样能在每条日志头部打印主机名。

### 开发计划

#### 功能
- 新增 `config` 子命令，用于加载，生成和修改配置文件。
- 编写根据标签表达式选择主机实体的解析器。

#### 优化

### 开发者参考
[ssh-protocol - SSH.COM](https://www.ssh.com/academy/ssh/protocol)
[tenacity document](https://tenacity.readthedocs.io/en/latest/index.html)
[click document](https://click.palletsprojects.com/en/7.x/)