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
        license="AGPL-3.0",
        classifiers=[
            "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
            "Programming Language :: Python :: 3 :: Only",
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
        python_requires='>= 3.5',
        )
