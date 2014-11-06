#!/usr/bin/env python

# Version extraction is from https://github.com/django-compressor/django-compressor/blob/develop/setup.py

import ast
import codecs
import os
from distutils.command.sdist import sdist
from pip.req import parse_requirements
from setuptools import setup, find_packages
from subprocess import call


def get_requirements(source):
    """
    Get the path of a requirements file and return a set of included packages
    """
    install_reqs = parse_requirements(source)
    return set([str(ir.req) for ir in install_reqs])


class VersionFinder(ast.NodeVisitor):
    """
    Class to find the `__version__` assignment in a file
    """
    def __init__(self):
        self.version = None

    def visit_Assign(self, node):
        if node.targets[0].id == '__version__':
            self.version = node.value.s


def read(*parts):
    """
    Get the file found at the given path (parts are different parts of the path)
    And return the content of this file
    """
    filename = os.path.join(os.path.dirname(__file__), *parts)
    with codecs.open(filename, encoding='utf-8') as fp:
        return fp.read()


def find_version(*parts):
    """
    Get the file found at the given path (parts are different parts of the path)
    And return the version found in the file
    """
    finder = VersionFinder()
    finder.visit(ast.parse(read(*parts)))
    return finder.version


class my_sdist(sdist):
    """
    Override the default sdist command to create a bunch of needed files to be
    included in the packages
    """
    def run(self):
        # honor the --dry-run flag
        if not self.dry_run:
            call(['django-admin.py', 'collectstatic', '--noinput', '-c'])
        # distutils uses old-style classes, so no super()
        sdist.run(self)


setup(
    name='gim',
    version=find_version('gim', '__init__.py'),

    packages=find_packages(),
    include_package_data=True,

    install_requires=get_requirements('requirements/base.txt'),

    description='GIM, the Github Issues manager',
    long_description=read('README.md'),

    cmdclass={'sdist': my_sdist},
    zip_safe=False,

    url='https://github.com/twidi/github-issues-manager/',
    author='Stephane "Twidi" Angel',
    author_email='s.angel@twidi.om',
)
