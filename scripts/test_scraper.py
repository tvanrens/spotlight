"""Offline regression tests for older Warwick records and matching."""
import datetime
from scripts.update import parse, same_work, classify, normalize_title, source_details
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

from scripts.update import popular_fallback, source_material
assert classify({"title":"Subsidise fruits and vegetables to encourage healthy and sustainable diets",
                 "source":"https://doi.org/10.25250/thescbr.brk710",
                 "doi":"10.25250/thescbr.brk710"}) == "popular"
assert classify({"title":"Video: The SALIENT Sufra Food Bank Trial",
                 "source":"https://www.youtube.com/watch?v=fbXL9Yd-J1c"}) == "popular"
intro = popular_fallback({"title":"Written evidence to the House of Lords Select Committee on Food, Diet and Obesity"})
assert "written evidence" in intro and "House of Lords" in intro
assert "results show" not in intro.lower()
assert "consultation response" in popular_fallback({
    "title":"Response to the Dutch government consultation on the sugar tax"})
assert source_material({"source":"","abstract":""}) == ("", "insufficient public source text")

print("Scraper regression tests passed")

assert classify({
    "title": "Would you like a food parcel or supermarket gift card? Results from a trial testing what happens when you give people a choice of support in a food bank setting",
    "source": "https://www.liverpool.ac.uk/population-health/about/public-health-policy-and-systems/salient-sufra/"
}) == "popular"
from scripts.update import draft
import inspect
implementation = inspect.getsource(draft)
assert "300 <= count <= 1000" in implementation
assert "if attempt:" in implementation

assert "sufra" in popular_fallback({
    "title": "Video: The SALIENT Sufra Food Bank Trial"
}).lower()
assert "supermarket vouchers" in popular_fallback({
    "title": "Video: The SALIENT Sufra Food Bank Trial"
}).lower()
assert source_details("https://www.youtube.com/watch?v=fbXL9Yd-J1c") == {}
from scripts.update import choose_image
assert choose_image({"id":"publication-826da0169a5f","title":"Video: The SALIENT Sufra Food Bank Trial"}).endswith("publication-826da0169a5f.svg")
