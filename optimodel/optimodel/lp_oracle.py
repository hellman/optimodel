from monolearn import Oracle

from optisolveapi.milp import MILP, MILPX

from subsets.SparseSet import SparseSet
from optimodel.inequality import Inequality, inner


class LPbasedOracle(Oracle):
    def __init__(self, pool, solver=None):
        super().__init__()

        self.solver = solver
        self.n_calls = 0
        self.pool = pool
        self.milp = None

    def _prepare_constraints(self):
        self.milp = MILP.maximization(solver=self.solver)

        if self.pool.is_monotone:
            lb = 0  # monotone => nonnegative
        else:
            lb = None

        # set ub = 1000+ ? ...
        self.xs = []
        for i in range(self.pool.n):
            self.xs.append(self.milp.var_real("x%d" % i, lb=lb, ub=None))
        self.c = self.milp.var_real("c", lb=lb, ub=None)

        for p in self.pool.good:
            self.milp.add_constraint(inner(p, self.xs) >= self.c)

        self.i2cs = []
        for q in self.pool.i2bad:
            self.i2cs.append(inner(q, self.xs) <= self.c - 1)

    def _query(self, bads: SparseSet):
        assert isinstance(bads, SparseSet)
        if not bads:
            # trivial inequality
            ineq = Inequality((0,) * self.pool.n + (0,))
            return True, ineq

        if self.milp is None:
            self._prepare_constraints()

        self.n_calls += 1

        LP = self.milp
        cs = [LP.add_constraint(self.i2cs[i]) for i in bads]
        res = LP.optimize(log=0)
        LP.remove_constraints(cs)

        if res is None:
            return False, None

        sol = LP.solutions[0]
        val_xs = tuple(sol[x] for x in self.xs)
        val_c = sol[self.c]

        # print("res", res, "sol", sol, "val_c", val_c)
        if not all(isinstance(v, int) for v in val_xs + (val_c,)):
            # keep real ineq, put the separator in the middle
            val_c -= 0.5
            pass

        ineq = Inequality(val_xs + (-val_c,))
        assert all(ineq.satisfy(p) for p in self.pool.good)
        assert all(not ineq.satisfy(self.pool.i2bad[i]) for i in bads)
        return True, ineq


class LPXbasedOracle(Oracle):
    def __init__(self, pool, solver=None):
        super().__init__()

        self.solver = solver
        self.n_calls = 0
        self.milp = None
        self.pool = pool

    def _prepare_constraints(self):
        self.milp = MILPX.feasibility(solver=self.solver)

        if self.pool.is_monotone:
            lb = 0  # monotone => nonnegative
        else:
            lb = None

        # set ub = 1000+ ? ...
        self.xs = []
        for i in range(self.pool.n):
            self.xs.append(self.milp.var_real("x%d" % i, lb=lb, ub=None))
        self.c = self.milp.var_real("c", lb=lb, ub=None)

        for p in self.pool.good:
            # ... >= c
            # ... -c >= 0
            self.milp.add_constraint(
                inner_dict(self.xs + [self.c], p.tuple + (-1,)),
                lb=0,
            )

        self.i2cs = []
        for q in self.pool.i2bad:
            # ... <= c - 1
            # ... - c <= -1
            self.i2cs.append(dict(
                coefs=inner_dict(self.xs + [self.c], q.tuple + (-1,)),
                ub=-1,
            ))

    def _query(self, bads: SparseSet):
        assert isinstance(bads, SparseSet)
        if not bads:
            # trivial inequality
            ineq = Inequality((0,) * self.pool.n + (0,))
            return True, ineq

        if self.milp is None:
            self._prepare_constraints()

        self.n_calls += 1

        LP = self.milp
        cs = [LP.add_constraint(**self.i2cs[i]) for i in bads]
        res = LP.optimize(log=0)
        LP.remove_constraints(cs)

        if res is False:
            return False, None

        sol = LP.solutions[0]
        val_xs = tuple(sol[x] for x in self.xs)
        val_c = sol[self.c]

        # print("res", res, "sol", sol, "val_c", val_c)
        if not all(isinstance(v, int) for v in val_xs + (val_c,)):
            # keep real ineq, put the separator in the middle
            val_c -= 0.5
            pass

        ineq = Inequality(val_xs + (-val_c,))
        assert all(ineq.satisfy(p) for p in self.pool.good)
        assert all(not ineq.satisfy(self.pool.i2bad[i]) for i in bads)
        return True, ineq


def inner_dict(a, b):
    return {aa: bb for aa, bb in zip(a, b)}
