class Inequality(tuple):
    """Inequality wrapper

    Format:
    (a0, a1, a2, ..., a_{n-1}, c)
    a0*x0 + a1*x1 + ... + a_{n-1}*x_{n-1} + c >= 0
    """

    def satisfy(self, pt):
        assert len(pt) + 1 == len(self)
        return inner(pt, self) + self[-1] >= 0

    def reorient(self, direction: tuple):
        assert len(self) == len(direction) + 1

        val = self[-1]
        ineq2 = []
        for a, s in zip(self, direction):
            if s == -1:
                ineq2.append(-a)
                val += a
            elif s == 1:
                ineq2.append(a)
            else:
                raise ValueError(s)
        ineq2.append(val)
        return Inequality(ineq2)


def inner(a, b):
    return sum(aa * bb for aa, bb in zip(a, b))
