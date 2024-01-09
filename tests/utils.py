def expand_to_decimals(num: int, decimals: int = 18) -> int:
    return (10**decimals) * num


def uint_max(bits: int) -> int:
    return 2**bits - 1
