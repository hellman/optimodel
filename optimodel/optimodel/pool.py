from random import choice
from math import ceil
from enum import Enum

from binteger import Bin

from subsets import DenseSet
from monolearn import LowerSetLearn, ExtraPrec_LowerSet

from optisolveapi.milp import MILP
from optisolveapi.milp.symbase import LPwriter

import logging


class TypeGood(Enum):
    LOWER = "lower"
    UPPER = "upper"
    GENERIC = "-"


class ConstraintPool:
    log = logging.getLogger(f"{__name__}:ConstraintPool")

    @classmethod
    def from_DenseSet_files(
        cls,
        fileprefix,
        checks=True,
        expand_monotone=False,
        **opts,
    ):
        opts.setdefault("sysfile", fileprefix + ".system")

        points_good = DenseSet.load_from_file(fileprefix + ".good.set")
        points_bad = DenseSet.load_from_file(fileprefix + ".bad.set")

        with open(fileprefix + ".type_good") as f:
            type_good = TypeGood(f.read().strip())

        cls.log.info(f"points_good: {points_good}")
        cls.log.info(f" points_bad: {points_bad}")
        cls.log.info(f"  type_good: {type_good}")

        if checks:
            if type_good == TypeGood.LOWER:
                assert points_bad <= points_good.LowerSet().Complement()
            elif type_good == TypeGood.UPPER:
                assert points_bad <= points_good.UpperSet().Complement()
            elif type_good == TypeGood.GENERIC:
                assert (points_good & points_bad).is_empty()
                # not necessary ("don't care" points)
                # assert (points_good | points_bad).is_full()

        if expand_monotone and type_good != TypeGood.GENERIC:
            if type_good == TypeGood.LOWER:
                cls.log.info("expanding monotone (good is lower set)")
                points_good = points_good.LowerSet()
                points_bad = points_bad.UpperSet()
            elif type_good == TypeGood.UPPER:
                cls.log.info("expanding monotone (bad is upper set)")
                points_good = points_good.UpperSet()
                points_bad = points_bad.LowerSet()
            else:
                raise

            type_good = TypeGood.GENERIC

            if checks:
                assert (points_good & points_bad).is_empty()

            cls.log.info(f"points_good: {points_good}")
            cls.log.info(f" points_bad: {points_bad}")
            cls.log.info(f"  type_good: {type_good}")

        pool = cls(
            points_good=points_good,
            points_bad=points_bad,
            type_good=type_good,
            **opts
        )
        if opts.get("swap", False):
            assert pool.N == len(points_good)
        else:
            assert pool.N == len(points_bad)
        return pool

    def __init__(
        self,
        points_good: tuple,
        points_bad: tuple,
        type_good: TypeGood = TypeGood.GENERIC,
        *,
        n=None,
        use_point_prec=False,
        sysfile=None,
        pre_shift=0,
        swap=False,
    ):
        if swap:
            self.log.info("swapping good and bad...")

            points_bad, points_good = points_good, points_bad
            if type_good == TypeGood.UPPER:
                type_good = TypeGood.LOWER
            elif type_good == TypeGood.LOWER:
                type_good = TypeGood.UPPER

        assert points_bad, "no bad points? nothing to do..."

        if isinstance(points_bad, DenseSet):
            self.n = points_bad.n
        else:
            for p in points_bad:
                if isinstance(p, Bin):
                    self.n = p.n
                else:
                    self.n = len(p)
                break
        assert self.n > 0

        self._good_orig = points_good
        self._bad_orig = points_bad
        self.bad = {Bin(v, self.n) for v in points_bad}
        self.good = {Bin(v, self.n) for v in points_good}

        assert pre_shift is None or isinstance(pre_shift, (int, Bin))
        pre_shift = Bin(pre_shift, self.n)

        if type_good == TypeGood.GENERIC:
            self.is_monotone = False
            self.shift = None
            assert pre_shift in (0, None)

        elif type_good == TypeGood.LOWER:
            self.is_monotone = True
            self.shift = pre_shift ^ ~Bin(0, self.n)
            self.bad = {~v for v in self.bad}
            self.good = {~v for v in self.good}

        elif type_good == TypeGood.UPPER:
            self.is_monotone = True
            self.shift = pre_shift

        else:
            assert 0, type_good

        self.i2bad = sorted(self.bad, key=lambda v: v.int)
        self.bad2i = {p: i for i, p in enumerate(self.i2bad)}
        self.N = len(self.bad)

        if use_point_prec:
            assert self.is_monotone
            ep = ExtraPrec_LowerSet(
                int2point=self.i2bad,
                point2int=self.bad2i,
            )
        else:
            ep = None
        self.use_point_prec = use_point_prec

        self.system = LowerSetLearn(
            n=self.N,
            file=sysfile,
            extra_prec=ep,
        )

    # tbd:
    # port polyhedron

    def _output_results(self, vecs):
        self.log.info(
            f"sanity checking {len(vecs)} ineqs on "
            f"{len(self.good)} good and "
            f"{len(self.bad)} bad points..."
        )
        ineqs = [self.system.meta[vec] for vec in vecs]
        for q in self.good:
            assert all(ineq.satisfy(q) for ineq in ineqs)
        for q in self.bad:
            assert any(not ineq.satisfy(q) for ineq in ineqs)

        self.log.info(f"processing ineqs (shifting by {self.shift})...")
        return list(map(self._output_one, ineqs))

    def _output_one(self, ineq):
        if self.shift:
            ineq = ineq.shift(self.shift)
        return ineq

    def choose_all(self):
        self.log.info(
            "InequalitiesPool.choose_all()"
        )
        return self._output_results(list(self.system.iter_lower()))

    def create_subset_milp(self, solver=None):
        """
        [SecITC:SasTod17]
        Choose subset optimally by optimizing MILP system.
        """
        self.log.info(
            f"InequalitiesPool.create_subset_milp(solver={solver})"
        )
        self.log.info(
            f"{self.system.n_lower()} ineqs {len(self.bad)} bad points"
        )

        vec_order = list(self.system.iter_lower())

        milp = MILP.minimization(solver=solver)
        n = len(vec_order)

        # xi = take i-th inequality?
        v_take_ineq = [milp.var_binary("v_take_ineq%d" % i) for i in range(n)]

        by_bad = [[] for _ in range(self.N)]
        for i, vec in enumerate(vec_order):
            for q in vec:
                by_bad[q].append(v_take_ineq[i])

        # each bad point is removed by at least one ineq
        for lst in by_bad:
            assert lst, "no solutions"
            milp.add_constraint(sum(lst) >= 1)

        # minimize number of ineqs
        milp.set_objective(sum(v_take_ineq))
        return v_take_ineq, vec_order, milp

    def write_subset_milp(self, filename, solver=None):
        assert filename.endswith(".lp")

        v_take_ineq, vec_order, milp = self.create_subset_milp(solver=solver)
        self.log.info(
            f"saving LP with {len(v_take_ineq)} variables (per ineq), "
            f"{len(self.bad)} constraints (per bad point) to {filename}"
        )
        milp.write_lp(filename)

        self.write_subset_milp_meta(
            filename=filename[:-3] + ".meta",
            vec_order=vec_order,
            pre_selected=(),
        )

    def write_subset_milp_meta(self, filename, vec_order, pre_selected):
        M = len(vec_order)
        by_vec = {j: set(vec_order[j]) for j in range(M)}

        with open(filename, "w") as f:
            for i, vec in enumerate(vec_order):
                if vec not in pre_selected and i not in by_vec:
                    continue
                ineq = self._output_one(self.system.meta[vec])
                print(
                    i,
                    ":".join(map(str, vec)),
                    ":".join(map(str, ineq)),
                    int(vec in pre_selected),
                    file=f
                )

    def choose_subset_milp(self, lp_output=None, solver=None):
        v_take_ineq, vec_order, milp = self.create_subset_milp(solver=solver)

        if lp_output:
            self.log.info(
                f"saving LP with {len(v_take_ineq)} variables (per ineq), "
                f"{len(self.bad)} constraints (per bad point) to {lp_output}"
            )
            milp.write_lp(lp_output)

        self.log.info(
            f"solving milp with {len(v_take_ineq)} variables, "
            f"{len(self.bad)} constraints"
        )

        # show log for large problems
        res = milp.optimize(log=(len(v_take_ineq) >= 5000))
        assert res is not None, "insufficient inequalities pool?"
        milpsol = milp.solutions[0]
        self.log.info(f"objective {res}")

        ineqs = [
            vec_order[i] for i, take in enumerate(v_take_ineq) if milpsol[take]
        ]
        return self._output_results(ineqs)

    def choose_subset_greedy_once(
        self, eps=0,
        lp_snapshot_step=None,
        lp_snapshot_format=None,
    ):
        self.log.debug("preparing greedy")

        # tbd update for non-prime option (clean up or ... ?)
        vec_order = list(self.system.iter_lower())
        M = len(vec_order)

        by_vec = {j: set(vec_order[j]) for j in range(M)}
        by_point = {i: [] for i in range(self.N)}
        for j, fset in enumerate(vec_order):
            for i in fset:
                by_point[i].append(j)

        self.log.debug("running greedy")

        n_removed = 0
        Lstar = set()
        while by_vec:
            max_remove = max(map(len, by_vec.values()))
            assert max_remove >= 1

            cands = [
                j for j, rem in by_vec.items()
                if len(rem) >= max_remove - eps
            ]
            j = choice(cands)

            Lstar.add(vec_order[j])
            n_removed += max_remove

            for i in vec_order[j]:
                js = by_point.get(i, ())
                if js:
                    for j2 in js:
                        s = by_vec.get(j2)
                        if s:
                            s.discard(i)
                            if not s:
                                del by_vec[j2]
                    del by_point[i]
            assert j not in by_vec

            lb = len(Lstar) + ceil(self.N / max_remove)
            self.log.debug(
                f"removing {max_remove} points: "
                f"cur {len(Lstar)} ineqs, left {len(by_vec)} ineqs"
                f"removed {n_removed}/{self.N} points; "
                f"bound {lb} ineqs"
            )

            if lp_snapshot_step and len(Lstar) % lp_snapshot_step == 0:
                self.do_greedy_snapshot(
                    vec_order, Lstar, by_vec, by_point,
                    lp_snapshot_format
                )

        self.log.debug(f"greedy result: {len(Lstar)}")
        return self._output_results(Lstar)

    def do_greedy_snapshot(
        self, vec_order, Lstar, by_vec, by_point,
        lp_snapshot_format,
    ):
        prefix = lp_snapshot_format % dict(
            selected=len(Lstar),
            remaining=len(vec_order)
        )

        self.log.info(
            f"snapshot to {prefix} "
            f"(pre-selected={len(Lstar)}, points_left={len(by_point)})"
        )

        self.write_subset_milp_meta(
            filename=prefix + ".meta",
            vec_order=vec_order,
            by_vec=by_vec,
            pre_selected=Lstar,
        )

        lp = LPwriter(filename=prefix + ".lp")

        var_fset = {}
        for j in by_vec:
            var_fset[j] = "x%d" % j  # take ineq j

        lp.objective(
            objective=lp.sum(var_fset.values()),
            sense="minimize",
        )

        for i, js in by_point.items():
            lp.constraint(lp.sum(var_fset[j] for j in js) + " >= 1")

        lp.binaries(var_fset.values())
        lp.close()

    def choose_subset_greedy(self, iterations=10, eps=0):
        self.log.info(
            f"InequalitiesPool.choose_subset_greedy("
            f"iterations={iterations},eps={eps}"
            ")"
        )
        self.log.info(
            f"{self.system.n_lower()} ineqs {len(self.bad)} bad points"
        )

        best = float("+inf"), None
        for itr in range(iterations):
            Lstar = self.choose_subset_greedy_once(eps=eps)

            cur = len(Lstar), Lstar
            self.log.info(f"itr #{itr}: {cur[0]} ineqs")
            if cur < best:
                best = cur
        self.log.info(f"best: {best[0]} inequalities")
        assert best[1] is not None
        return best[1]
