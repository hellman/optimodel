from binteger import Bin
from subsets import DenseSet


class OrClause(tuple):
    """Disjunction (cube complement)

    Format:
    (4, -7, 11, ...)
    (x[4-1] v ~x[7-1] v x[11-1] & ...)
    """

    def satisfy(self, pt):
        for i in self:
            if i > 0 and pt[abs(i)-1] == 1:
                return True
            if i < 0 and pt[abs(i)-1] == 0:
                return True
        return False

    def solutions(self, n) -> DenseSet:
        d = DenseSet(n)
        shift = [0] * n
        for i in self:
            d.set(1 << (n - abs(i)))  # Clause is 1-based so no n-1
            if i < 0:
                shift[abs(i)-1] = 1
        shift = Bin(shift).int
        d.do_UpperSet()
        d.do_Not(shift)
        return d

    def __invert__(self):
        return AndClause(-v for v in self)


class AndClause(tuple):
    """Conjunction (cube).

    Format:
    (4, -7, 11, ...)
    (x[4-1] & ~x[7-1] & x[11-1] & ...)
    """

    def satisfy(self, pt):
        for i in self:
            if i > 0 and pt[abs(i)-1] != 1:
                return False
            if i < 0 and pt[abs(i)-1] != 0:
                return False
        return True

    def solutions(self, n) -> DenseSet:
        d = DenseSet(n)
        shift = [0] * n
        mask = [0] * n
        for i in self:
            if i < 0:
                shift[abs(i)-1] = 1
            mask[abs(i)-1] = 1
        shift = Bin(shift).int
        mask = Bin(mask).int
        d.set(mask)
        d.do_UpperSet()
        d.do_Not(shift)
        return d

    def __invert__(self):
        return OrClause(-v for v in self)
