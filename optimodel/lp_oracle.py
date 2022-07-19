from monolearn import Oracle
from monolearn.SparseSet import SparseSet

from optisolveapi.milp import MILP

from optimodel.inequality import Inequality


class LPbasedOracle(Oracle):
    def __init__(self, pool, solver=None):
        super().__init__()

        self.solver = solver
        self.n_calls = 0
        self.milp = None
        self.pool = pool

    def _prepare_constraints(self):
        self.milp = MILP.feasibility(solver=self.solver)

        if self.pool.is_upper:
            lb = 0  # monotone => nonnegative
        else:
            lb = None

        # set ub = 1000+ ? ...
        self.xs = []
        for i in range(self.pool.n):
            self.xs.append(self.milp.var_real("x%d" % i, lb=lb, ub=None))

        self.c = self.milp.var_real("c", lb=lb, ub=None)
        self.xsc = self.xs + [self.c]

        for p in self.pool.include:
            # ... >= c
            # ... -c >= 0
            self.milp.add_constraint(
                zip(self.xsc, p + (-1,)),
                lb=0,
            )

        self.i2cs = []
        for q in self.pool.i2exc:
            # ... <= c - 1
            # ... -c <= -1
            self.i2cs.append(dict(
                coefs=tuple(zip(self.xsc, q + (-1,))),
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

        if not all(isinstance(v, int) for v in val_xs + (val_c,)):
            # if non-integral coefficients,
            # keep real ineq, put the separator in the middle
            # (can be massaged later..)
            val_c -= 0.5

        ineq = Inequality(val_xs + (-val_c,))
        assert all(ineq.satisfy(p) for p in self.pool.include)
        assert all(not ineq.satisfy(self.pool.i2exc[i]) for i in bads)
        return True, ineq
