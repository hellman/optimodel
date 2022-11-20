import os
import logging
import subprocess
from random import randrange

# from random import choice
# from math import ceil
from collections import namedtuple

from monolearn import LowerSetLearn, ExtraPrec_LowerSet
from monolearn.utils import dictify_add_class

from optisolveapi.milp import MILP
#from optisolveapi.milp.symbase import LPwriter


log = logging.getLogger(f"{__name__}")


Constraint = namedtuple(
    "Constraint", ["fset", "cons_pool", "cons_final"]
)
Result = namedtuple(
    "Result", ["constraints", "optimal"]
)


def hash_sorted_points(lst):
    mask = 2**128-1
    h = 0xc1b8110707ac03c72f523637091a63d3
    for pt in lst:
        for c in pt:
            h = ((h + c) * 0x3dca7017) ^ h
            h &= mask
            h ^= h >> 17
            h &= mask
        h ^= h >> 27
    return "%032x" % h


NotGiven = object()


class ConstraintPool:
    log = logging.getLogger(f"{__name__}:ConstraintPool")

    def reorient_point(self, pt: tuple[int], direction: tuple[int] = NotGiven):
        if direction is NotGiven:
            direction = self.direction
        if direction is None:
            return pt
        return tuple(
            1 - v if d == -1 else v
            for v, d in zip(pt, direction)
        )

    def __init__(
        self,
        exclude: set[tuple[int]],
        include: set[tuple[int]] = None,
        direction: tuple[int] = None,  # reorient points to make upper set
        is_upper: bool = False,  # include is a upper set (max-set or explicit)
                                 # or generic explicit?
                                 # (after redirection)
        use_point_prec: bool = False,
        sysfile: str = None,
        output_prefix: str = None,
        constraint_class: type = None,
    ):
        for v in exclude:
            self.n = len(v)
            break
        else:
            raise RuntimeError("no exclude points? nothing to do")

        self.direction = direction
        self.is_upper = is_upper

        if self.direction:
            assert self.is_upper, "why redirect if not monotone?"
            self.log.info(
                "reorienting points, direction:"
                f" {' '.join(map(str, direction))}"
            )
        else:
            self.log.info("no reorienting")

        # copy to new sets to ensure it's not modified externally
        self.exclude = sorted(self.reorient_point(v, direction) for v in exclude)
        self.include = (sorted(self.reorient_point(v, direction) for v in include)
                        if include is not None else None)

        hi = hash_sorted_points(self.include) if self.include is not None else -1
        he = hash_sorted_points(self.exclude)

        li = len(self.include) if self.include is not None else "(not given)"
        self.log.info(f"exclude: {len(self.exclude):11} points, hash {he}")
        self.log.info(f"include: {li:11} points, hash {hi}")

        self.i2exc = sorted(self.exclude)
        self.exc2i = {p: i for i, p in enumerate(self.i2exc)}

        self.N = len(self.exclude)

        if use_point_prec:
            assert self.is_upper
            ep = ExtraPrec_LowerSet(
                int2point=self.i2exc,
                point2int=self.exc2i,
            )
        else:
            ep = None
        self.use_point_prec = use_point_prec

        dictify_add_class(constraint_class)
        self.system = LowerSetLearn(
            n=self.N,
            file=sysfile,
            extra_prec=ep,
        )

        self._constraints = None
        self.system_lower = None
        self.system_upper = None

        self.cons2i = None

        self.best_subset_size_ub = 1111111111111111111  # inf
        self.best_subset_size_lb = 1  # inf
        self.best_subset = None

        self.output_prefix = output_prefix

    def finalize(self):
        if self._constraints is not None:
            raise RuntimeError("finalizing ConstraintPool twice (bad practice)")

        self.log.warning(
            "finalizing ConstraintPool's system"
            " for using in subset covers"
        )
        self.system_lower = list(self.system.iter_lower())
        self.system_upper = list(self.system.iter_upper())

        self._constraints = [
            Constraint(
                fset=c,
                cons_pool=self.system.meta[c],
                cons_final=self.constraint_finalize(self.system.meta[c]),
            )
            for c in sorted(self.system.iter_lower())
        ]
        del self.system
        self.cons2i = {c.fset: i for i, c in enumerate(self._constraints)}

        self.log.info("finished finalizing")

    def constraint_finalize(self, cons):
        if self.direction:
            # should never happen to CNF/DNF
            # (not considering lower/upper sets as they are trivial)
            cons = cons.reorient(self.direction)
        return cons

    @property
    def constraints(self):
        if self._constraints is None:
            self.finalize()
        return self._constraints

    def check_subset(self, fsets):
        constrs = [
            self.constraints[self.cons2i[fset]].cons_pool
            for fset in fsets
        ]

        if self.include:
            for q in self.include:
                assert all(cons.satisfy(q) for cons in constrs)
        for q in self.exclude:
            assert any(not cons.satisfy(q) for cons in constrs)

    def write_subset_gecco(self, filename):
        assert filename.endswith(".gecco")

        n_var = self.N
        n_sets = len(self.constraints)

        self.log.info(
            f"saving GECCO with {n_var} variables (per exclude point), "
            f"{n_sets} sets (per constraint) to {filename}"
        )

        by_bad = [[] for _ in range(n_var)]
        for set_i, cons in enumerate(self.constraints):
            for pti in cons.fset:
                by_bad[pti].append(set_i)

        with open(filename, "wt") as f:
            print(n_var, n_sets, file=f)

            for pti, lst in enumerate(by_bad):
                assert lst, "no solutions"
                print(pti, len(lst), *lst, file=f)

        subprocess.check_call(["bzip2", "-k", filename])

    def write_subset_milp(self, filename, solver=None):
        assert filename.endswith(".lp")

        self.log.info("creating MILP instance for writing")

        v_take_ineq, milp = self.create_subset_milp(solver=solver)

        self.log.info(
            f"saving LP with {len(v_take_ineq)} variables (per ineq), "
            f"{len(self.exclude)} constraints (per exclude point) to {filename}"
        )
        milp.write_lp(filename)

        self.write_subset_meta(
            filename=filename.removesuffix(".lp") + ".meta",
            pre_selected=(),
        )

    def write_subset_meta(self, filename, pre_selected=()):
        assert filename.endswith(".meta")

        self.log.info(
            "saving META"
            f" with {len(self.exclude)} variables (per exclude point), "
            f"{len(self.constraints)} sets (per constraint) to {filename}"
        )

        with open(filename, "w") as f:
            for i, cons in enumerate(self.constraints):
                print(
                    i,
                    ":".join(map(str, cons.fset)),
                    ":".join(map(str, cons.cons_final)),
                    int(cons.fset in pre_selected),
                    file=f
                )

    def subset_full(self):
        self.log.info("InequalitiesPool.subset_full()")
        self.report(
            [cons.cons_final for cons in self.constraints],
            source="subset_full",
            optimal=False,
        )

    def create_subset_milp(self, solver=None):
        """
        [SecITC:SasTod17]
        Choose subset optimally by optimizing MILP system.
        """
        self.log.info(
            f"InequalitiesPool.create_subset_milp(solver={solver})"
        )
        self.log.info(
            f"{len(self.constraints)} ineqs {len(self.exclude)} exclude points"
        )

        milp = MILP.minimization(solver=solver)

        # vi = take i-th constraint?
        v_take_ineq = [
            milp.var_binary("v_take_cons%d" % i)
            for i in range(len(self.constraints))
        ]

        by_bad = [[] for _ in range(self.N)]
        for i, vec in enumerate(self.constraints):
            vi = v_take_ineq[i]
            for q in vec.fset:
                by_bad[q].append(vi)

        # each bad point is removed by at least one ineq
        for lst in by_bad:
            assert lst, "no solutions"
            milp.add_constraint(((v, 1) for v in lst), lb=1)

        # minimize number of ineqs
        # todo: compute better lb (is it helpful?)
        obj = [(v, 1) for v in v_take_ineq]
        milp.set_objective(obj)
        if self.best_subset_size_ub < 1111111111111111111:
            self.log.info(f"adding previous upper bound {self.best_subset_size_ub}")
            milp.add_constraint(obj, lb=1, ub=self.best_subset_size_ub)
        else:
            milp.add_constraint(obj, lb=1, ub=self.best_subset_size_ub)
        return v_take_ineq, milp

    def subset_by_milp(self, lp_output=None, solver=None):
        v_take_ineq, milp = self.create_subset_milp(solver=solver)

        if lp_output:
            self.log.info(
                f"saving LP with {len(v_take_ineq)} variables (per ineq), "
                f"{len(self.exclude)} constraints (per exclude point)"
                f" to {lp_output}"
            )
            milp.write_lp(lp_output)

        self.log.info(
            f"solving milp with {len(v_take_ineq)} variables, "
            f"{len(self.exclude)} constraints"
        )

        # show log for large problems
        res = milp.optimize(log=(len(v_take_ineq) >= 5000))
        assert res is not None, "insufficient inequalities pool?"

        self.log.info(f"objective {res}")
        assert abs(res - int(res + 0.001)) <= 0.01, \
            f"objective should be int? {res}"

        milpsol = milp.solutions[0]

        # sanity check
        for i, take in enumerate(v_take_ineq):
            assert milpsol[take] in (0, 1), \
                f"non-integral solution? value {milpsol[take]}"

        constrs = [
            self.constraints[i].cons_final
            for i, take in enumerate(v_take_ineq)
            if milpsol[take]
        ]
        # todo: if using timeout, set optimal accordingly
        self.report(constrs, source="subset_by_milp", optimal=True)

    def subset_by_setcoveringsolver(
        self,
        algorithm="largeneighborhoodsearch_2",
        timeout=120,
        solfile=None,
        geccofile=None,
    ):
        self.log.info(
            f"{len(self.constraints)} constraints/sets"
            f" {len(self.exclude)} exclude points"
        )
        self.log.info(
            f"setcoveringsolver algorithm : {algorithm} timeout : {timeout}"
        )

        seed = randrange(2**30)

        cmd = list(map(str, [
            "setcoveringsolver",
            "--algorithm", algorithm,
            "--input", geccofile,
            "--unicost",
            "--time-limit", timeout,
            "--certificate", solfile,
            "--verbosity", 10,
            "--seed", seed,
            "--log2stderr",
        ]))

        self.log.info("$ " + " ".join(cmd))

        try:
            subprocess.check_call(cmd, timeout=timeout + 5)
        except subprocess.TimeoutExpired as err:
            self.log.error(str(err))
        except subprocess.SubprocessError as err:
            self.log.error(str(err))

        with open(solfile, "r") as f:
            solsize = int(f.readline())
            self.log.info(f"got solution {solsize}")

            sol = list(map(int, f.readline().split()))
            if len(sol) != solsize:
                self.log.warning("size mismatch, corrupted solution?")
                return

        self.report(
            [self.constraints[i].cons_final for i in sol],
            source=f"subset_by_setcoveringsolver:{algorithm},"
                   + f"timeout={timeout},seed={seed}",
            optimal=False
        )

    def report(self, constraints, source, limit=50, optimal=False):
        self.log.info(
            f"got {len(constraints)} constraints"
            f"from {source} (optimal? {optimal})"
        )

        if not self.output_prefix:
            self.log.warning("output prefix not set, not writing")
            return

        filename = f"{self.output_prefix}{len(constraints)}"
        if optimal:
            filename += ".opt"

        if len(constraints) < self.best_subset_size_ub:
            self.best_subset_size_ub = len(constraints)
            self.best_subset = constraints
        elif len(constraints) == self.best_subset_size_ub \
             and optimal \
             and not os.path.isfile(filename):
            # perhaps was not known that it's optimal, let's write down to .opt
            self.best_subset_size_ub = len(constraints)
            self.best_subset = constraints
        else:
            self.log.info(
                "skipping sol with"
                f" {len(constraints)} >= {self.best_subset_size_ub}"
                f" constraints, from {source}"
            )
            return

        # record source
        with open(filename + ".source", "wt") as f:
            print(source, file=f)

        if os.path.exists(filename):
            self.log.warning(f"file {filename} exists, skipping overwrite!")
        else:
            self.log.info(
                f"saving {len(constraints)} constraints to {filename}"
            )
            with open(filename, "w") as f:
                print(len(constraints), file=f)
                for eq in constraints:
                    print(*eq, file=f)
            self.log.info(f"saved {len(constraints)} constraints to {filename}")

        if len(constraints) < limit:
            self.log.info(f"constraints ({len(constraints)}):")
            for cons in constraints:
                self.log.info(f"{cons}")
            self.log.info("end")

    # outdated by the "setcoveringsolver"
    # perhaps worth keeping for self-containedness
    # (also greedy snapshots for bounds)
    # but need to fix
    # due to update vec_order -> self.constraints structure

    # def choose_subset_greedy_once(
    #     self, eps=0,
    #     lp_snapshot_step=None,
    #     lp_snapshot_format=None,
    # ):
    #     self.log.debug("preparing greedy")

    #     # tbd update for non-prime option (clean up or ... ?)
    #     vec_order = list(self.system.iter_lower())
    #     M = len(vec_order)

    #     by_vec = {j: set(vec_order[j]) for j in range(M)}
    #     by_point = {i: [] for i in range(self.N)}
    #     for j, fset in enumerate(vec_order):
    #         for i in fset:
    #             by_point[i].append(j)

    #     self.log.debug("running greedy")

    #     n_removed = 0
    #     Lstar = set()
    #     while by_vec:
    #         max_remove = max(map(len, by_vec.values()))
    #         assert max_remove >= 1

    #         cands = [
    #             j for j, rem in by_vec.items()
    #             if len(rem) >= max_remove - eps
    #         ]
    #         j = choice(cands)

    #         Lstar.add(vec_order[j])
    #         n_removed += max_remove

    #         for i in vec_order[j]:
    #             js = by_point.get(i, ())
    #             if js:
    #                 for j2 in js:
    #                     s = by_vec.get(j2)
    #                     if s:
    #                         s.discard(i)
    #                         if not s:
    #                             del by_vec[j2]
    #                 del by_point[i]
    #         assert j not in by_vec

    #         lb = len(Lstar) + ceil(self.N / max_remove)
    #         self.log.debug(
    #             f"removing {max_remove} points: "
    #             f"cur {len(Lstar)} ineqs, left {len(by_vec)} ineqs"
    #             f"removed {n_removed}/{self.N} points; "
    #             f"bound {lb} ineqs"
    #         )

    #         if lp_snapshot_step and len(Lstar) % lp_snapshot_step == 0:
    #             self.do_greedy_snapshot(
    #                 vec_order, Lstar, by_vec, by_point,
    #                 lp_snapshot_format
    #             )

    #     self.log.debug(f"greedy result: {len(Lstar)}")
    #     return self._output_results(Lstar)

    # def do_greedy_snapshot(
    #     self, vec_order, Lstar, by_vec, by_point,
    #     lp_snapshot_format,
    # ):
    #     prefix = lp_snapshot_format % dict(
    #         selected=len(Lstar),
    #         remaining=len(vec_order)
    #     )

    #     self.log.info(
    #         f"snapshot to {prefix} "
    #         f"(pre-selected={len(Lstar)}, points_left={len(by_point)})"
    #     )

    #     self.write_subset_milp_meta(
    #         filename=prefix + ".meta",
    #         vec_order=vec_order,
    #         by_vec=by_vec,
    #         pre_selected=Lstar,
    #     )

    #     lp = LPwriter(filename=prefix + ".lp")

    #     var_fset = {}
    #     for j in by_vec:
    #         var_fset[j] = "x%d" % j  # take ineq j

    #     lp.objective(
    #         objective=lp.sum(var_fset.values()),
    #         sense="minimize",
    #     )

    #     for i, js in by_point.items():
    #         lp.constraint(lp.sum(var_fset[j] for j in js) + " >= 1")

    #     lp.binaries(var_fset.values())
    #     lp.close()

    # def choose_subset_greedy(self, iterations=10, eps=0):
    #     self.log.info(
    #         f"InequalitiesPool.choose_subset_greedy("
    #         f"iterations={iterations},eps={eps}"
    #         ")"
    #     )
    #     self.log.info(
    #         f"{self.system.n_lower()} ineqs {len(self.exclude)} bad points"
    #     )

    #     best = float("+inf"), None
    #     for itr in range(iterations):
    #         Lstar = self.choose_subset_greedy_once(eps=eps)

    #         cur = len(Lstar), Lstar
    #         self.log.info(f"itr #{itr}: {cur[0]} ineqs")
    #         if cur < best:
    #             best = cur
    #     self.log.info(f"best: {best[0]} inequalities")
    #     assert best[1] is not None
    #     return best[1]
