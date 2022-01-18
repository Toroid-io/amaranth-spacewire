#!/usr/bin/env python3

from setuptools import setup
from setuptools import find_packages


setup(
    name="amaranth-spacewire",
    description="SpaceWire Node written in Amaranth",
    author="Andrés MANELLI",
    author_email="am@toroid.io",
    url="",
    download_url="",
    test_suite="",
    license="propietary",
    python_requires="~=3.6",
    packages=find_packages(exclude=("test*", "sim*", "doc*", "examples*")),
    include_package_data=True
)
