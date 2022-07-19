import os
import argparse

from enum import Enum
from time import time

from binteger import Bin
from monolearn.SparseSet import SparseSet
from monolearn.utils import TimeStat

from subsets.misc import Quine_McCluskey_Step1_Dense2
from subsets.misc import Quine_McCluskey_Step1_Dense3

from optimodel.constraint_pool import ConstraintPool, read_set
from optimodel.clause import AndClause, OrClause
from optimodel.tool.constraint_base import ConstraintTool
from optimodel.tool.base import complement_binary

import justlogs
import logging

# sage/pure python compatibility
try:
    import sage.all
except ImportError:
    pass


AutoDefault = (
    #"QmC:Sparse",
    "QmC:Dense3",
    "AutoSelect",
)


class Format(Enum):
    CNF = "cnf"
    DNF = "dnf"


class ToolQMC(ConstraintTool):
    KIND = "clause"

    log = logging.getLogger(__name__)

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
            "(files with appended `feasible.bz2` or `infeasible.bz2` must exist)"
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
        self.sysfile = self.output_prefix + "system"

        if self.format == Format.CNF:
            self.log.info("CNF format: using excluded set")

            self.coverspace = read_set(self.fileprefix + "exclude")
            if self.dontcare:
                self.cubespace = \
                    complement_binary(read_set(self.fileprefix + "include"))
            else:
                self.cubespace = self.coverspace

            self.pool = ConstraintPool(
                include=None,
                exclude=self.coverspace,
                sysfile=self.sysfile,
                output_prefix=self.output_prefix,
                constraint_class=AndClause,
            )
        elif self.format == Format.DNF:
            self.log.info("DNF format: using included set")

            self.coverspace = read_set(self.fileprefix + "include")
            if self.dontcare:
                self.cubespace = \
                    complement_binary(read_set(self.fileprefix + "exclude"))
            else:
                self.cubespace = self.coverspace

            self.pool = ConstraintPool(
                include=None,
                exclude=self.coverspace,
                sysfile=self.sysfile,
                output_prefix=self.output_prefix,
                constraint_class=OrClause,
            )

        self.force = args.force

        self.log.info(f"using output prefix {self.output_prefix}")

        commands = args.commands or AutoDefault

        self.log.info(f"commands: {' '.join(commands)}")

        for cmd in commands:
            self.run_command_string(cmd)

        self.log_time_stats(header="Finished")

    @TimeStat.log
    def QmC(self, algorithm="Dense3", checks=True):
        if algorithm == "Sparse":
            raise NotImplementedError(
                "QmC:Sparse not implemented, use QmC:Dense2 or QmC:Dense3"
            )
        elif algorithm == "Dense2":
            QMC = Quine_McCluskey_Step1_Dense2
        elif algorithm == "Dense3":
            QMC = Quine_McCluskey_Step1_Dense3
        else:
            raise NotImplementedError(algorithm)

        if not self.force and self.pool.system.is_complete_lower:
            self.log.info("reusing complete system")
            self.pool.system.log_info()
            return

        self.log.info(f"calling Quine-McCluskey algorithm {QMC.__name__}")
        t0 = time()
        cubes = TimeStat(QMC)(self.cubespace)
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
                from subsets import DenseSet
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


def main():
    return ToolQMC().main()


if __name__ == '__main__':
    main()
