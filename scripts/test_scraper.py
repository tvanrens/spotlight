"""Offline regression tests for older Warwick records and matching."""
import datetime
from scripts.update import parse, same_work, classify, normalize_title
sample = """Outputs
Showing page 1 out of 4
Showing page 1, outputs 1 to 25 of 76
PREPRINT
Why wages move with the economy: a working paper
8 Sep 2025 Warwick
Co-authors:
Author A
MORE VIEW MORE INFO
JOURNAL ARTICLE
Delayed adjustment and persistence in macroeconomic models
1 Sep 2023 Journal of Money, Credit and Banking
Co-authors:
Van Rens T
DOI: 10.1111/jmcb.13011
MORE VIEW MORE INFO
JOURNAL ARTICLE
Rethinking the skills gap
2023 IZA World of Labor
Co-authors:
Rathelot R
DOI: 10.15185/izawol.391.v2
MORE VIEW MORE INFO
"""
links={"why wages move with the economy: a working paper":"https://example.org/paper"}
found=parse([sample],links,today=datetime.date(2026,11,19))
assert len(found)==3, f"Expected 3 records (PREPRINT, 2023 journal, year-only), got {list(found)}"
titles=[p['title'] for p in found.values()]
assert "Rethinking the skills gap" in titles
assert all(p['date']>="2022-11-19" for p in found.values())
assert same_work({"title":"Podcast: Food for thought – eating our way to a sustainable future (my bit starts at minute 13:12)"},{"title":"Food for thought – eating our way to a sustainable future"})
assert same_work({"title":"P81 The use of eco-labels and price discounts to promote sustainable grocery purchases"},{"title":"The use of eco-labels and price discounts to promote sustainable grocery purchases"})
assert classify({"title":"News article: Healthy food", "source":"https://www.cnbc.com/abc"})=="popular"
assert classify({"title":"Delayed adjustment", "source":"https://doi.org/10.1111/jmcb.13011", "doi":"10.1111/jmcb.13011"})=="academic"
print("Scraper regression tests passed")
