import os


class BaseTool:
    output_prefix = NotImplemented
    log = NotImplemented

    def run_command_string(self, cmd):
        method, args, kwargs = parse_method(cmd)
        self.log.info(f"running command {method} {args} {kwargs}")
        ret = getattr(self, method)(*args, **kwargs)
        self.log.info(f"command {method} returned {ret}")

    def save(self, constraints, kind, limit=50):
        filename = f"{self.output_prefix}.{len(constraints)}"

        if os.path.exists(filename):
            self.log.warning(f"file {filename} exists, skipping overwrite!")
        else:
            self.log.info(f"saving {len(constraints)} {kind} to {filename}")
            with open(filename, "w") as f:
                print(len(constraints), file=f)
                for eq in constraints:
                    print(*eq, file=f)
            self.log.info(f"saved {len(constraints)} {kind} to {filename}")

        if len(constraints) < 50:
            self.log.info(f"{kind} ({len(constraints)}):")
            for ineq in constraints:
                self.log.info(f"{ineq}")
            self.log.info("end")


def parse_method(s):
    """
    >>> parse_method("Test")
    ('Test', (), {})
    >>> parse_method("Test:")
    ('Test', (), {})
    >>> parse_method("Test:asd")
    ('Test', ('asd',), {})
    >>> parse_method("Test:test,asd=123")
    ('Test', ('test',), {'asd': 123})
    >>> parse_method("Test:asd=123a")
    ('Test', (), {'asd': '123a'})
    >>> parse_method("Pre:Test,asd")
    ('Pre', ('Test', 'asd'), {})
    """
    if ":" not in s:
        s += ":"
    method, str_opts = s.split(":", 1)
    assert method

    kwargs = {}
    args = []
    str_opts = str_opts.strip()
    if str_opts:
        for opt in str_opts.split(","):
            if "=" in opt:
                key, val = opt.split("=", 1)
                kwargs[key] = parse_value(val)
            else:
                val = opt
                args.append(parse_value(val))
    return method, tuple(args), kwargs


def parse_value(s: str):
    """
    >>> parse_value("123")
    123
    >>> parse_value("123.0")
    123.0
    >>> parse_value("+inf")
    inf
    >>> parse_value("123a")
    '123a'
    >>> parse_value("None")
    >>> parse_value("False")
    False
    >>> parse_value("True")
    True
    >>> parse_value("true")
    'true'
    """
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    if s == "None":
        return
    if s == "False":
        return False
    if s == "True":
        return True
    return s
