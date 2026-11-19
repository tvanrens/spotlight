"""Regression check: an empty Warwick response must never become a successful refresh."""
from pathlib import Path
script = (Path(__file__).resolve().parent / 'update.py').read_text()
assert "Warwick crawl attempt {attempt}/3" in script
assert "if scraped is None:" in script
assert "Monthly refresh aborted: Warwick publication discovery failed" in script
assert "scraped = []" not in script[script.index('def main():'):]
print("Fail-closed scraper check passed")
