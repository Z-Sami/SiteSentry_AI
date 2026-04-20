"""Setup configuration for SiteSentry autonomous construction QA robot."""

from setuptools import setup, find_packages

setup(
    name="sitesentry",
    version="1.0.0",
    description="Autonomous construction QA robot with SLAM, inspection, and reporting",
    author="SiteSentry Team",
    packages=find_packages(),
    python_requires=">=3.9",
    include_package_data=True,
    install_requires=[
        "python-dotenv>=1.0.0",
        "smbus2>=0.4.2",
        "requests>=2.31.0",
        "pyserial>=3.5",
        "opencv-python>=4.8.0",
        "numpy>=1.26.0",
        "pillow>=10.0.0",
        "matplotlib>=3.8.0",
        "reportlab>=4.0.8",
        "python-telegram-bot>=20.1",
    ],
    entry_points={
        "console_scripts": [
            "sitesentry=sitesentry.main:main",
        ],
    },
)
