#!/bin/env python

import re
import os
import sys
import ast
import time
import socket
import copy
import select
import logging
import platform
import itertools
import functools
import dataclasses

from pathlib import Path
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures._base import as_completed
from typing import Optional, List, Callable, Dict

import yaml
import click
import paramiko
import marshmallow_dataclass

from yaml import Loader
from scp import SCPClient
from jinja2 import Template

ssh_formatter = logging.Formatter(
    fmt=f'%(asctime)s [%(hostname)s][%(levelname)s] %(message)s')
ssh_streamHandler = logging.StreamHandler()
ssh_streamHandler.setFormatter(ssh_formatter)
# logging.basicConfig(level=logging.ERROR,format='%(asctime)s:%(name)s:%(levelname)s:%(message)s')
# logging.basicConfig(level = logging.DEBUG,format = '%(asctime)s:%(name)s:%(levelname)s:%(message)s')
ssh_logger = logging.getLogger("ssh")
ssh_logger.setLevel(logging.INFO)
ssh_logger.removeHandler(ssh_logger.handlers)
ssh_logger.addHandler(ssh_streamHandler)

MAIN_DIR = os.path.join(os.path.expanduser('~'), ".pypssh")
SLICE_PATTERN = "\[(\w*):(\w*)\]"
SLICE_NON_GROUP_PATTERN = "\[\w*:\w*\]"
BANNER_TIMEOUT = 300
TARGET = []


@dataclass
class Host:
    """
    主机类
    """
    hostname: str = "localhost"
    username: str = "root"
    port: int = 22
    password: str = ""
    pkfile: str = ""
    pkpasswd: str = ""
    sudo: bool = False
    timeout: int = 5
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SSHResult:
    hostname: str
    command: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    returncode: int = 0
    exception: Optional[str] = None

@dataclass
class SCPResult:
    hostname: str
    src: str
    dst: str
    completed: bool = False
    exception: Optional[str] = None

class Evaluator(ast.NodeTransformer):

    def __init__(self, data) -> None:
        super().__init__()
        self.data = data

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.operand, ast.Name):
            unaryop = {
                ast.Not: lambda a: not a
            }.get(node.op.__class__)
            return unaryop(node.operand.id in self.data.keys())
        else:
            raise NotImplementedError(
                f"row {node.lineno} col {node.col_offset} error, {type(node.operand).__name__} is an unsupported operation!")

    def visit_Compare(self, node):
        self.generic_visit(node)
        if isinstance(node.left, ast.Name):
            result = False
            lval = self.data.get(node.left.id)
            for op, rnode in zip(node.ops, node.comparators):
                cmpop = {
                    ast.Eq: lambda a, b: a == b,
                    ast.In: lambda a, b: a in b,
                    ast.Is: lambda a, b: a is b,
                    ast.IsNot: lambda a, b: a is not b,
                    ast.NotEq: lambda a, b: a != b,
                    ast.NotIn: lambda a, b: a not in b,
                }.get(op.__class__)
                rval = rnode.id
                if cmpop:
                    result = cmpop(lval, rval)
                    lval = rval
                else:
                    raise NotImplementedError(
                        f"row {node.lineno} col {node.col_offset} error, {type(op).__name__} is an unsupported operation!")
            return ast.Constant(value=result)
        else:
            raise NotImplementedError(
                f"row {node.lineno} col {node.col_offset} error, {type(node.left).__name__} is an unsupported operation!")

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        boolop = {
            ast.And: lambda a, b: a and b,
            ast.Or: lambda a, b: a or b,
        }.get(node.op.__class__)
        return functools.reduce(boolop, [i for i in map(lambda v:v.value, node.values)])

    def eval(self, expr: str):
        tree = ast.parse(expr)
        tree = ast.fix_missing_locations(self.visit(tree))
        if len(tree.body) == 1:
            return tree.body[0].value
        else:
            raise AssertionError(f"{tree.body} eval exception!")


