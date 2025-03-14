from setuptools import setup, find_packages

setup(
    name="gitmirror",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "PyGithub>=2.1.1",
        "python-dotenv>=1.0.0",
        "Flask>=2.3.3",
        "APScheduler>=3.10.4",
        "Flask-Caching>=2.1.0",
    ],
    entry_points={
        "console_scripts": [
            "gitmirror=gitmirror.cli:main",
        ],
    },
    author="Jonas Rosland",
    author_email="jonas.rosland@gmail.com",
    description="A tool to mirror GitHub repositories to Gitea",
    keywords="github, gitea, mirror",
    url="https://github.com/jonasrosland/gitmirror",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
) 