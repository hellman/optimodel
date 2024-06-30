import pyomo.environ as pyo
from pyomo.opt import SolverFactory

from monolearn import Oracle
from monolearn.SparseSet import SparseSet

# from optisolveapi.milp import MILP

from optimodel.inequality import Inequality

def pyo_dot(a, b):
    assert len(a) == len(b)
    lst = [a[i] * b[i] for i in range(len(b))]
    return pyo.quicksum([a[i] * b[i] for i in range(len(b))])


class LPbasedOracle(Oracle):
    def __init__(self, pool, solver=None):
        super().__init__()

        self.solver = solver or "glpk"
        self.model = None
        self.pool = pool

    def _prepare_constraints(self):
        self.model = pyo.ConcreteModel()
        self.model_solver = SolverFactory(self.solver)

        # model.x = pyo.Var(range(V), domain=pyo.Binary)
        # xs = list(model.x.values())

        # model.OBJ = pyo.Objective(expr = pyo.summation(model.x))

        # self.milp = MILP.feasibility(solver=self.solver)
        LP = self.model = pyo.ConcreteModel()

        if self.pool.is_upper:
            # monotone => nonnegative
            LP.xs = pyo.Var(range(self.pool.n), domain=pyo.NonNegativeReals)
            LP.c = pyo.Var(domain=pyo.NonNegativeReals)
        else:
            LP.xs = pyo.Var(range(self.pool.n), domain=pyo.Reals)
            LP.c = pyo.Var(domain=pyo.Reals)

        LP.inc = pyo.ConstraintList()
        for p in self.pool.include:
            # ... >= c
            # ... -c >= 0
            LP.inc.add(
                pyo_dot(LP.xs, p) >= LP.c,
            )

        self.i2cs = []
        for q in self.pool.i2exc:
            # ... <= c - 1
            # ... -c <= -1
            self.i2cs.append(
                pyo_dot(LP.xs, q) <= LP.c - 1,
            )

    def _query(self, bads: SparseSet):
        assert isinstance(bads, SparseSet)
        if not bads:
            # trivial inequality
            ineq = Inequality((0,) * self.pool.n + (0,))
            return True, ineq

        if self.model is None:
            self._prepare_constraints()

        LP = self.model  # .clone()
        LP.exc = pyo.ConstraintList()
        for i in bads:
            LP.exc.add(self.i2cs[i])
        res = self.model_solver.solve(LP)
        # del LP.exc
        # print(res)
        if res.solver.termination_condition != "optimal":
            del LP.exc
            return False, None

        val_xs = tuple(LP.xs[i].value for i in range(len(LP.xs)))
        val_c = LP.c.value

        if not all(isinstance(v, int) for v in val_xs + (val_c,)):
            # if non-integral coefficients,
            # keep real ineq, put the separator in the middle
            # (can be massaged later..)
            val_c -= 0.5

        ineq = Inequality(val_xs + (-val_c,))
        assert all(ineq.satisfy(p) for p in self.pool.include)
        assert all(not ineq.satisfy(self.pool.i2exc[i]) for i in bads)
        del LP.exc
        return True, ineq