def get_ssh_logger(host: Host):
    return logging.LoggerAdapter(logger=ssh_logger, extra=dataclasses.asdict(host))


def get_ssh_conn_client(host: Host):
    client = paramiko.SSHClient()
    # client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host.hostname,
        username=host.username,
        password=host.password,
        passphrase=host.pkpasswd,
        timeout=host.timeout,
        banner_timeout=BANNER_TIMEOUT,
        key_filename=host.pkfile if host.pkfile else None
    )
    return client


def is_digest_slice(s: str):
    if not re.match(SLICE_PATTERN, s):
        return False
    a, b = s[1:-1].split(":")
    try:
        return re.match("\d+", a).group() == a and re.match("\d+", b).group() == b
    except Exception:
        return False


def is_letter_slice(s: str):
    if not re.match(SLICE_PATTERN, s):
        return False
    a, b = s[1:-1].split(":")
    try:
        return re.match("\w+", a).group() == a and re.match("\w+", b).group() == b
    except Exception:
        return False


def expand_slice(slices: list) -> list:
    slice_tuples = []
    for s in slices:
        slice_list = []
        if is_digest_slice(s):
            s0, s1 = re.match(SLICE_PATTERN, s).groups()
            slice_list = list(range(int(s0), int(s1)))
        elif is_letter_slice(s):
            s0, s1 = re.match(SLICE_PATTERN, s).groups()
            slice_list = [chr(i) for i in range(ord(s0), ord(s1))]
        else:
            raise AssertionError("slice error " + s)
        slice_tuples.append((s, slice_list))
    return slice_tuples

def render_hosts(rd:Dict) -> Dict[str, Host]:
    result = {}
    for key in rd.keys():
        find_slice = re.findall(SLICE_NON_GROUP_PATTERN, rd[key].get('hostname'))
        if find_slice:
            slice_tuples = expand_slice(find_slice)
            combilist = [i for i in itertools.product(
                *[i[1] for i in slice_tuples])]
            for comitem in combilist:
                host = rd[key].get('hostname')
                for index, slice_key in enumerate([i[0] for i in slice_tuples]):
                    host = host.replace(slice_key, str(comitem[index]), 1)
                result[f"{key}-{host}"] = marshmallow_dataclass.class_schema(
                    Host)().load(rd[key])
                result[f"{key}-{host}"].hostname = host
        else:
            result[key] = marshmallow_dataclass.class_schema(
                Host)().load(rd[key])
    return result

# inventory plugins
def fillinghostname_fromkey(rd:Dict):
    result = copy.deepcopy(rd)
    for key in result.keys():
        if not result[key].get('hostname'):
            result[key]['hostname'] = key
    return result
# execute utils


def linesplit(socket):
    buffer_bytes = socket.recv(4048)
    buffer_string = buffer_bytes.decode()
    done = False
    while not done:
        if "\n" in buffer_string:
            (line, buffer_string) = buffer_string.split("\n", 1)
            yield line
        else:
            more = socket.recv(4048)
            if not more:
                done = True
            else:
                buffer_string = buffer_string + more.decode()
    if buffer_string:
        yield buffer_string


def realtime_output(host: Host, command: str):
    client = get_ssh_conn_client(host)
    returncode = 0
    try:
        transport = client.get_transport()
        channel = transport.open_session()
        # 必须获取 pty 才能有机会输入 sudo
        channel.get_pty()
        # 若是非阻塞则强制 recv 时会造成错误
        # channel.setblocking(0)
        channel.exec_command(command)
        lines = []
        if host.sudo:
            while channel.recv_ready() == False:
                stdout = channel.recv(4096)
                if re.search('\[sudo\] ', stdout.decode()):
                    channel.send(host.password+'\n')
                time.sleep(1)
        while True:
            time.sleep(0.001)
            rl, _, _ = select.select([channel], [], [], 0.0)
            if len(rl) > 0:
                for line in linesplit(channel):
                    lines.append(line)
                    get_ssh_logger(host).info(line)
            if channel.exit_status_ready():
                returncode = channel.recv_exit_status()
                break
        # returncode = channel.recv_exit_status()
    except Exception as ex:
        return SSHResult(hostname=host.hostname, command=command, stdout="\n".join(lines), returncode=returncode, exception=repr(ex))
    finally:
        client.close()
    return SSHResult(hostname=host.hostname, command=command, stdout="\n".join(lines), returncode=returncode)


