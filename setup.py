import os
from setuptools import setup
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='snitchpy',
    version='0.0.1',
    description='Python client SDK for Streamdal.com Snitch',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/streamdal/snitch-python-client',
    author='Streamdal.com',
    author_email='engineering@streamdal.com',
    license='MIT',
    packages=['snitchpy', 'snitchpy.metrics'],
    install_requires=[''],
    python_requires=">=3.8",

    classifiers=[
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)