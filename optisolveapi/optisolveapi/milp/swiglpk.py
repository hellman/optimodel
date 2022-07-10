import logging
from collections import namedtuple
from .base import MILPX

log = logging.getLogger(__name__)

try:
    from swiglpk import (
        glp_create_prob,
        glp_set_obj_dir,
        glp_add_rows,
        glp_add_cols,
        glp_set_col_name,
        glp_get_num_rows,
        glp_get_num_cols,
        GLP_MIN, GLP_MAX,
        glp_set_row_bnds,
        glp_set_col_bnds,
        GLP_FR, GLP_LO, GLP_UP, GLP_DB,
        glp_set_mat_row,
        # glp_set_mat_col,
        intArray, doubleArray,
        glp_del_rows,
        glp_set_obj_coef,
        glp_delete_prob,
        glp_smcp, glp_iocp,
        glp_init_iocp, glp_init_smcp,
        glp_term_out,
        GLP_ON, GLP_OFF,
        glp_intopt, glp_simplex,
        glp_get_obj_val,
        glp_get_col_prim,
        glp_get_status,
        GLP_OPT, GLP_FEAS, GLP_NOFEAS, GLP_INFEAS,
        GLP_ENOPFS, GLP_ENODFS,
        glp_std_basis,
    )
    has_swiglpk = True
except ImportError as err:
    has_swiglpk = False
    log.warning(f"no swiglpk detected: {err}")