def concurrent(func: Callable, tasks: list):
    if not tasks and len(tasks) <= 0:
        return []
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_list = list()
        result_list = list()
        for task in tasks:
            future_list.append(executor.submit(func, *task))
        for future in as_completed(future_list):
            result_list.append(future.result())
        return result_list


def get_target(hosts: Dict[str, Host], name):
    result = []
    if name in hosts.keys():
        result.append(hosts[name])
    else:
        for host in hosts.values():
            try:
                if Evaluator(host.tags).eval(name):
                    result.append(host)
            except Exception as ex:
                get_ssh_logger(host.hostname).warn(ex)
    return result

# root cmd


@click.group()
@click.option('-i', '--inventory', default=os.path.join(MAIN_DIR, "inventory", "inventory.yaml"), type=click.types.Path(), required=False, help="inventory.yaml path")
@click.option('-l', '--log-level', default='INFO', type=click.Choice(["NOTSET", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]), required=False)
@click.option('-t', '--target', type=str, required=False, help="Host IP address or label expression")
def cli(inventory, log_level, target):
    with open(inventory) as file:
        hosts_dict = yaml.load(file, Loader=Loader)
    hosts_dict = fillinghostname_fromkey(hosts_dict)
    hosts = render_hosts(hosts_dict)
    ssh_logger.setLevel(log_level)
    global TARGET
    if target:
        TARGET = get_target(hosts, target)


# config cmd
@cli.group()
def config():
    pass

default_config ="""
localhost:
  port: 22
  username: root
  password: youerpassword
  tags:
    yourtagkey: yourtagvalue
"""
@config.command()
def dump_default():
    """
    wirte default config
    """
    Path(MAIN_DIR).joinpath("inventory").mkdir(exist_ok=True, parents=True)
    with open(Path(MAIN_DIR).joinpath("inventory").joinpath("inventory.yaml"), "w") as f:
        f.write(default_config)
    click.echo(f'default config write {Path(MAIN_DIR).joinpath("inventory").joinpath("inventory.yaml")} successfully!')


# @config.command()
# def add_host():
#     pass

# @config.command()
# def del_host():
#     pass


# func cmd
"""
exec
"""

default_template = """
========== {{ hostname }} ==========
command: {{ command }}
{% if stdout %}
stdout:
{{stdout}}
{% endif %}
{% if stderr %}
stderr:
{{stderr}}
{% endif %}
returncode: {{ returncode }}
{% if exception %}
exception: {{ exception }}
{% endif %}
"""


@cli.command()
@click.option('-c', '--command', type=str, required=True)
@click.option('--needpty', default=True, type=bool, required=False)
@click.option('--sudo', default=False, type=bool, required=False)
@click.option('-o', '--outmode', default="none", type=click.Choice(["none", "template", "json", "yaml"]))
@click.option('-t', '--template', default=default_template, type=str, required=False)
def execute(command, needpty, sudo, outmode, template):
    """
    execute command
    """
    result = []
    if needpty:
        result = concurrent(
            realtime_output, [tuple([h, command]) for h in TARGET])
    else:
        raise NotImplementedError("not impl nonpty command!")
    if outmode == "none":
        return
    elif outmode == "template":
        template = Template(template, lstrip_blocks=True, trim_blocks=True)
        result.sort(key=lambda k: int(k.hostname.replace(".", "")))
        for r in result:
            click.echo(template.render(dataclasses.asdict(r)))
    elif outmode == "json":
        click.echo(marshmallow_dataclass.class_schema(
            SSHResult)().dumps(result, many=True))
    elif outmode == "yaml":
        click.echo(yaml.dump(result, allow_unicode=True))


