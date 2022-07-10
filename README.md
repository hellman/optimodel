# `optimodel` : Constraint Minimization Toolkit

This repository contains a toolkit for minimizing constraint systems (CNF/DNF/MILP inequalities), primarily for in-place modeling subsets of bit-vectors of small dimensions using CNF or DNF formulas, of systems of inequalities on binary integer variables. "In-place" refers to not using auxiliary variables.

**Warning:** small constraint systems do not imply better performance (although may have some correlation on practice).

The code is based on the paper ([ia.cr/2021/1099](https://ia.cr/2021/1099)) by Aleksei Udovenko titled

> *MILP modeling of Boolean functions by minimum number of inequalities*.

Many datasets, results and benchmarks are available in a separate repository [optimodel-results](https://github.com/hellman/optimodel-results).

## Installation

TO DO

## Usage

TO DO

## Results

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