@MILPX.register("swiglpk")
class SWIGLPK(MILPX):
    VarInfo = namedtuple("VarInfo", ("name", "typ", "id"))

    def __init__(self, maximization, solver):
        super().__init__(maximization, solver)
        assert has_swiglpk
        self.model = glp_create_prob()
        self.rowid2cid = {}
        self.has_ints = False
        if maximization is True:
            glp_set_obj_dir(self.model, GLP_MAX)
        elif maximization is False:
            glp_set_obj_dir(self.model, GLP_MIN)

    def __del__(self):
        if has_swiglpk:
            glp_delete_prob(self.model)

    def _var(self, name, typ):
        assert typ in "RCIB", typ
        if typ not in ("C", "R"):
            self.has_ints = True
        assert glp_get_num_cols(self.model) == len(self.vars)
        varid = len(self.vars) + 1
        glp_add_cols(self.model, 1)
        glp_set_col_name(self.model, varid, name)
        return self.VarInfo(name=name, typ=typ, id=varid)

    def set_var_bounds(self, var, lb=None, ub=None):
        glp_set_col_bnds(
            self.model,
            self.vars[var].id,
            *self._bounds(lb, ub)
        )

    def _bounds(self, lb, ub):
        if lb is None:
            if ub is None:
                return (
                    GLP_FR,  # free
                    0.0, 0.0,
                )
            else:
                return (
                    GLP_UP,  # upper bound
                    0.0, ub,
                )
        else:
            if ub is None:
                return (
                    GLP_LO,  # lower bound
                    lb, 0.0,
                )
            else:
                assert lb != ub, "to make GLP_FX = fixed"
                return (
                    GLP_DB,  # double bound
                    lb, ub,
                )
        assert 0

    def add_constraint(self, coefs: dict, lb=None, ub=None) -> int:
        assert isinstance(coefs, dict)
        assert lb is not None or ub is not None
        assert lb is None or isinstance(lb, (int, float))
        assert ub is None or isinstance(ub, (int, float))

        cid = self._constraint_id
        self._constraint_id += 1
        assert glp_get_num_rows(self.model) == len(self.constraints)

        rowid = self.constraints[cid] = len(self.constraints) + 1
        self.rowid2cid[rowid] = cid

        glp_add_rows(self.model, 1)
        assert glp_get_num_rows(self.model) == len(self.constraints)

        glp_set_row_bnds(self.model, rowid, *self._bounds(lb, ub))

        inds = intArray(len(coefs) + 1)
        vals = doubleArray(len(coefs) + 1)
        # print(coefs)
        ptr = 1
        for var, val in coefs.items():
            inds[ptr] = self.vars[var].id
            vals[ptr] = val
            ptr += 1

        # print(glp_get_num_rows(self.model))
        # print(glp_get_num_cols(self.model))
        # print(coefs,
        #     [inds[i] for i in range(len(coefs))],
        #     [vals[i] for i in range(len(coefs))],
        # )

        glp_set_mat_row(self.model, rowid, len(coefs), inds, vals)
        return cid

    def remove_constraint(self, del_cid: int):
        assert isinstance(del_cid, int)
        max_rowid = len(self.constraints)

        del_rowid = self.constraints[del_cid]
        del self.constraints[del_cid]
        del self.rowid2cid[del_rowid]

        inds = intArray(2)
        inds[1] = del_rowid
        glp_del_rows(self.model, 1, inds)

        for rowid in range(del_rowid + 1, max_rowid + 1):
            assert (rowid-1) not in self.rowid2cid
            cid = self.rowid2cid[rowid-1] = self.rowid2cid[rowid]
            del self.rowid2cid[rowid]
            self.constraints[cid] = rowid - 1

        assert len(self.constraints) \
            == len(self.rowid2cid) \
            == glp_get_num_rows(self.model)
        glp_std_basis(self.model)

    def remove_constraints(self, del_cids: [int]):
        todel = [(del_cid, self.constraints[del_cid]) for del_cid in del_cids]
        max_rowid = len(self.constraints) + 1

        inds = intArray(1 + len(del_cids))
        ptr = 1
        for del_cid, del_rowid in todel:
            inds[ptr] = del_rowid
            ptr += 1
            del self.constraints[del_cid]
            del self.rowid2cid[del_rowid]
        glp_del_rows(self.model, len(del_cids), inds)

        free = min(v[1] for v in todel)
        for rowid in range(free, max_rowid + 1):
            if rowid in self.rowid2cid:
                assert free not in self.rowid2cid
                cid = self.rowid2cid[free] = self.rowid2cid[rowid]
                del self.rowid2cid[rowid]
                self.constraints[cid] = free
                free += 1

        assert len(self.constraints) \
            == len(self.rowid2cid) \
            == glp_get_num_rows(self.model)
        glp_std_basis(self.model)

    def set_objective(self, coefs):
        for name, value in coefs.items():
            glp_set_obj_coef(
                self.model,
                self.vars[name].id,
                value,
            )

    # def copy(self):
    #     obj = object.__new__(type(self))
    #     obj.model = self.model.__copy__()
    #     obj.constraints = self.model.constraints[::]
    #     obj.vars = self.model.vars[::]
    #     return obj

    def optimize(self, solution_limit=1, log=None, only_best=True):
        self.err = None
        self.solutions = None

        if log:
            glp_term_out(GLP_ON)
        else:
            glp_term_out(GLP_OFF)

        # glp_std_basis(self.model)

        status = None

        # step 1: simplex
        parm = glp_smcp()
        glp_init_smcp(parm)
        parm.presolve = GLP_ON
        ret = glp_simplex(self.model, parm)
        if ret in (GLP_ENOPFS, GLP_ENODFS):
            return False
        elif ret != 0:
            raise RuntimeError(f"unknown GLPK error (simplex): {ret}")

        status = glp_get_status(self.model)
        if status == GLP_INFEAS or status == GLP_NOFEAS:
            return False

        if self.has_ints:
            # step 2: MIP
            parm = glp_iocp()
            glp_init_iocp(parm)
            parm.presolve = GLP_ON
            ret = glp_intopt(self.model, parm)
            if ret in (GLP_ENOPFS, GLP_ENODFS):
                return False
            elif ret != 0:
                raise RuntimeError(f"unknown GLPK error (intopt): {ret}")

        status = glp_get_status(self.model)

        if self.maximization is None:
            if status in (GLP_FEAS, GLP_OPT):
                obj = True
            elif status in (GLP_INFEAS, GLP_NOFEAS):
                return False
            else:
                raise RuntimeError(f"unknown GLPK status: {status}")
        else:
            if status == GLP_OPT:
                obj = self.trunc(glp_get_obj_val(self.model))
            else:
                raise RuntimeError(f"unknown GLPK status: {status}")

        if solution_limit == 0:
            return obj

        # sagemath returns only 1 solution
        vec = {
            name: self.trunc(glp_get_col_prim(self.model, var.id))
            for name, var in self.vars.items()
        }
        self.solutions = vec,
        return obj