@cli.command()
@click.argument('script_file', type=click.types.Path())
@click.argument('script_arg', type=str, nargs=-1, required=False)
@click.option('-e','--env', type=str, multiple=True, required=False)
@click.option('-a', '--attachment', type=str, multiple=True, required=False)
@click.option('-w', '--workdir', default='/root' ,type=str)
@click.option('--needpty', default=True, type=bool, required=False)
@click.option('--sudo', default=False, type=bool, required=False)
@click.option('-o', '--outmode', default="none", type=click.Choice(["none", "template", "json", "yaml"]))
@click.option('-t', '--template', default=default_template, type=str, required=False)
@click.pass_context
def execfile(ctx, script_file, script_arg, env, attachment, workdir, needpty, sudo, outmode, template):
    """
    execute script file
    """
    if not Path(script_file).is_file():
        raise AssertionError("script_file must is executable file!")
    remote_file = str(Path(workdir).joinpath(Path(script_file).name))
    put_files = []
    try:
        put_files.append(remote_file)
        ctx.invoke(put, local_file=script_file, remote_file=remote_file)
        for att_item in attachment:
            remote_att_file = str(Path(workdir).joinpath(Path(att_item).name))
            ctx.invoke(put, local_file=att_item, remote_file=remote_att_file)
            put_files.append(remote_att_file)
        script_env = ''.join(["export %s && " % item for item in env])
        script_arg_str = ' '.join(script_arg)
        command = f"{script_env} cd {workdir} && chmod +x {remote_file} && {remote_file} {script_arg_str}"
        ctx.invoke(execute, command=command, outmode=outmode, template=template)
    finally:
        command = f"rm -rf {' '.join(put_files)}"
        ctx.invoke(execute, command=command, outmode=outmode, template=template)

put_default_template = "{{src}} =====> {{hostname}}:{{dst}} {% if completed %} successfully! {% else %} faild! {% endif %}"

@cli.command()
@click.argument('local_file', type=click.types.Path(exists=True))
@click.argument('remote_file', type=click.types.Path())
@click.option('-o', '--outmode', default="none", type=click.Choice(["none", "template", "json", "yaml"]))
@click.option('-t', '--template', default=put_default_template, type=str, required=False)
@click.option('-r', '--recursive', default=True, type=bool)
@click.option('-p', '--process', default=False, type=bool)
def put(local_file, remote_file, outmode, template, recursive, process):
    """
    upload file
    example:
      pypssh -t 192.168.31.1 put /etc/yum.conf /etc/yum.conf
    """
    def _progress(filename, size, sent, peername):
        click.echo("(%s:%s) %s's progress: %.2f%%   \r" % (
            peername[0], peername[1], filename, float(sent)/float(size)*100))

    def _upload(host):
        try:
            ssh = get_ssh_conn_client(host)
            scp = SCPClient(ssh.get_transport(), progress4=_progress if process else None)
            scp.put(local_file, remote_file, recursive)
            return SCPResult(host.hostname, src=local_file, dst=remote_file, completed=True)
        except Exception as ex:
            return SCPResult(host.hostname, src=local_file, dst=remote_file, completed=False, exception=repr(ex))
    
    result = concurrent(_upload, [tuple([h]) for h in TARGET])

    if outmode == "none":
        return
    elif outmode == "template":
        template = Template(template, lstrip_blocks=True, trim_blocks=True)
        result.sort(key=lambda k: int(k.hostname.replace(".", "")))
        for r in result:
            click.echo(template.render(dataclasses.asdict(r)))
    elif outmode == "json":
        click.echo(marshmallow_dataclass.class_schema(
            SSHResult)().dumps(result, many=True))
    elif outmode == "yaml":
        click.echo(yaml.dump(result, allow_unicode=True))


pull_default_template = "{{dst}} <===== {{hostname}}:{{src}} {% if completed %} successfully! {% else %} faild! {% endif %}"

