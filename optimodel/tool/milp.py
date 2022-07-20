import os

import argparse
from argparse import RawTextHelpFormatter

from monolearn import Modules as LearnModules
from monolearn.utils import TimeStat

from optimodel.constraint_pool import ConstraintPool
from optimodel.shift_learn import ShiftLearn
from optimodel.lp_oracle import LPbasedOracle
from optimodel.inequality import Inequality

from optimodel.tool.constraint_base import ConstraintTool
from optimodel.tool.set_files import read_set, SetType, TypeGood

from optisolveapi.milp import MILP

import justlogs
import logging

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

AutoShifts = (
    "AutoChain",
    "ShiftLearn:threads=7",
    "AutoSelect",
)


class ToolMILP(ConstraintTool):
    KIND = "ineq"

    log = logging.getLogger(__name__)

    def main(self):
        justlogs.setup(level="INFO")

        parser = argparse.ArgumentParser(description=f"""
    Generate inequalities to model a set.
    AutoSimple: alias for
        {" ".join(AutoSimple)}
    AutoSelect: alias for automatic subset selection (depends on system's size)
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
        if os.path.isdir(self.fileprefix):
            self.fileprefix += "/"

        self.output_prefix = self.fileprefix + "ineq."

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

        if typ.type_good == TypeGood.UPPER:
            direction = None
            is_upper = True
            self.log.info("monotone UPPER set")
        elif typ.type_good == TypeGood.LOWER:
            direction = (-1,)*n
            is_upper = True
            self.log.info("monotone LOWER set, reorienting to an upper set")
        elif typ.type_good == TypeGood.EXPLICIT:
            direction = None
            is_upper = False
            self.log.info("EXPLICIT set")
        else:
            raise NotImplementedError(typ)

        self.pool = ConstraintPool(
            include=include,
            exclude=exclude,
            direction=direction,
            is_upper=is_upper,
            use_point_prec=False,
            sysfile=self.sysfile,
            output_prefix=self.output_prefix,
            constraint_class=Inequality,
        )
        self.oracle = LPbasedOracle(pool=self.pool)

        commands = args.commands
        if self.pool.is_upper:
            commands = commands or AutoSimple
        else:
            commands = commands or AutoShifts

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

    def AutoShifts(self):
        for cmd in AutoShifts:
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

        self.log_time_stats(header=f"Learn:{module}")

    @TimeStat.log
    def ShiftLearn(self, threads):
        path = self.fileprefix + "shifts"
        os.makedirs(path, exist_ok=True)
        sl = ShiftLearn(
            pool=self.pool,
            path=path,
            learn_chain=self.chain,
        )
        sl.process_all_shifts(threads=threads)
        sl.compose()


def main():
    return ToolMILP().main()


if __name__ == '__main__':
    main()
