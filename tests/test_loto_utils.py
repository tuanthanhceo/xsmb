from src.utils.loto_utils import compute_loto, compute_de_dau, compute_de_duoi, build_raw_string

SAMPLE_PRIZES = {
    "giai_db": "56848",
    "giai_1": "73483",
    "giai_2": ["92423", "03127"],
    "giai_3": ["91144", "79528", "68003", "34736", "86805", "73286"],
    "giai_4": ["8396", "4678", "6700", "0668"],
    "giai_5": ["9231", "4787", "8494", "9238", "8841", "1247"],
    "giai_6": ["214", "587", "621"],
    "giai_7": ["52", "55", "92", "91"],
}


def test_compute_loto():
    loto = compute_loto(SAMPLE_PRIZES)
    assert len(loto) == 27
    assert loto == [
        "00", "03", "05", "14", "21", "23", "27", "28",
        "31", "36", "38", "41", "44", "47", "48", "52",
        "55", "68", "78", "83", "86", "87", "87", "91",
        "92", "94", "96",
    ]


def test_compute_de_dau():
    assert compute_de_dau("56848") == "48"


def test_compute_de_duoi():
    assert compute_de_duoi(["52", "55", "92", "91"]) == "52"


def test_build_raw_string():
    raw = build_raw_string(SAMPLE_PRIZES)
    assert len(raw) == 107
    assert raw == "56848734839242303127911447952868003347368680573286839646786700066892314787849492388841124721458762152559291"
