import os
import sys

import argparse

from enum import Enum

from binteger import Bin
from subsets import DenseSet
from subsets.SparseSet import SparseSet
from subsets.misc import Quine_McCluskey_Step1 as QMC1

from optimodel.pool import ConstraintPool
from optimodel.clause import AndClause, OrClause
from optimodel.tool import BaseTool

import justlogs
import logging

# sage/pure python compatibility
try:
    import sage.all
except ImportError:
    pass


AutoSelect = (
    "SubsetGreedy:",
    "SubsetWriteMILP:solver=sage/glpk",
    "SubsetMILP:solver=sage/glpk",
)


class Format(Enum):
    CNF = "cnf"
    DNF = "dnf"


class ToolQMC(BaseTool):
    log = logging.getLogger(__name__)

    def main(self):
        justlogs.setup(level="INFO")

        parser = argparse.ArgumentParser(
            description="""Generate CNF or DNF to model a set.""".strip()
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force Quine-McCluskey algorithm call (ignore cache)"
        )
        parser.add_argument("--cnf", action="store_true")
        parser.add_argument("--dnf", action="store_true")
        parser.add_argument(
            "fileprefix", type=str,
            help="Sets prefix "
            "(files with appended .good.set, .bad.set, .type_good must exist) "
            "or one .set file",
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
        if self.fileprefix.endswith(".set"):
            points_good = DenseSet.load_from_file(self.fileprefix)
            self.fileprefix = self.fileprefix.removesuffix(".set")
        else:
            points_good = None
            assert os.path.exists(self.fileprefix + ".good.set")
            assert os.path.exists(self.fileprefix + ".bad.set")
            assert os.path.exists(self.fileprefix + ".type_good")

        justlogs.addFileHandler(self.fileprefix + f".log.{format}")

        self.log.info(args)

        if points_good:
            self.log.info(
                f"using single set (generic) from {self.fileprefix}.set"
            )
            self.pool = ConstraintPool(
                points_good=points_good,
                points_bad=points_good.Complement(),
                swap=(self.format == Format.DNF),
                sysfile=f"{self.fileprefix}.{self.format.value}.system",
            )
        else:
            self.log.info(
                f"using good-bad-type_good sets from prefix {self.fileprefix}"
            )
            self.pool = ConstraintPool.from_DenseSet_files(
                fileprefix=self.fileprefix,
                expand_monotone=True,
                swap=(self.format == Format.DNF),
                sysfile=f"{self.fileprefix}.{self.format.value}.system",
            )
        n = self.pool.n
        if args.force or not self.pool.system.is_complete:
            self.log.info("calling Quine-McCluskey (DenseSet-based)")
            cubes = QMC1(self.pool._bad_orig)
            self.log.info("done Quine-McCluskey")

            for a, u in cubes:
                a = Bin(a, n)
                u = Bin(u, n)
                assert a & u == 0
                # a + lowerset(u) subseteq BAD
                rem_clause = []
                for i in range(n):
                    if u[i] == 0:  # non-wildcard
                        if a[i] == 0:
                            rem_clause.append(-(i+1))
                        else:
                            rem_clause.append((i+1))
                rem_clause = AndClause(rem_clause)  # subseteq BAD
                keep_clause = ~rem_clause  # superseteq GOOD

                cube = rem_clause.solutions(n).to_Bins()

                if 1:
                    d = DenseSet(n)
                    d.set(u.int)
                    d.do_LowerSet()
                    d.do_Not(a.int)
                    assert rem_clause.solutions(n).to_Bins() == d.to_Bins()
                    for v in cube:
                        assert rem_clause.satisfy(v)

                fset = SparseSet([self.pool.bad2i[p] for p in cube])
                self.pool.system.add_lower(vec=fset, meta=keep_clause, is_prime=True)

            self.pool.system.set_complete()
            self.pool.system.save()
        else:
            self.log.info("reusing complete system")
            self.pool.system.log_info()

        self.output_prefix = args.fileprefix + "." + self.format.value.lower()
        self.log.info(f"using output prefix {self.output_prefix}")

        commands = args.commands or AutoSelect

        self.log.info(f"commands: {' '.join(commands)}")

        for cmd in commands:
            self.run_command_string(cmd)

    def AutoSelect(self):
        for cmd in AutoSelect:
            self.run_command_string(cmd)

    def SubsetGreedy(self, *args, **kwargs):
        res = self.pool.choose_subset_greedy(*args, **kwargs)
        self.save(res, kind="clauses", limit=50)

    def SubsetMILP(self, *args, **kwargs):
        res = self.pool.choose_subset_milp(*args, **kwargs)
        self.save(res, kind="clauses", limit=50)

    def SubsetWriteMILP(self, *args, **kwargs):
        prefix = self.fileprefix + ".lp"
        os.makedirs(prefix, exist_ok=True)
        filename = os.path.join(prefix, "full.lp")

        self.pool.write_subset_milp(filename=filename, **kwargs)

    def _output_one(self, clause):
        if self.format == Format.DNF:
            clause = ~clause
        return super()._output_one(clause)


def main():
    return ToolQMC().main()


if __name__ == '__main__':
    main()
