#!/usr/bin/env python

from setuptools import setup

setup(
    name='co2mqtt',
    version='1.0.0',
    description='Client for MT8057 CO2 sensor',
    # long_description='',
    # long_description_content_type="text/x-rst",
    author='Ivan Belokobylskiy',
    author_email='belokobylskij@gmail.com',
    url='https://github.com/devbis/co2mqtt/',
    install_requires=[
        'CO2meter @ git+https://github.com/vfilimonov/co2meter.git@8a2e12d205a7ac1c0a8fbc7fe885fc60cf2d1d0c#egg=CO2meter',
        'aio-mqtt==0.2.0',
    ],
    classifiers=[
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Utilities',
    ],
)
