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

pypssh is a high-performance and user friendly ssh tool. It can efficiently execute commands, execute script files, and transfer files. 

- [中文](./README_zh-CN.md).
- [English](./README.md)

## Features
- Supports four common usages of ssh：
  - `execute`: remote execute single-line commands.
  - `execfile`: remote execution of local scripts;
  - `put`: upload of files;
  - `get`: downloaded of files;
- Supports `sudo`.
- Support to declare multiple hosts in the configuration file by means of lists and slices.
- Support host selection based on host name, label, label logical expression.
- Supports jinja2 template redefinition the output of all subcommands on selected host.
- Support port test and ssh connection test on selected host.

## Installation
You can download pre-built binaries for CentOS 8 (mainly dependent on higher versions of GLIBC) from [GitHub Release Page](https://github.com/witchc/pypssh/releases).

It can also be install `pypssh` by compiling：
```bash
$ git clone  https://github.com/witchc/pypssh 
$ cd pypssh
$ python3 -m venv .venv  # requires python 3.7 or higher
$ source .venv/bin/activate
$ pip install -r requirement.txt
$ ./script/build/package_exec # used pyinstaller build single binary file.
$ ./dist/pypssh --version
```

## Usage
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

# create a default configuration file
$ pypssh config dump-default
# or according to the old version of the configuration conversion to the new version of the configuration file
$ pypssh config convert config/old_inventory.conf  > /root/.pypssh/inventory/inventory.yaml

# use -t to select the host to execute the command
$ pypssh -t 192.168.1.100 execute -e NAME=peter 'echo hello $NAME'

# use -t to select host slices and list the hosts in the configuration
$ pypssh -t 192.168.3[2:90].10[5:9] ls

# use -t to select the host slice with a list and list the hosts in the configuration
$ pypssh -t 192.168.32.1[5:9,32,35,38] ls

# use -t to select the host with the master tag to upload files
$ pypssh -t master put [localfile] [remotefile]

# use -t to select the host with the mysql==master tag to upload files
$ pypssh -t mysql==master get [remotefile] [localdir]

# use -t to select the host where the complex label expression evaluates to True to upload files
$ pypssh -t 'ds01 and (redis==master or mysql)' execfile test.py
```

## Configure
Sample configuration：  
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
# 192.168.31.[21,22,23,24,28,29]
192.168.31.2[1:5,8,9]:
  port: 22
  username: mysql
  pkfile: "/root/.ssh/id_rsa"
  pkpasswd: ""
  sudo: false
  tags:
    mysql: master
```

## pypssh developer
### dependency
runtime dependency：  
- paramiko/scp: Provide ssh/scp client support.
- jinja2: Provide template rendering support when outputting command results.
- marshmallow_dataclass: Provide support for dataclass conversion to dict;
- click: Provide cli support.
- PyYAML: Provide yaml configuration file parsing support.
- tenacity: Provide retry support.

development dependency：
- altgraph: Provide alt module debugging support.
- autopep8: Provide code formatting support.
- PyInstaller：Provide binary program release support.

### Promise
- The import statement is written in accordance with the following specifications：
  - Built-in packages are listed in front of dependent packages.
  - The short package name comes before the long.
  - `import ...` comes before `from ... import`
- By default, `~/.pypssh/` is used as the data directory to store its own data and configuration files.
- The output of the subcommand uses `echo(output_mode:str, cls, datas, template)` or `click.echo(yaml.dump({{result}}, allow_unicode=True))`.
- Use `get_ssh_logger(host)` in the ssh task function to get the log instance, so that the host name can be printed in the header of each log.

### Reference
[ssh-protocol - SSH.COM](https://www.ssh.com/academy/ssh/protocol)  
[tenacity document](https://tenacity.readthedocs.io/en/latest/index.html)  
[click document](https://click.palletsprojects.com/en/7.x/)  


## License
This project is under the MIT License. See the [LICENSE](./LICENSE)  file for the full license text.

## Thanks
- [shields](img.shields.io): provides a beautiful badge.
- [axiom](repobeats.axiom.co): provides a beautiful analysis image.
