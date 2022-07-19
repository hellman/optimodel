import os
import bz2
import logging

from enum import Enum
from collections import namedtuple


log = logging.getLogger(f"{__name__}")


class TypeGood(Enum):
    LOWER = "lower"
    UPPER = "upper"
    EXPLICIT = "explicit"


SetType = namedtuple("SetType", ("type_good", "type_values"))


def read_from_file(cls, filename):
    with open(filename, "rt") as f:
        type_good, type_values = f.read().split()

    return SetType(
        type_good=TypeGood(type_good),
        type_values=type_values,
    )


SetType.read_from_file = classmethod(read_from_file)
del read_from_file


def read_set(filename):
    if filename.endswith(".bz2"):
        log.info(f"reading bzip2 file {filename}")
        f = bz2.open(filename, "rt")

    elif filename.endswith(".txt"):
        log.info(f"reading text file {filename}")
        f = open(filename, "rt")

    elif filename.endswith(".set"):
        from subsets import DenseSet
        log.info(f"reading DenseSet file {filename}")
        s = DenseSet.load_from_file(filename)
        return set(s.to_Bins())

    else:
        for ext in (".bz2", ".txt", ".set"):
            if os.path.isfile(filename + ext):
                return read_set(filename + ext)
        raise NotImplementedError(f"{filename} should end with one of .bz, .txt, .set")

    num, n = map(int, f.readline().split())
    s = set()
    for i in range(num):
        pt = tuple(map(int, f.readline().split()))
        s.add(pt)
    return s
