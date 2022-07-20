# `optimodel` : Constraint Minimization Toolkit

This repository contains a toolkit for minimizing constraint systems (CNF/DNF/MILP inequalities), primarily for in-place modeling subsets of bit-vectors of small dimensions using CNF or DNF formulas, of systems of inequalities on binary integer variables. "In-place" refers to not using auxiliary variables.

**Warning:** small constraint systems do not imply better performance (although may have some correlation on practice).

The code is based on the paper ([ia.cr/2021/1099](https://ia.cr/2021/1099)) by Aleksei Udovenko titled

> *MILP modeling of Boolean functions by minimum number of inequalities*.

Many datasets, results and benchmarks are available in a separate repository [optimodel-results](https://github.com/hellman/optimodel-results).

## Installation

### Main part

The main part requires the `subsets` python module based on C++, which requires `swig` and a C++ compiler to be installed. Then, optimodel can be installed usig `pip` directly:

```bash
apt install swig g++ python-dev
pip install wheel
pip install optimodel
```

The tool uses both SAT-solvers and MILP-optimizers, so you need to install something that is supported by the [optisolveapi](https://github.com/hellman/optisolveapi) module (currently, not much..). The simplest is to install [PySAT](https://pysathq.github.io/) and [GLPK]() with low-level python bindings [swiglpk](https://github.com/biosustain/swiglpk):

**Note:** currently, they are listed as requirements for optisolveapi and will be installed automatically.

```bash
apt install glpk-utils libglpk-dev
pip install python-sat[pblib,aiger] swiglpk
```

### Minimization part

GLPK however won't work well for the final minimzation step for large functions. It is recommended to use Gurobi or SCIP.

Note that it is possible to write the LP file and solve manually with any external solver.

Alternative is to use (unicost) SetCover solvers, which quickly derive heuristic good solutions, although without any lower bound.
Recommendation: [setcoveringsolver](https://github.com/fontanf/setcoveringsolver) by Florian Fontan.

### SAT: [PySAT]()

```bash
pip install python-sat[pblib,aiger]
```

### MILP: [GLPK](https://www.gnu.org/software/glpk/) (open source)

- install GLPK solver: `apt install glpk-utils libglpk-dev`
- install python bindings: `pip install swiglpk`

### MILP: [Gurobi](https://www.gurobi.com/) (commercial, free academic licenses)

- download archive
- add `bin/` to PATH and `lib/` to LD_LIBRARY_PATH
- install python module: `python setup.py install`
- get license
- activate license: `$ grbgetkey ...`

### MILP: [SCIP Optimization Suite](https://scipopt.org/) (open source)

[Download page](https://scipopt.org/index.php#download)

```bash
# some prerequisites:
apt install gcc g++ gfortran liblapack3 libtbb2 libcliquer1 libopenblas-dev libgsl23 patchelf
# install python bindings:
`pip install pyscipopt`
```

## Usage

TO DO

## Results

See [optimodel-results](https://github.com/hellman/optimodel-results).

## Citation

```
@misc{cryptoeprint:2021/1099,
      author = {Aleksei Udovenko},
      title = {MILP modeling of Boolean functions by minimum number of inequalities},
      howpublished = {Cryptology ePrint Archive, Paper 2021/1099},
      year = {2021},
      note = {\url{https://eprint.iacr.org/2021/1099}},
      url = {https://eprint.iacr.org/2021/1099}
}
```