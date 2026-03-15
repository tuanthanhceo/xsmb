def compute_loto(prizes: dict) -> list[str]:
    """Extract last 2 digits from all 27 prizes, sorted ascending."""
    all_numbers = [prizes["giai_db"], prizes["giai_1"]]
    all_numbers.extend(prizes["giai_2"])
    all_numbers.extend(prizes["giai_3"])
    all_numbers.extend(prizes["giai_4"])
    all_numbers.extend(prizes["giai_5"])
    all_numbers.extend(prizes["giai_6"])
    all_numbers.extend(prizes["giai_7"])

    loto = [n[-2:].zfill(2) for n in all_numbers]
    loto.sort()
    return loto


def compute_de_dau(giai_db: str) -> str:
    return giai_db[-2:]


def compute_de_duoi(giai_7: list[str]) -> str:
    return giai_7[0][-2:].zfill(2)


def build_raw_string(prizes: dict) -> str:
    parts = [prizes["giai_db"], prizes["giai_1"]]
    parts.extend(prizes["giai_2"])
    parts.extend(prizes["giai_3"])
    parts.extend(prizes["giai_4"])
    parts.extend(prizes["giai_5"])
    parts.extend(prizes["giai_6"])
    parts.extend(prizes["giai_7"])
    return "".join(parts)
