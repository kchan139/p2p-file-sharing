# setup.py
from setuptools import setup, find_packages

setup(
    name="p2p-file-sharing",
    version="0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        # Add your dependencies here if any
    ],
    python_requires=">=3.10",
)