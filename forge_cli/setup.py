from setuptools import setup

setup(
    name="forge-cli",
    version="0.1.0",
    description="Deploy any HTML app to Forge in one command.",
    author="Forge",
    packages=["forge_cli"],
    python_requires=">=3.9",
    install_requires=[],
    entry_points={
        "console_scripts": [
            "forge = forge_cli.cli:main",
        ],
    },
)
