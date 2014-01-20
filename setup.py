#!/usr/bin/env python

import os
import glob
from setuptools import setup
from deploytools import __version__


def find_packages(root):
    packages = []

    for dirname, dirnames, filenames in os.walk(root):
        package = os.path.split(dirname)

        if (os.path.exists(os.path.join(dirname, '__init__.py'))
                and not package[-1].startswith(".")):

            packages.append(".".join(package).lstrip("."))

    return packages


setup(
    name='finiteloop-deploy',
    version='.'.join(str(s) for s in __version__),
    description='Finite Loop Deployment System',
    author='Mike Crute',
    author_email='mike@finiteloopsoftware.com',
    url='http://finiteloopsoftware.com',
    packages=find_packages('deploytools'),
    package_data={ 'deploytools': ['templates/*', ]},
    install_requires=['fabric'],
    entry_points={
        'console_scripts': [
            'deploy = deploytools.__main__:main',
        ],
    }
)
