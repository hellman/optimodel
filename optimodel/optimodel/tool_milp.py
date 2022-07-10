import os
import sys

import argparse
from argparse import RawTextHelpFormatter

from monolearn import Modules as LearnModules

from optimodel.pool import ConstraintPool
from optimodel.shift_learn import ShiftLearn
from optimodel.lp_oracle import LPbasedOracle, LPXbasedOracle
from optimodel.tool import BaseTool

import justlogs, logging

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

AutoShifts = (
    "AutoChain",
    "ShiftLearn:threads=7",
    "AutoSelect",
)


class ToolMILP(BaseTool):
    log = logging.getLogger(__name__)

    def main(self):
        TOOL = os.path.basename(sys.argv[0])

        justlogs.setup(level="INFO")

        parser = argparse.ArgumentParser(description=f"""
    Generate inequalities to model a set.
    AutoSimple: alias for
        {" ".join(AutoSimple)}
    AutoSelect: alias for
        {" ".join(AutoSelect)}
    AutoShifts: alias for
        {" ".join(AutoShifts)}
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

        assert os.path.exists(self.fileprefix + ".good.set")
        assert os.path.exists(self.fileprefix + ".bad.set")
        assert os.path.exists(self.fileprefix + ".type_good")

        justlogs.addFileHandler(self.fileprefix + f".log.{TOOL}")

        self.log.info(args)

        self.pool = ConstraintPool.from_DenseSet_files(
            fileprefix=self.fileprefix,
        )
        self.oracle = LPXbasedOracle(pool=self.pool)

        commands = args.commands
        if self.pool.is_monotone:
            commands = commands or AutoSimple
        else:
            commands = commands or AutoShifts

        self.log.info(f"commands: {' '.join(commands)}")

        self.output_prefix = args.fileprefix + ".ineqs"
        self.log.info(f"using output prefix {self.output_prefix}")

        self.chain = []

        for cmd in commands:
            self.run_command_string(cmd)

    def Chain(self, module, *args, **kwargs):
        self.chain.append((module, args, kwargs))

    def AutoSimple(self):
        for cmd in AutoSimple:
            self.run_command_string(cmd)

    def AutoShifts(self):
        for cmd in AutoShifts:
            self.run_command_string(cmd)

    def AutoSelect(self):
        for cmd in AutoSelect:
            self.run_command_string(cmd)

    def AutoChain(self):
        for cmd in AutoChain:
            self.run_command_string(cmd)

    def Learn(self, module, *args, **kwargs):
        if module not in LearnModules:
            raise KeyError(f"Learn module {module} is not registered")
        self.module = LearnModules[module](*args, **kwargs)
        self.module.init(system=self.pool.system, oracle=self.oracle)
        self.module.learn()

    def ShiftLearn(self, threads):
        path = self.fileprefix + ".shifts"
        os.makedirs(path, exist_ok=True)
        sl = ShiftLearn(
            pool=self.pool,
            path=path,
            learn_chain=self.chain,
        )
        sl.process_all_shifts(threads=threads)
        sl.compose()

    def SubsetGreedy(self, *args, **kwargs):
        res = self.pool.choose_subset_greedy(*args, **kwargs)
        self.save(res, kind="inequalities", limit=50)

    def SubsetMILP(self, *args, **kwargs):
        res = self.pool.choose_subset_milp(*args, **kwargs)
        self.save(res, kind="inequalities", limit=50)

    def SubsetWriteMILP(self, *args, **kwargs):
        prefix = self.fileprefix + ".lp"
        os.makedirs(prefix, exist_ok=True)
        filename = os.path.join(prefix, "full.lp")

        self.pool.write_subset_milp(filename=filename, **kwargs)

    #     "Polyhedron": NotImplemented,


def main():
    return ToolMILP().main()


if __name__ == '__main__':
    main()
