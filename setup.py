#!/usr/bin/env python

import sys
from setuptools import setup
sys.path.insert(0, '.')
import versioneer

setup(name='dmf-device',
      version=versioneer.get_version(),
      description=open('README.md', 'rb').read(),
      author='Christian Fobel',
      author_email='christian@fobel.net',
      url='https://github.com/Lucaszw/dmf_device',
      install_requires=['droplet-planning', 'lxml', 'networkx', 'numpy',
                        'pandas', 'path_helpers','pyyaml', 'svg-model'],
      packages=['dmf_device'])
