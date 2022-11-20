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
apt install swig g++ python3-dev
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

GLPK however won't work well for the final minimzation step for large functions. It is recommended to use [Gurobi](gurobi.com) (commercial, free licenses for academia) or [SCIP](https://scipopt.org/) (free, open-source). (SCIP support is currently broken in this tool, but should be fixed ASAP).

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

<!--
### MILP: [SCIP Optimization Suite](https://scipopt.org/) (open source)

[Download page](https://scipopt.org/index.php#download)

```bash
# some prerequisites:
apt install gcc g++ gfortran liblapack3 libtbb2 libcliquer1 libopenblas-dev patchelf
# one of the two:
apt install libgsl23
apt install libgslcblas0
# install python bindings:
pip install pyscipopt
```
-->

## Usage

### Instance format

The modeled set should be stored in a separate folder in 3 files:

1. `included.txt` - set of **included** (allowed) points (format: first line number of points **N** and dimension **n**, then **N** lines with points, all entries separated by space)
2. `excluded.txt` - set of **excluded** (removed) points (format: first line number of points **N** and dimension **n**, then **N** lines with points, all entries separated by space)
3. `type` - information about set type (typically `explicit binary`, can be also `upper binary` or `lower binary` for an upper- or a lower-set, given by their extremes).

Sets can be compressed with **bz2** and stored in `included.bz2`/`excluded.bz2`.

See example in [./example_present_ddt/](./example_present_ddt/):

```sh
$ ls -1 example_present_ddt/
exclude.bz2
include.bz2
type

$ bzcat example_present_ddt/include.bz2  | head
97 8
0 0 0 0 0 0 0 0
0 0 0 1 0 0 1 1
0 0 0 1 0 1 1 1
0 0 0 1 1 0 0 1
0 0 0 1 1 1 0 1
0 0 1 0 0 0 1 1
0 0 1 0 0 1 0 1
0 0 1 0 0 1 1 0
0 0 1 0 1 0 1 0

$ bzcat example_present_ddt/exclude.bz2  | head
159 8
0 0 0 0 0 0 0 1
0 0 0 0 0 0 1 0
0 0 0 0 0 0 1 1
0 0 0 0 0 1 0 0
0 0 0 0 0 1 0 1
0 0 0 0 0 1 1 0
0 0 0 0 0 1 1 1
0 0 0 0 1 0 0 0
0 0 0 0 1 0 0 1

$ cat example_present_ddt/type 
explicit binary
```

### Minimizing CNF/DNF - Tool `optimodel.boolean`

```sh
$ optimodel.boolean --cnf ./example_present_ddt/
...
00:00:00.081 INFO optimodel.constraint_pool:ConstraintPool: got 36 constraintsfrom subset_by_milp (optimal? True)
00:00:00.082 INFO optimodel.constraint_pool:ConstraintPool: saving 36 constraints to ./example_present_ddt//cnf.36.opt
...

$ optimodel.boolean --dnf ./example_present_ddt/
...
00:00:00.075 INFO optimodel.constraint_pool:ConstraintPool: got 38 constraintsfrom subset_by_milp (optimal? True)
00:00:00.075 INFO optimodel.constraint_pool:ConstraintPool: saving 38 constraints to ./example_present_ddt//dnf.38.opt
...
```

Outputs are in the standard format (first line - number of clauses, then clauses one perline)
```sh
$ cat example_present_ddt/cnf.36.opt
36
-2 -3 5 -6 7 -8
-1 -2 3 -5 -6 7
1 2 4 -5 6 7
...

$ cat example_present_ddt/dnf.38.opt
38
-1 2 3 5 6 7 8
1 2 -4 5 -6 -7
...
```

### Minimizing inequalities - Tool `optimodel.milp`

```sh
$ optimodel.milp example_present_ddt/
...
00:00:01.830 INFO optimodel.constraint_pool:ConstraintPool: got 16 constraintsfrom subset_by_milp (optimal? True)
00:00:01.831 INFO optimodel.constraint_pool:ConstraintPool: saving 16 constraints to example_present_ddt//ineq.16.opt
...

$ cat example_present_ddt/ineq.16.opt
16
-4 6 6 -6 -2 1 -2 -5 13
-7 5 5 11 3 -4 3 8 0
...
```



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