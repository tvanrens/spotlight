"""Sanity checks for publication approval and GitHub Pages rendering data."""
import json
import re
from pathlib import Path
from difflib import SequenceMatcher
ROOT = Path(__file__).resolve().parents[1]
posts = json.loads((ROOT / 'data/publications.json').read_text())
articles = json.loads((ROOT / 'data/articles.json').read_text())
assert posts, 'No published stories'
titles = []
ids = set()
for p in posts:
    assert p['id'] not in ids, f"Duplicate ID {p['id']}"
    ids.add(p['id'])
    assert p.get('source','').startswith('https://'), p['id']
    assert p.get('title') and p.get('angle'), p['id']
    assert (ROOT / p['local_image']).is_file(), 'Missing local image: '+p['local_image']
    normalized = re.sub(r'\W+', ' ', p['title'].lower()).strip()
    assert all(SequenceMatcher(None, normalized, t).ratio()<0.91 for t in titles), 'Duplicate title: '+p['title']
    titles.append(normalized)
    if p.get('kind')=='popular':
        assert p.get('teaser'), 'Popular writing needs short source description: '+p['id']
    else:
        assert p.get('authors') and p.get('venue'), 'Academic metadata incomplete: '+p['id']
        assert p['id'] in articles, 'Academic story missing: '+p['id']
        words = len(' '.join(articles[p['id']]).split())
        assert 300 <= words <= 1000, f'Article outside 300–1000 words: {p["id"]} ({words})'
data_js = (ROOT / 'data/site-data.js').read_text()
assert data_js.startswith('/* Generated; do not edit by hand. */')
site_data = json.loads(data_js.split('window.RESEARCH_DATA = ',1)[1].strip().removesuffix(';'))
assert [p['id'] for p in site_data['publications']] == [p['id'] for p in posts], 'Site data out of sync'
print(f'Validated {len(posts)} public stories; {len(articles)} archived articles; image files and metadata OK')
