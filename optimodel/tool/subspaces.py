import os
from binteger import Bin

import argparse
from argparse import RawTextHelpFormatter

from monolearn import Modules as LearnModules
from monolearn.utils import TimeStat
from monolearn.LowerSetLearn import ExtraPrec
from monolearn.SparseSet import SparseSet
from monolearn import Oracle

from optimodel.constraint_pool import ConstraintPool
from optimodel.shift_learn import ShiftLearn
from optimodel.lp_oracle import LPbasedOracle
from optimodel.inequality import Inequality

from optimodel.tool.constraint_base import ConstraintTool
from optimodel.tool.set_files import read_set, SetType, TypeGood

from optisolveapi.milp import MILP

import justlogs
import logging
# logging.getLogger("monolearn.GainanovSAT").setLevel(logging.DEBUG)

# sage/pure python compatibility
try:
    import sage.all
except ImportError:
    pass


AutoSimple = (
    "Learn:LevelLearn,levels_lower=3",
    # "Learn:RandomLower:max_repeat_rate=3",
    # min vs None?
    "Learn:GainanovSAT,sense=min,save_rate=100,solver=pysat/cadical",
    "AutoSelect",
)

AutoChain = (
    "Chain:LevelLearn,levels_lower=3",
    "Chain:GainanovSAT,sense=min,save_rate=100,solver=pysat/cadical",
)

# AutoShifts = (
#     "AutoChain",
#     "ShiftLearn:threads=7",
#     "AutoSelect",
# )


class ExtraPrec_Subspace(ExtraPrec):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        N = len(self.int2point)
        #n = len(self.int2point[0])
        self.int2point = [Bin(p) for p in self.int2point]
        self.point2int = {p: i for i, p in enumerate(self.int2point)}

    def reduce(self, vec: SparseSet, return_skipped=False):
        """Subspace basis"""
        if not vec:
            if return_skipped:
                return vec, 0
            else:
                return vec

        res = set()
        qs = [self.int2point[i] for i in vec]
        qs0 = qs[:]
        assert all(isinstance(q, Bin) for q in qs)
        # for q in qs:
        #     print(q)
        # print()

        n = qs[0].n

        offset = qs[0]
        qs = [q ^ offset for q in qs]
        qs = [q for q in qs if q]
        for p in qs:
            t = p ^ offset
            assert t in self.point2int

        # Gaussian Elimination
        basis = []
        mat = list(map(list, enumerate(qs)))
        top = 0
        for i in range(n):
            for j in range(top, len(mat)):
                if mat[j][1][i] == 1:
                    basis.append(qs[mat[j][0]])
                    mat[top], mat[j] = mat[j], mat[top]
                    for k in range(top+1, len(mat)):
                        if mat[k][1][i] == 1:
                            #print(mat[k], mat[top])
                            mat[k][1] ^= mat[top][1]
                    top += 1
                    break
            mat = [[ind, q] for ind, q in mat if q]
        # print(qs)

        n_skipped = 0
        basis.append(Bin(0, n))
        for p in basis:
            t = p ^ offset
            if t in self.point2int:
                res.add(self.point2int[t])
            else:
                n_skipped += 1
                assert 0
        # print("GE")
        # for q in qs:
        #     print(q ^ offset)
        # print("reduce", len(vec), "->", len(qs), "->", len(res), ":", qs0, [offset ^ p for p in qs])
        if return_skipped:
            return SparseSet(res), n_skipped
        else:
            return SparseSet(res)

    def expand(self, vec: SparseSet, return_skipped=False):
        """Span of vectors"""
        if not vec:
            if return_skipped:
                return vec, 0
            else:
                return vec

        res = set()
        qs = [self.int2point[i] for i in vec]
        assert all(isinstance(q, Bin) for q in qs)

        n = qs[0].n

        offset = qs[0]
        qs = [q ^ offset for q in qs]
        qs = [q for q in qs if q]

        span = set(Bin(0, n))
        for q in qs:
            if q not in span:
                for p in list(span):
                    span.add(p ^ q)

        n_skipped = 0
        for p in span:
            t = p ^ offset
            if t in self.point2int:
                res.add(self.point2int[t])
            else:
                n_skipped += 1
        # print("expand", len(vec), "->", len(span), "->", len(res))
        if return_skipped:
            return SparseSet(res), n_skipped
        else:
            return SparseSet(res)


