from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="rann-agent",
    version="1.0.0",
    author="Rann",
    author_email="rann@example.com",
    description="Next-generation autonomous AI agent with self-healing and multi-agent orchestration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rann-xyz/rann-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "rann-agent=rann_agent.cli.main:app",
        ],
    },
    include_package_data=True,
    package_data={
        "rann_agent": [
            "config/*.yaml",
            "templates/*.j2",
        ],
    },
)
