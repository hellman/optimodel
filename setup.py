from distutils.core import setup


setup(
    name='optimodel',
    version='0.2.0',
    packages=["optimodel", "optimodel.tool"],

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
        'subsets>=1.1.0',
        'optisolveapi',
        'monolearn',
        'justlogs',
    ],

    entry_points={
        'console_scripts': [
            'optimodel.milp = optimodel.tool.milp:main',
            'optimodel.boolean = optimodel.tool.boolean:main',
            #'optimodel.verify_milp = optimodel.tool.verify_milp:main',
        ]
    },
)
