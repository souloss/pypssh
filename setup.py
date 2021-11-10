#!/usr/bin/python
# from distutils.core import setup
from setuptools import setup, find_packages, find_namespace_packages

setup(
      name='pypssh',
      version='0.2.2',
      description='pypssh',
      author='pypssh developers',
      maintainer='witchc',
      author_email='lebowitzgerald407@gmail.com',
      url='https://github.com/witchc/pypssh',
      license='MIT',
      # 要打包的项目文件夹
    #   packages = find_packages("."),
    #   package_dir={"sauto3":"sauto3"},
      # 自动打包文件夹内所有数据
      include_package_data=True,
      # package_data={'sauto3.static': ['*']},
      zip_safe=False, 
      # 安装依赖的其他包
      install_requires = [
        "paramiko",
        "PyYAML",
        "click",
        "Jinja2",
        "marshmallow-dataclass",
        "tenacity"
      ],
    # 设置程序的入口
    # 安装后，命令行执行 `key` 相当于调用 `value`: 中的 :`value` 方法
    entry_points={
        'console_scripts':[
            'pypssh = pypssh.__main__:main'
        ]
    },
    python_requires='>=3.7'
)
