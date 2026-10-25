from __future__ import annotations

import random

from keeper.config import get_config
from keeper.growth import forms as FM


def test_parallel_forms_balanced():
    rng = random.Random(7)
    cats = ["tests", "security", "api_compat", "docs", "correctness"]
    bank = [{"pr": i, "difficulty": rng.uniform(1, 8), "categories": rng.sample(cats, 2), "n": 2} for i in range(40)]
    FM.bucketize(bank)
    g = get_config().growth["practice"]
    a, b = FM.parallel_forms(bank, set(), int(g["k"]), dict(g["strata"]), 3, dict(g["balance"]))
    assert len(a) == len(b) == int(g["k"])
    assert not {i["pr"] for i in a} & {i["pr"] for i in b}
    assert FM.balanced(a, b, bank, dict(g["balance"]))
