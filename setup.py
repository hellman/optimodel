from distutils.core import setup


setup(
    name='optimodel',
    version='0.2.0',
    packages=["optimodel"],

    url=None,
    license="MIT",

    author='Aleksei Udovenko',
    author_email="aleksei@affine.group",
    maintainer=None,
    maintainer_email=None,

    description="""Tools for generating ~shortest MILP and SAT models""",
    long_description=None,

    python_requires='>=3.5,<4.0',
    install_requires=[
        'binteger',
        'subsets',
        'optisolveapi',
        'monolearn',
        'justlogs',
    ],

    entry_points={
        'console_scripts': [
            'optimodel.milp = optimodel.tool_milp:main',
            'optimodel.verify_milp = optimodel.tool_verify:tool_verify_milp',
        ]
    },
)
