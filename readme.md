## pypssh
`pypssh` 命令行程序是一款简易易用的 ssh 批处理工具，它支持直接通过命令行或者配置文件的方式对多台主机进行操作。

## 用户指南
`pypssh` 的大多数帮助文档或示例都可以通过 `--help` 进行获取，所以这里仅对 `pypssh` 做一个简单的介绍。

### 关于基本使用
```bash
# 选择特定主机执行命令
pypssh 192.168.1.100 execute -e NAME=peter 'echo hello $NAME'
# 根据标签选择特定主机上传文件
pypssh master put [localfile] [remotefile]
# 根据简单的标签表达式获取文件
pypssh mysql==master get [remotefile] [localdir]
# 根据复杂的标签表达式执行脚本
pypssh ds01&&(redis==master||mysql==master) execfile test.py
```

但对于中大规模的主机数量而言，没有配置文件不便于管理，所以 `pypssh` 提供配置的方式建立会话进行操作。配置文件为了便于解析和扩展我们采用了数据类对象转储的形式进行存储，数据类对象可以转储为 `json`，`yaml` 等格式。配置文件内容示例如下：

```yaml
192.168.31.133:
  port: 22
  username: mysql
  # echo -n 'mysql$123' | base64
  # echo -n 'bXlzcWwkMTIz' | base64 -d
  password: bXlzcWwkMTIz
  tags:
    mysql: master
192.168.31.134:
  port: 22
  username: mysql
  # echo -n 'mysql$123' | base64
  # echo -n 'bXlzcWwkMTIz' | base64 -d
  password: bXlzcWwkMTIz
  tags:
    mysql: master
192.[22:26].[95:99].[95:99]:
  port: 22
  username: mysql
  pkfile: "/root/.ssh/id_rsa"
  pkpasswd: ""
  sudo: false
  tags:
    mysql: master
```

我们可以通过 命令行操作 或者 手动编写 两种形式进行配置。
命令行的配置方式：
```bash
# 添加主机 192.168.1.100 并且为该主机设置账户密码以及端口和标签 test1 和 test2
pypssh config add-host 192.168.1.100 -u root -p 'root$123' -P 22 -t test1=x1 -t test2=x2
# 删除主机 192.168.1.100
pypssh config del-host 192.168.1.100
# 删除包含 test 标签，并且 ip 为 192.168.1.100 的主机
pypssh config del-host 192.168.1.100 -t test

# 加载特殊格式的配置文件，该子命令使得 pypssh 支持多种格式的配置文件
# -p 默认值，加载普通格式的主机清单到配置中，普通格式主机清单每一项以换行符分割，每项格式为 hostname:[sshPort]:[sshUser]:[sshPassword]:[group1]:[group2]....
# -o 加载老版本 pypssh 配置文件的
# ....
pypssh config load -o inventory.conf >> oldds.yaml
# 合并配置文件
pypssh config merge ds1.yaml ds2.yaml >> ds3.yaml
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
- paramiko: 提供 ssh 客户端支持；
- click: 提供 cli 支持；
- PyYAML: 提供 yaml 配置文件解析支持；
- PyInstaller: 提供二进制程序发布支持； 
- concurrent(python3自带): 为子命令提供并发支持；

约定：
- 它默认使用 `~/.pypssh/` 作为数据目录存放自己的数据和配置文件。
- 所有子命令的输出都使用 `click.echo(yaml.dump({{result}}}))` 的形式，这样既能保证人类可读也便于其它程序调用和解析。
- 

### 开发计划

#### 功能

#### 优化
### 开发者参考
[click文档](https://click.palletsprojects.com/en/7.x/)