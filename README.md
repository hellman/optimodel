# `optimodel` : Constraint Minimization Toolkit

This repository contains a toolkit for minimizing constraint systems (CNF/DNF/MILP inequalities), primarily for in-place modeling subsets of bit-vectors of small dimensions using CNF or DNF formulas, of systems of inequalities on binary integer variables. "In-place" refers to not using auxiliary variables.

**Warning:** small constraint systems do not imply better performance (although may have some correlation on practice).

**Warning:** the project is in its early stages under development, things may break/not work, be unclear, etc.

The code is based on the paper ([ia.cr/2021/1099](https://ia.cr/2021/1099)) by Aleksei Udovenko titled

> *MILP modeling of Boolean functions by minimum number of inequalities*.

<!-- Many datasets, results and benchmarks are available in a separate repository [optimodel-results](https://github.com/hellman/optimodel-results). -->

Based on closely related packages
- [monolearn](https://github.com/hellman/monolearn) - generic monotone learning, and
- [optisolveapi](https://github.com/hellman/optisolveapi) - efficient SAT/MILP APIs).


## Installation

### Main part

The main part requires the `subsets` python module writtin in C++, which requires `swig` and a C++ compiler to be installed. Nowadays, swig can be installed as a python package and so will be automatically pulled as a dependency.

The tool uses both SAT-solvers and MILP-optimizers, so you need to install something that is supported by the [optisolveapi](https://github.com/hellman/optisolveapi) module (currently, not much). The simplest is to use [PySAT](https://pysathq.github.io/) and [GLPK](https://www.gnu.org/software/glpk/) with low-level python bindings [swiglpk](https://github.com/biosustain/swiglpk). [Gurobi](https://gurobi.com/) is also supported if you have a license. It is mainly useful for the subset cover step on big problems.

The full setup (Gurobi solver has to be installed separately) can be done as follows:

```bash
apt install glpk-utils libglpk-dev g++ python3-dev  # also "swig" if build fails later
pip install wheel  # not sure if needed
pip install optimodel[glpk,pysat,scip,gurobi]  # note: this installs gurobipy; omit gurobi if on PyPy
```

The tool can be run on PyPy but there the `gurobipy` binding is not supported, so the \[gurobi\] option has to be omitted.

### Minimization part

GLPK won't work well for the final minimzation step for large functions. It is recommended to use [Gurobi](gurobi.com) (commercial, free licenses for academia) or [SCIP](https://scipopt.org/) (free, open-source). (SCIP support is currently broken in this tool, but should be fixed ASAP).

Note that it is possible to write the LP file and solve manually with any external solver.

Alternative is to use (unicost) SetCover solvers, which quickly derive heuristic good solutions, although without any lower bound.
Recommendation: [setcoveringsolver](https://github.com/fontanf/setcoveringsolver) by Florian Fontan.

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

### Advanced usage

Under the hood, the tools run a sequence of commands, such as algorithms to generate complete systems of covers, commands to write down the final minimization problem as a set cover problem or as a MILP problem, etc.

By default, the tools use hardcoded sequences of commands depending on the problem size. This should work well for small-medium problems (using the GLPK solver), but for larger problems may not work fully automatically.

For finding the complete covering system of constraints, there are currently two methods:

1. `optimodel.milp set/ AutoSimple` , which learns the feasibility of removing of each **pair** of points (command `Learn:LevelLearn,levels_lower=3`), and then uses the Gainanov's monotone learning with the Cadical SAT solver (command `Learn:GainanovSAT,sense=min,save_rate=100,solver=pysat/cadical`), followed by automatic minimization step, see below.

2. `optimodel.milp set/ AutoShifts` uses the advanced technique by finding all maximal removable sets per each **direction** and then merging them together (command `ShiftLearn:threads=7`); it requires the learning configuration to be set using `AutoChain` command (alias for `Chain:LevelLearn,levels_lower=3` and `Chain:GainanovSAT,sense=min,save_rate=100,solver=pysat/cadical`).

Then, the minimal set of constraints can be selected using several ways:

1. `SubsetMILP:` directly solves the problem using available solver API (typically GLPK), can be modified to use particular solver, eg.g. `SubsetMILP:solver=gurobi`
2. `SubsetWriteMILP:solver=swiglpk` writes the minimization problem into an LP file (the solver is only used for creating and writing the problem)
3. `SubsetSCS:` directly solves the problem (heuristically) using the [setcoveringsolver](https://github.com/fontanf/setcoveringsolver) (needs to be installed in the system), different algorithms are possible
4. `SubsetWriteGecco:` writes the minimization problem into a Gecco file (set covering problem instance).

Options 2 and 4 also create `.meta` file which connects the minimization problem to the LP/Gecco instance, so that a solution can be mapped back (tool NOT IMPLEMENTED YET). In the meta-file, each line contains:

(constraint ID) (points it removes) (constraint: inequality/clause) (is it pre-selected? 1/0 for yes/no)

<!--
## Results

See [optimodel-results](https://github.com/hellman/optimodel-results).
-->


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