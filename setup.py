from setuptools import setup, find_packages

setup(
    name="sardana-iba",
    version = "version="0.1.0"",
    description = "IBA Sardana Controller",
    author = "ALBA",
    author_email = "controls@cells.es",
    license = "GPLv3",
    url = "https://github.com/ALBA-Synchrotron/sardana-iba",
    packages = find_packages(),
    install_requires = ['sardana'],
)