@cli.command()
@click.argument('remote_file', type=click.types.Path())
@click.argument('local_file', type=click.types.Path())
@click.option('-r', '--recursive', default=True, type=bool)
@click.option('-o', '--outmode', default="none", type=click.Choice(["none", "template", "json", "yaml"]))
@click.option('-t', '--template', default=pull_default_template, type=str, required=False)
@click.option('-n', '--naming-template', default="{{ remote_file_name }}-{{ hostname }}", type=str)
@click.option('-p', '--process', default=False, type=bool)
def pull(remote_file, local_file, outmode, template, recursive, naming_template, process):
    """
    download file
    example:
      pypssh -t 192.168.31.1 put /etc/yum.conf /etc/yum.conf
    """
    def _progress(filename, size, sent, peername):
        click.echo("(%s:%s) %s's progress: %.2f%%   \r" % (
            peername[0], peername[1], filename, float(sent)/float(size)*100))

    def _download(host):
        try:
            ssh = get_ssh_conn_client(host)
            scp = SCPClient(ssh.get_transport(), progress4=_progress if process else None)
            if Path(local_file).is_dir():
                render_local_file = Path(local_file).joinpath(Template(naming_template).render(
                        {
                            **dataclasses.asdict(host), 
                            "local_file": local_file, 
                            "remote_file": remote_file, 
                            "remote_file_name": Path(remote_file).name, 
                            "local_file_name": Path(local_file).name
                        }))
                scp.get(
                    remote_file, 
                    render_local_file, 
                    recursive
                    )
            return SCPResult(host.hostname, src=remote_file, dst=render_local_file, completed=True)
        except Exception as ex:
            return SCPResult(host.hostname, src=remote_file, dst=local_file, completed=False, exception=repr(ex))

    result = concurrent(_download, [tuple([h]) for h in TARGET])

    if outmode == "none":
        return
    elif outmode == "template":
        template = Template(template, lstrip_blocks=True, trim_blocks=True)
        result.sort(key=lambda k: int(k.hostname.replace(".", "")))
        for r in result:
            click.echo(template.render(dataclasses.asdict(r)))
    elif outmode == "json":
        click.echo(marshmallow_dataclass.class_schema(
            SSHResult)().dumps(result, many=True))
    elif outmode == "yaml":
        click.echo(yaml.dump(result, allow_unicode=True))


@cli.command()
def ls():
    """
    list host
    """
    click.echo(yaml.dump([i.hostname for i in TARGET], allow_unicode=True))


@cli.command()
def ping():
    """
    ping hosts
    """
    def _connect_test(host: Host):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(host.timeout)
        try:
            s.connect((host.hostname, host.port))
        except Exception as ex:
            get_ssh_logger(host).error(
                f"connection {host.port} test exception: {ex}")
            return None
        finally:
            s.close()
        return host

    def _ssh_test(host):
        try:
            client = get_ssh_conn_client(host)
        except Exception as ex:
            get_ssh_logger(host).error(f"ssh test exception: {ex}")
            return None
        return host

    c = [i for i in concurrent(_connect_test, [tuple([i])
                               for i in TARGET]) if i]
    s = concurrent(_ssh_test, [tuple([i]) for i in c if i])

    working_host = [i.hostname for i in s if i]
    non_working_host = [i.hostname for i in TARGET if i not in s]
    working_host.sort(key=lambda key: int(key.replace(".", "")))
    non_working_host.sort(key=lambda key: int(key.replace(".", "")))
    result = {'working_host': working_host,
              'non_working_host': non_working_host}
    click.echo(yaml.dump(result, allow_unicode=True))


@cli.command()
def version():
    """
    print version
    """
    addr = "https://github.com/witchc/pypssh"
    vno = "v0.2.0"
    interrupt_version = "Python " + ' '.join(sys.version.split('\n'))
    print(
        "\n".join
        ([
            f"地址: {addr}",
            f"版本号: {vno}",
            f"解释器版本: {interrupt_version}",
            f"发行版: {platform.platform()}"
        ])
    )


if __name__ == '__main__':
    cli()