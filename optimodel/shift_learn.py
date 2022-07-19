import os
import logging
import multiprocessing
from collections import defaultdict
from functools import reduce

from binteger import Bin

from subsets import DenseSet
from monolearn.SparseSet import SparseSet

from monolearn import Modules as LearnModules

from optimodel.constraint_pool import ConstraintPool
from optimodel.lp_oracle import LPbasedOracle

from optimodel.inequality import Inequality

# multiprocessing is nuts
HACK = None


def worker(shift):
    return HACK.worker(shift)


class ShiftLearn:
    log = logging.getLogger(__name__)

    def __init__(self, pool, path, learn_chain):
        self.pool = pool
        if self.pool.is_upper or self.pool.direction is not None:
            # convert to generic? tool
            raise ValueError(
                "ShiftLearn is only applicable to generic non-shifted sets"
            )

        # NB: for now, only binary sets are supported!
        # otherwise, need to compute lower/upper sets inside given sets
        self.include = DenseSet(
            self.pool.n, [Bin(v).int for v in self.pool.include])
        self.exclude = DenseSet(
            self.pool.n, [Bin(v).int for v in self.pool.exclude])

        self.path = path
        self.learn_chain = learn_chain
        assert os.path.isdir(self.path)

    def process_all_shifts(self, threads=1):
        if self.pool.system.is_complete:
            self.log.warning("system is complete, nothign to learn...")
            return

        self.counts = defaultdict(int)
        self.core = {}  # sanity check
        self.solutions = {}

        if threads == 1:
            for new_origin in self.exclude.to_Bins():
                new_origin = new_origin.tuple
                self.log.info(
                    f"processing reorientation from {new_origin}"
                )
                core, solutions = self.process_origin(new_origin)

                self.log.info(f"merging solutions for origin {new_origin}")
                for vec in solutions:
                    if vec not in self.core:
                        self.core.setdefault(vec, core[vec])
                    assert self.core[vec] == core[vec]
                    self.counts[vec] += 1
                self.solutions.update(solutions)
        else:
            shifts = list(self.exclude.to_Bins())

            global HACK
            HACK = self
            p = multiprocessing.Pool(processes=threads)
            for new_origin, core, solutions in p.imap_unordered(worker, shifts):
                self.log.info(f"merging solutions of new_origin {new_origin}")
                for vec in solutions:
                    if vec not in self.core:
                        self.core.setdefault(vec, core[vec])
                    assert self.core[vec] == core[vec]
                    self.counts[vec] += 1
                self.solutions.update(solutions)

    def compose(self):
        self.log.info("composing")
        for vec, ineq in self.solutions.items():
            if self.counts[vec] == 2**self.core[vec].weight:
                self.pool.system.add_lower(vec, meta=ineq, is_prime=True)
        self.pool.system.save()

    def worker(self, shift: Bin):
        core, solutions = self.process_origin(shift)
        return shift, core, solutions

    def process_origin(self, new_origin: Bin):
        subpool = self.process_origin_get_subpool(new_origin)
        self.log.info(f"extracting solutions for origin {new_origin}")
        core, solutions = self.extract_subpool_solutions(subpool)
        return core, solutions

    def process_origin_get_subpool(self, origin: tuple[int]):
        shift = Bin(origin)
        direction = [-1 if v == 1 else 1 for v in origin]
        # (1, 0) -> (-1,1)

        # xor
        assert len(origin) == self.pool.n
        s = self.include.copy()
        s.do_Not(shift.int)
        s.do_UpperSet()
        good = s.MinSet()
        s.do_Complement()
        removable = s
        good.do_Not(shift.int)  # subpool will shift again..

        bad = self.exclude.copy()
        bad.do_Not(shift.int)
        bad &= removable
        # bad.do_LowerSet()  # unnecessary?! optimization
        bad.do_Not(shift.int)  # subpool will shift again..

        # good is MinSet of the upper closure
        # bad is what can be removed within this shift
        #          (subset of the removable lower set)

        self.log.info(f"shift {shift.hex} good (MinSet)        {good}")
        self.log.info(f"shift {shift.hex} removable (LowerSet) {removable}")
        self.log.info(f"shift {shift.hex} bad (&LowerSet)      {bad}")

        subpool = ConstraintPool(
            include=[v.tuple for v in good.to_Bins()],
            exclude=[v.tuple for v in bad.to_Bins()],
            direction=direction,
            is_upper=True,
            use_point_prec=True,
            sysfile=os.path.join(self.path, f"shift_{shift.hex}.system"),
            constraint_class=Inequality,
        )
        self.learn_origin(subpool)
        return subpool

    def learn_origin(self, subpool):
        for module, args, kwargs in self.learn_chain:
            if module not in LearnModules:
                raise KeyError(f"Learn module {module} is not registered")

            oracle = LPbasedOracle(pool=subpool)
            self.module = LearnModules[module](*args, **kwargs)
            self.module.init(system=subpool.system, oracle=oracle)
            self.module.learn()

    def extract_subpool_solutions(self, subpool):
        solutions = {}
        core = {}
        for fset, cons_pool, cons_final in subpool.constraints:
            qsi = [Bin(subpool.i2exc[i], self.pool.n).int for i in fset]

            d = DenseSet(self.pool.n, qsi)
            assert d == d.LowerSet(), "temporary assert for no don't care case"
            dmax = d.MaxSet().to_Bins()
            dand = reduce(lambda a, b: a & b, dmax)

            # map points from subpool to the main pool
            # invert orientation (it's involution)
            mainvec = SparseSet(
                self.pool.exc2i[subpool.reorient_point(subpool.i2exc[i])]
                for i in fset
            )

            core[mainvec] = dand
            solutions[mainvec] = cons_final
        return core, solutions
