from binteger import Bin


class Inequality(tuple):
    """Inequality wrapper

    Format:
    (a0, a1, a2, ..., a_{n-1}, c)
    a0*x0 + a1*x1 + ... + a_{n-1}*x_{n-1} + c >= 0
    """

    def satisfy(self, pt):
        assert len(pt) + 1 == len(self)
        return inner(pt, self) + self[-1] >= 0

    def shift(self, shift: Bin):
        shift = shift.tuple
        assert len(self) == len(shift) + 1

        val = self[-1]
        ineq2 = []
        for a, s in zip(self, shift):
            if s:
                ineq2.append(-a)
                val += a
            else:
                ineq2.append(a)
        ineq2.append(val)
        return Inequality(ineq2)


def inner(a, b):
    return sum(aa * bb for aa, bb in zip(a, b))
