#!/usr/bin/env python

from distutils.core import setup

setup(name='Distutils',
      version='1.0',
      description='Athome automation hub',
      author='Alessandro Duca',
      author_email='alessandro.duca@gmail.com',
      url='https://github.com/dual75/athome',
      package_dir={'':'src'},
      packages=['athome', 'athome.api', 'athome.lib', 'athome.subsystems'],
      data_files=[
            ('/etc/systemd/system', ['scripts/athome.service'])
      ]
     )
