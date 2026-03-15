import re

PRIZE_SPEC = [
    ("giai_db", 1, 5),
    ("giai_1", 1, 5),
    ("giai_2", 2, 5),
    ("giai_3", 6, 5),
    ("giai_4", 4, 4),
    ("giai_5", 6, 4),
    ("giai_6", 3, 3),
    ("giai_7", 4, 2),
]

DIGIT_ONLY = re.compile(r"^\d+$")


def validate_prizes(prizes: dict) -> bool:
    for key, count, digits in PRIZE_SPEC:
        value = prizes.get(key)
        if value is None:
            raise ValueError(f"Missing key: {key}")
        if count == 1:
            values = [value]
        else:
            values = value
            if len(values) != count:
                raise ValueError(f"{key}: expected {count} values, got {len(values)}")
        for v in values:
            if not DIGIT_ONLY.match(v):
                raise ValueError(f"{key}: digits only, got '{v}'")
            if len(v) != digits:
                raise ValueError(f"{key}: expected {digits} digits, got {len(v)} in '{v}'")
    return True
