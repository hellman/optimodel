from distutils.core import setup

setup(
    name='monolearn',
    version='0.1.0',
    packages=["monolearn"],

    url=None,
    license="MIT",

    author='Aleksei Udovenko',
    author_email="aleksei@affine.group",
    maintainer=None,
    maintainer_email=None,

    description="""Learning monotone Boolean functions""",
    long_description=None,

    python_requires='>=3.5,<4.0',
    install_requires=[
        'subsets',
        'python-sat[pblib,aiger]',
    ],
)
