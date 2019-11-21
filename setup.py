from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
        name="odoc",
        version="0.1.0",
        py_modules=find_packages(),
        description="A documentation generator for Odoo modules.",
        long_description=long_description,
        long_description_content_type="text/markdown",
        url="https://github.com/wangonya/odoc",
        author="Kinyanjui Wangonya",
        author_email="kwangonya@gmail.com",
        license="AGPL",
        classifiers=[
            "License :: OSI Approved :: AGPL License",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.7",
        ],
        install_requires=[
            "Click",
            "requests",
            "halo"
            ],
        entry_points="""
        [console_scripts]
        odoc=app:cli
        """,
        )
