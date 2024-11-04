from setuptools import setup

# Helper function to read the requirements file
def load_requirements(filename="requirements.txt"):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line and not line.startswith("#")]

setup(
    name="bartdepart",
    version="0.1.0",
    py_modules=["bartdepart"],
    install_requires=load_requirements(),
    entry_points={
        "console_scripts": [
            "bartdepart=bartdepart:main",
        ],
    },
)
