from monolearn.utils import TimeStat

from optimodel.tool.base import BaseTool


AutoSmall = (
    "SubsetMILP:",
)

AutoMedium = (
    "SubsetWriteGecco:",
    "SubsetWriteMILP:solver=swiglpk",

    # to give good baseline
    "SubsetSCS:largeneighborhoodsearch_2,timeout=10",
    "SubsetSCS:localsearch_rowweighting,timeout=10",

    # usuall worse, but fast (don't actually take 10sec)
    # so worth keeping
    "SubsetSCS:greedy,timeout=10",
    "SubsetSCS:greedy_lin,timeout=10",
    "SubsetSCS:greedy_dual,timeout=10",

    "SubsetWriteMILP:solver=swiglpk",
    "SubsetMILP:solver=gurobi",
)

AutoLarge = (
    "SubsetWriteGecco:",
    "SubsetWriteMILP:solver=swiglpk",

     # to give good baseline
    "SubsetSCS:largeneighborhoodsearch_2,timeout=10",
    "SubsetSCS:localsearch_rowweighting,timeout=10",

    # usuall worse, but fast (don't actually take 10sec)
    # so worth keeping
    "SubsetSCS:greedy,timeout=10",
    "SubsetSCS:greedy_lin,timeout=10",
    "SubsetSCS:greedy_dual,timeout=10",

    # just in case
    "SubsetSCS:localsearch_rowweighting,timeout=10",
    "SubsetSCS:localsearch_rowweighting_2,timeout=10",
    "SubsetSCS:largeneighborhoodsearch,timeout=10",
    "SubsetSCS:largeneighborhoodsearch_2,timeout=10",

    # main artillery
    "SubsetSCS:localsearch_rowweighting_2,timeout=300",
    "SubsetSCS:largeneighborhoodsearch_2,timeout=300",

    # write LP with updated bound
    "SubsetWriteMILP:solver=swiglpk",

    # "SubsetGreedy:",
    # "SubsetSCS:algorithm=greedy",
    # "SubsetSCS:algorithm=greedy_lin",
    # "SubsetSCS:algorithm=greedy_dual",
    # "SubsetSCS:algorithm=largeneighborhoodsearch_2,timeout=10",
    # "SubsetSCS:algorithm=localsearch_rowweighting,timeout=120",
    # "SubsetSCS:algorithm=localsearch_rowweighting_2,timeout=120",
    # "SubsetSCS:algorithm=largeneighborhoodsearch,timeout=120",
    #"SubsetSCS:algorithm=largeneighborhoodsearch_2,timeout=100,iterations=36",  # 1 hour
    #"SubsetMILP:",
)


class ConstraintTool(BaseTool):
    """
    Base class for constraint minimization tools.
    Includes minimization for # of constraints.
    """
    KIND = NotImplemented
    FOLDER = ""

    gecco_written = None
    lp_written = None
    meta_written = None

    @TimeStat.log
    def AutoSelect(self):
        n_sets = len(self.pool.constraints)
        n_vars = len(self.pool.exclude)
        param = min(n_sets, n_vars)

        self.log.info(f"AutoSelect with {n_sets} sets and {n_vars} elements")

        if param < 400:
            self.log.info("using AutoSmall preset")
            return self.AutoSmall()

        if param < 1500:
            self.log.info("using AutoMedium preset")
            return self.AutoMedium()

        self.log.info("using AutoLarge preset")
        return self.AutoLarge()

    @TimeStat.log
    def AutoSmall(self):
        for cmd in AutoSmall:
            self.run_command_string(cmd)

    @TimeStat.log
    def AutoMedium(self):
        for cmd in AutoSmall:
            self.run_command_string(cmd)

    @TimeStat.log
    def AutoLarge(self):
        for cmd in AutoLarge:
            self.run_command_string(cmd)

    # ================================

    def _write_meta(self):
        if self.meta_written is None:
            filename = self.output_prefix + "subset.meta"
            self.pool.write_subset_meta(filename=filename)
            self.meta_written = filename

    @TimeStat.log
    def SubsetWriteGecco(self):
        self._write_meta()

        filename = self.output_prefix + "subset.gecco"
        self.pool.write_subset_gecco(filename=filename)
        self.gecco_written = filename

    @TimeStat.log
    def SubsetWriteMILP(self, *args, **kwargs):
        self._write_meta()

        filename = self.output_prefix + "subset.lp"
        self.pool.write_subset_milp(filename=filename, **kwargs)
        self.lp_written = filename

    # ================================

    @TimeStat.log
    def SubsetFull(self):
        self.pool.subset_all()

    @TimeStat.log
    def SubsetMILP(self, *args, **kwargs):
        self.pool.subset_by_milp(*args, **kwargs)

    @TimeStat.log
    def SubsetSCS(self, *args, **kwargs):
        if not self.gecco_written:
            self.SubsetWriteGecco()

        kwargs.setdefault(
            "solfile", self.output_prefix + "scs.solution"
        )
        kwargs.setdefault(
            "geccofile", self.gecco_written
        )

        iters = kwargs.pop("iterations", 1)
        for itr in range(iters):
            self.log.info(f"SCS iter {itr+1}/{iters}")
            self.pool.subset_by_setcoveringsolver(*args, **kwargs)

    # def SubsetGreedy(self, iterations=10, eps=0):
    #     self.log.info(
    #         f"{self.pool.system.n_lower()} ineqs"
    #         f" {len(self.pool.exclude)} exclude points"
    #     )

    #     best = float("+inf"), None
    #     for itr in range(iterations):
    #         Lstar = self.pool.choose_subset_greedy_once(eps=eps)

    #         cur = len(Lstar), Lstar
    #         self.log.info(f"itr #{itr}: {cur[0]} ineqs")
    #         if cur < best:
    #             best = cur
    #             self.save(Lstar, limit=50, optimal=False)

    #     self.log.info(f"best: {best[0]} inequalities")
    #     assert best[1] is not None
    #     return best[1]

    # =======================================

    def log_time_stats(self, header):
        maxlen = max(map(len, TimeStat.Stat))
        self.log.info(f"timing {header}")
        for name, ts in TimeStat.Stat.items():
            if ts:
                self.log.info(f"{name.rjust(maxlen+3)} {ts}")
