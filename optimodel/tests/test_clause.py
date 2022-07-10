import pytest

from binteger import Bin

from optimodel.clause import OrClause, AndClause


def test_OrClause():
    c = OrClause([1])
    assert c.solutions(1).to_Bins() == [
        Bin(0b1, n=1),
    ]
    assert c.solutions(2).to_Bins() == [
        Bin(0b10, n=2),
        Bin(0b11, n=2),
    ]
    assert c.satisfy([1])
    assert not c.satisfy([0])

    assert c.satisfy([1, 0])
    assert c.satisfy([1, 1])
    assert not c.satisfy([0, 0])
    assert not c.satisfy([0, 1])

    # ====================

    c = OrClause([-2])
    with pytest.raises((ValueError, IndexError)):
        c.solutions(1)

    assert c.solutions(2).to_Bins() == [
        Bin(0b00, n=2),
        Bin(0b10, n=2),
    ]

    assert c.satisfy([0, 0])
    assert c.satisfy([1, 0])
    assert not c.satisfy([0, 1])
    assert not c.satisfy([1, 1])

    # ====================

    c = OrClause((1, -3))

    with pytest.raises((ValueError, IndexError)):
        c.solutions(1)

    with pytest.raises((ValueError, IndexError)):
        c.solutions(2)

    assert c.solutions(3).to_Bins() == [
        Bin(0b000, n=3),
        Bin(0b010, n=3),
        Bin(0b100, n=3),
        Bin(0b101, n=3),
        Bin(0b110, n=3),
        Bin(0b111, n=3),
    ]

    assert c.solutions(4).to_Bins() == [
        Bin(0b0000, n=4),
        Bin(0b0001, n=4),
        Bin(0b0100, n=4),
        Bin(0b0101, n=4),
        Bin(0b1000, n=4),
        Bin(0b1001, n=4),
        Bin(0b1010, n=4),
        Bin(0b1011, n=4),
        Bin(0b1100, n=4),
        Bin(0b1101, n=4),
        Bin(0b1110, n=4),
        Bin(0b1111, n=4),
    ]

    # ====================

    c = OrClause((1, -2, -3))

    assert c.solutions(3).to_Bins() == [
        Bin(0b000, n=3),
        Bin(0b001, n=3),
        Bin(0b010, n=3),
        # Bin(0b011, n=3),
        Bin(0b100, n=3),
        Bin(0b101, n=3),
        Bin(0b110, n=3),
        Bin(0b111, n=3),
    ]


def test_AndClause():
    c = AndClause([1])
    assert c.solutions(1).to_Bins() == [
        Bin(0b1, n=1),
    ]
    assert c.solutions(2).to_Bins() == [
        Bin(0b10, n=2),
        Bin(0b11, n=2),
    ]
    assert c.satisfy([1])
    assert not c.satisfy([0])

    assert c.satisfy([1, 0])
    assert c.satisfy([1, 1])
    assert not c.satisfy([0, 0])
    assert not c.satisfy([0, 1])

    # ====================

    c = AndClause([-2])
    with pytest.raises((ValueError, IndexError)):
        c.solutions(1)

    assert c.solutions(2).to_Bins() == [
        Bin(0b00, n=2),
        Bin(0b10, n=2),
    ]

    assert c.satisfy([0, 0])
    assert c.satisfy([1, 0])
    assert not c.satisfy([0, 1])
    assert not c.satisfy([1, 1])

    # ====================

    c = AndClause((1, -3))

    with pytest.raises((ValueError, IndexError)):
        c.solutions(1)

    with pytest.raises((ValueError, IndexError)):
        c.solutions(2)

    assert c.solutions(3).to_Bins() == [
        Bin(0b100, n=3),
        Bin(0b110, n=3),
    ]

    assert c.solutions(4).to_Bins() == [
        Bin(0b1000, n=4),
        Bin(0b1001, n=4),
        Bin(0b1100, n=4),
        Bin(0b1101, n=4),
    ]

    # ====================

    c = AndClause((1, -2, -3))

    assert c.solutions(3).to_Bins() == [
        Bin(0b100, n=3),
    ]

    assert c.solutions(4).to_Bins() == [
        Bin(0b1000, n=4),
        Bin(0b1001, n=4),
    ]


if __name__ == '__main__':
    test_OrClause()
    test_AndClause()
