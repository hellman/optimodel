import logging
from itertools import product

try:
    from pysat.solvers import Solver
    has_pysat = True
except ImportError:
    has_pysat = False

from .base import CNF

if has_pysat:
    @CNF.register("pysat/cadical")  # CaDiCaL SAT solver
    @CNF.register("pysat/glucose3")  # Glucose 3 SAT solver
    @CNF.register("pysat/glucose4")  # Glucose 4.1 SAT solver
    @CNF.register("pysat/lingeling")  # Lingeling SAT solver
    @CNF.register("pysat/maplechrono")  # MapleLCMDistChronoBT SAT solver
    @CNF.register("pysat/maplecm")  # MapleCM SAT solver
    @CNF.register("pysat/maplesat")  # MapleCOMSPS_LRB SAT solver
    @CNF.register("pysat/minicard")  # Minicard SAT solver
    @CNF.register("pysat/minisat22")  # MiniSat 2.2 SAT solver
    @CNF.register("pysat/minisatgh")  # MiniSat SAT solver (version from github)
    class PySAT(CNF):
        log = logging.getLogger(f"{__name__}.PySAT")

        def init_solver(self, solver):
            assert has_pysat
            assert solver.startswith("pysat/")
            solver = solver[len("pysat/"):]
            self._solver = Solver(name=solver)

        def model_to_sol(self, model):
            res = {(i+1): int(v > 0) for i, v in enumerate(model)}
            added = self.n_vars - len(model)
            for i in range(len(model), self.n_vars):
                assert (i+1) not in res
                res[i+1] = 0
            if added:
                self.log.debug(f"set {added} free vars to 0")
            return res

        def model_to_sols(self, model):
            res = {(i+1): int(v > 0) for i, v in enumerate(model)}
            if self.n_vars > len(res):
                for vals in product(range(2), repeat=self.n_vars - len(model)):
                    for i, v in zip(range(len(model), self.n_vars), vals):
                        res[i+1] = v
                    yield res.copy()
            else:
                yield res

        def solve(self, assumptions=()):
            sol = self._solver.solve(assumptions=assumptions)
            if sol is None or sol is False:
                return False
            model = self._solver.get_model()
            return self.model_to_sol(model)

        def solve_all(self, assumptions=()):
            sol = self._solver.solve(assumptions=assumptions)
            if sol is None or sol is False:
                return
            for model in self._solver.enum_models():
                yield from self.model_to_sols(model)
            # pysat spoils the model after enum_models() ...
            # clear up to ensure no surprises
            self._solver.delete()
            del self._solver

        def __del__(self):
            if hasattr(self, "_solver") and self._solver:
                self._solver.delete()
