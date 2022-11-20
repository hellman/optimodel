import os
import argparse

from enum import Enum
from time import time

from binteger import Bin
from subsets import DenseSet

from subsets.max_cubes import MaxCubes_Dense2
from subsets.max_cubes import MaxCubes_Dense3

from monolearn.SparseSet import SparseSet
from monolearn.utils import TimeStat

from optimodel.constraint_pool import ConstraintPool
from optimodel.clause import AndClause, OrClause

from optimodel.tool.constraint_base import ConstraintTool
from optimodel.tool.set_files import read_set, SetType, TypeGood
from optimodel.tool.base import complement_binary

import justlogs
import logging

# sage/pure python compatibility
try:
    import sage.all
except ImportError:
    pass


AutoDefault = (
    #"MaxCubes:Sparse",
    "MaxCubes:Dense3",
    "AutoSelect",
)


class Format(Enum):
    CNF = "cnf"
    DNF = "dnf"


class ToolBoolean(ConstraintTool):
    KIND = "clause"

    log = logging.getLogger(__name__)

    def __init__(self):
        # please the linter
        self.args = None
        self.format = None
        self.fileprefix = None
        self.output_prefix = None
        self.dontcare = None
        self.sysfile = None
        self.coverspace = None
        self.cubespace = None
        self.pool = None
        self.force = None

    def main(self):
        justlogs.setup(level="INFO")

        parser = argparse.ArgumentParser(
            description="Generate minimal/small CNF or DNF to model a set.".strip()
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force Quine-McCluskey algorithm call (ignore cache)"
        )
        parser.add_argument(
            "--dontcare",
            action="store_true",
            help="Use `don't care` points."
                 " For CNF, will use the complement of `included` points"
                 " for generating maximal cubes"
                 " (`excluded` still used for coverage)."
                 " For DNF, will use the complement of `exclude` points"
                 " for generating maximal cubes"
                 " (`included` still used for coverage)."
        )
        parser.add_argument("--cnf", action="store_true", help="Generate CNF")
        parser.add_argument("--dnf", action="store_true", help="Generate DNF")
        parser.add_argument(
            "fileprefix", type=str,
            help="File prefix "
            "(files with appended `type`, `feasible.bz2` or `infeasible.bz2` must exist)"
        )
        parser.add_argument(
            "commands", type=str, nargs="*",
            help="Commands with options (available: Learn:* ???)",
        )

        args = self.args = parser.parse_args()

        if args.cnf and args.dnf:
            raise ValueError("only one of --cnf, --dnf can be specified")

        self.format = Format.DNF if args.dnf else Format.CNF  # cnf by default

        self.fileprefix = args.fileprefix
        if os.path.isdir(self.fileprefix):
            self.fileprefix += "/"
        self.output_prefix = self.fileprefix + self.format.value + "."

        justlogs.addFileHandler(self.output_prefix + "log")
        self.log.info(args)

        self.dontcare = args.dontcare
        self.sysfile = self.output_prefix + "system.bz2"

        try:
            typ = SetType.read_from_file(self.fileprefix + "type")
        except FileNotFoundError:
            raise FileNotFoundError(f"type file not found: {self.fileprefix + 'type'}")

        self.read_sets(typ)

        self.pool = ConstraintPool(
            include=None,
            exclude=self.coverspace,
            sysfile=self.sysfile,
            output_prefix=self.output_prefix,
            constraint_class=OrClause,  # even in CNF we first cover the complement with Or clauses, then flip
        )

        self.force = args.force

        self.log.info(f"using output prefix {self.output_prefix}")

        commands = args.commands or AutoDefault

        self.log.info(f"commands: {' '.join(commands)}")

        for cmd in commands:
            self.run_command_string(cmd)

        self.log_time_stats(header="Finished")

    def read_sets(self, typ: TypeGood):
        if self.format == Format.CNF:
            self.log.info("CNF format: using excluded set")

            self.coverspace = read_set(self.fileprefix + "exclude")
            if self.dontcare:
                self.cubespace = \
                    complement_binary(read_set(self.fileprefix + "include"))
            else:
                self.cubespace = self.coverspace

        elif self.format == Format.DNF:
            self.log.info("DNF format: using included set")

            self.coverspace = read_set(self.fileprefix + "include")
            if self.dontcare:
                self.cubespace = \
                    complement_binary(read_set(self.fileprefix + "exclude"))
            else:
                self.cubespace = self.coverspace

        else:
            raise RuntimeError()

        if typ.type_good in (TypeGood.LOWER, TypeGood.UPPER):
            self.log.warning(f"expanding {typ.type_good.value} include set into EXPLICIT")

            if (self.format == Format.CNF) ^ (typ.type_good == TypeGood.UPPER):
                self.coverspace = to_upper(self.coverspace)
                self.cubespace = to_upper(self.cubespace)
            elif (self.format == Format.CNF) ^ (typ.type_good == TypeGood.LOWER):
                self.coverspace = to_lower(self.coverspace)
                self.cubespace = to_lower(self.cubespace)
            else:
                raise RuntimeError()

    @TimeStat.log
    def MaxCubes(self, algorithm="Dense3", checks=0):
        if algorithm == "Sparse":
            raise NotImplementedError(
                "MaxCubes:Sparse not implemented, use MaxCubes:Dense2 or MaxCubes:Dense3"
            )
        elif algorithm == "Dense2":
            QMC = MaxCubes_Dense2
        elif algorithm == "Dense3":
            QMC = MaxCubes_Dense3
        else:
            raise NotImplementedError(algorithm)

        if not self.force and self.pool.system.is_complete_lower:
            self.log.info("reusing complete system")
            self.pool.system.log_info()
            return

        self.log.info(f"calling Quine-McCluskey algorithm {QMC.__name__}")
        t0 = time()
        cubes = TimeStat.log(QMC)(self.cubespace)
        t = time() - t0
        self.log.info("done Quine-McCluskey")
        self.log.info(
            f"time {self.format.value} {QMC.__name__} {t:.2f} seconds"
        )

        self.log.info("filling the system with cubes...")
        n = self.pool.n
        for a, u in cubes:
            a = Bin(a, n)
            u = Bin(u, n)
            assert a & u == 0
            # a + lowerset(u) subseteq EXC
            rem_clause = []
            for i in range(n):
                if u[i] == 0:  # non-wildcard
                    if a[i] == 0:
                        rem_clause.append(-(i+1))
                    else:
                        rem_clause.append((i+1))
            rem_clause = AndClause(rem_clause)  # subseteq EXC
            keep_clause = ~rem_clause  # superseteq INC

            # option 1: expand cube and check each point
            cube = rem_clause.solutions(n).to_Bins()

            if checks:
                d = DenseSet(n)
                d.set(u.int)
                d.do_LowerSet()
                d.do_Not(a.int)
                assert rem_clause.solutions(n).to_Bins() == d.to_Bins()
                for v in cube:
                    assert rem_clause.satisfy(v)

            inds = []
            for pt in cube:
                ind = self.pool.exc2i.get(Bin(pt, n).tuple)
                # can be None if it's a `don't care` point
                if ind is not None:
                    inds.append(ind)

            # option 2: iterate through exclude points and check cube
            # todo

            fset = SparseSet(inds)
            if self.format == Format.CNF:
                clause = keep_clause
            else:
                clause = rem_clause

            self.pool.system.add_lower(vec=fset, meta=clause, is_prime=True)

        self.pool.system.set_complete_lower()
        self.pool.system.save()

    def _output_one(self, clause):
        if self.format == Format.DNF:
            clause = ~clause
        return super()._output_one(clause)


def to_lower(P):
    for v in P:
        n = len(v)
        break
    else:
        return []
    P = [Bin(v, n).int for v in P]
    return [v.tuple for v in DenseSet(n, P).LowerSet().to_Bins()]


def to_upper(P):
    for v in P:
        n = len(v)
        break
    else:
        return []
    P = [Bin(v, n).int for v in P]
    return [v.tuple for v in DenseSet(n, P).UpperSet().to_Bins()]


def main():
    return ToolBoolean().main()


if __name__ == '__main__':
    main()