class ToolSubspaces(ConstraintTool):
    KIND = "subspace"

    log = logging.getLogger(__name__)

    def main(self):
        justlogs.setup(level="INFO")

        parser = argparse.ArgumentParser(description=f"""
    Generate subspaces to model a set.
    AutoSimple: alias for
        {" ".join(AutoSimple)}
    AutoSelect: alias for automatic subset selection (depends on system's size)
    # AutoShifts: alias for
    #     {{" ".join(AutoShifts)}}
    AutoChain: alias for
        {" ".join(AutoChain)}
        """.strip(), formatter_class=RawTextHelpFormatter)

        parser.add_argument(
            "fileprefix", type=str,
            help="Sets prefix "
            "(files with appended .good.set, .bad.set, .type_good must exist)",
        )
        parser.add_argument(
            "commands", type=str, nargs="*",
            help="Commands with options (available: Learn:* ???)",
        )

        args = self.args = parser.parse_args()

        self.fileprefix = args.fileprefix
        if os.path.isdir(self.fileprefix):
            self.fileprefix += "/"

        self.output_prefix = self.fileprefix + "subspaces."

        justlogs.addFileHandler(self.fileprefix + "log")
        self.log.debug(f"MILP solver: {MILP.DEFAULT_SOLVER}")  # causes the choice to be logged

        self.log.info(args)
        self.log.info(f"using output prefix {self.output_prefix}")

        self.sysfile = self.output_prefix + "system.bz2"

        include = read_set(self.fileprefix + "include")
        exclude = read_set(self.fileprefix + "exclude")
        typ = SetType.read_from_file(self.fileprefix + "type")

        for v in exclude:
            n = len(v)
            break
        else:
            raise ValueError("exclude should be nonempty")

        self.log.info(f"set type: {typ}, n {n}")

        if typ.type_good == TypeGood.EXPLICIT or 1:
            direction = None
            is_upper = False
            self.log.info("EXPLICIT set")
        elif typ.type_good == TypeGood.UPPER:
            # direction = None
            # is_upper = True
            # self.log.info("monotone UPPER set")
            self.log.warning("UPPER sets not optimized yet, using EXPLICIT")
        elif typ.type_good == TypeGood.LOWER:
            # direction = (-1,)*n
            # is_upper = True
            # self.log.info("monotone LOWER set, reorienting to an upper set")
            self.log.warning("LOWER sets not optimized yet, using EXPLICIT")
        else:
            raise NotImplementedError(typ)

        self.pool = ConstraintPool(
            include=include,
            exclude=exclude,
            direction=direction,
            is_upper=is_upper,
            use_point_prec=ExtraPrec_Subspace,
            sysfile=self.sysfile,
            output_prefix=self.output_prefix,
            constraint_class=Inequality,
        )
        self.oracle = SubspaceOracle(pool=self.pool)

        commands = args.commands
        commands = commands or AutoSimple

        self.log.info(f"commands: {' '.join(commands)}")

        self.chain = []

        for cmd in commands:
            self.run_command_string(cmd)

        self.log_time_stats(header="Finished")


    def Chain(self, module, *args, **kwargs):
        self.chain.append((module, args, kwargs))

    def AutoSimple(self):
        for cmd in AutoSimple:
            self.run_command_string(cmd)

    # def AutoShifts(self):
    #     for cmd in AutoShifts:
    #         self.run_command_string(cmd)

    # def AutoChain(self):
    #     for cmd in AutoChain:
    #         self.run_command_string(cmd)

    def Learn(self, module, *args, **kwargs):
        if module not in LearnModules:
            raise KeyError(f"Learn module {module} is not registered")
        self.module = LearnModules[module](*args, **kwargs)
        self.module.init(system=self.pool.system, oracle=self.oracle)
        self.module.learn()

        self.log_time_stats(header=f"Learn:{module}")

    # @TimeStat.log
    # def ShiftLearn(self, threads):
    #     path = self.fileprefix + "shifts"
    #     os.makedirs(path, exist_ok=True)
    #     sl = ShiftLearn(
    #         pool=self.pool,
    #         path=path,
    #         learn_chain=self.chain,
    #     )
    #     sl.process_all_shifts(threads=threads)
    #     sl.compose()


def main():
    return ToolSubspaces().main()


class SubspaceOracle(Oracle):
    def __init__(self, pool):
        super().__init__()

        self.pool = pool

    def _query(self, bads: SparseSet):
        assert isinstance(bads, SparseSet)
        ext, skipped = self.pool.system.extra_prec.expand(bads, return_skipped=True)
        if skipped:
            # print("query", len(bads), "->", "false", "|", len(bads), len(ext), skipped)
            # print()
            return False, None
        basis = self.pool.system.extra_prec.reduce(bads, return_skipped=False)
        # print("query", len(bads), bads, "->", "true")
        # print()
        return True, basis


if __name__ == '__main__':
    main()
