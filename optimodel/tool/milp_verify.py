import os
import sys
import ast
from tqdm import tqdm

import argparse
from argparse import RawTextHelpFormatter

from subsets import DenseSet

from optimodel.pool import InequalitiesPool, TypeGood
from optimodel.base import satisfy

import justlogs, logging

# sage/pure python compatibility
try:
    import sage.all
except ImportError:
    pass

def tool_verify_milp_main():

    # OUTDATED, NEE TO UPDATE FOR NEW API

    log = logging.getLogger(__name__)
    TOOL = os.path.basename(sys.argv[0])

    justlogs.setup(level="INFO")

    parser = argparse.ArgumentParser(
        description="Verify inequalities to model a set."
    )

    parser.add_argument(
        "fileprefix", type=str,
        help="Sets prefix "
        "(files with appended .good.set, .bad.set, .type_good must exist)",
    )
    parser.add_argument(
        "ineqfile", type=str,
        help="File with inequalities",
    )

    args = parser.parse_args()

    fileprefix = args.fileprefix

    assert os.path.exists(fileprefix + ".good.set")
    assert os.path.exists(fileprefix + ".bad.set")
    assert os.path.exists(fileprefix + ".type_good")

    justlogs.addFileHandler(fileprefix + f".log.{TOOL}")

    log.info(args)

    #pool = InequalitiesPool.from_DenseSet_files(fileprefix=fileprefix)

    good = DenseSet.load_from_file(fileprefix + ".good.set")
    bad = DenseSet.load_from_file(fileprefix + ".bad.set")

    with open(fileprefix + ".type_good") as f:
        type_good = TypeGood(f.read().strip())

    log.info(f"points_good: {good}")
    log.info(f" points_bad: {bad}")
    log.info(f"  type_good: {type_good}")

    ineqs = [ast.literal_eval(v) for v in open(args.ineqfile, "r")]

    log.info("verifying good points")
    for q in tqdm(good.to_Bins()):
        assert all(satisfy(q, ineq) for ineq in ineqs)

    log.info("verifying bad points")
    for q in tqdm(bad.to_Bins()):
        assert any(not satisfy(q, ineq) for ineq in ineqs)

    if type_good != TypeGood.GENERIC:
        log.info("verifying monotonic closures")

        log.info(f"points_good: {good}")
        log.info(f"points_bad: {bad}")
        if type_good == TypeGood.UPPER:
            good.do_UpperSet()
            bad.do_LowerSet()
        elif type_good == TypeGood.LOWER:
            good.do_LowerSet()
            bad.do_UpperSet()
        else:
            raise
        log.info(f"points_good: {good}")
        log.info(f"points_bad: {bad}")

        log.info("verifying good points")
        for q in tqdm(good.to_Bins()):
            assert all(satisfy(q, ineq) for ineq in ineqs)

        log.info("verifying bad points")
        for q in tqdm(bad.to_Bins()):
            assert any(not satisfy(q, ineq) for ineq in ineqs)


if __name__ == '__main__':
    tool_verify_milp_main()
