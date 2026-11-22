from setuptools import setup, find_packages

setup(
    name="omnidisplay",
    version="1.0.0",
    description="Cross-Platform Dual-PC Dual-Monitor Coordinator",
    author="Vismay Thaker",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "omnidisplay = omnidisplay.cli:main",
        ],
    },
    python_requires=">=3.8",
)
