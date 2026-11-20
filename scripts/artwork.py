"""Generate a deterministic, topic-specific SVG thumbnail for a new publication.

Existing artwork is never overwritten. No external image services or stock-photo
licensing required, and new thumbnails are committed as part of the editorial PR.
"""
from pathlib import Path
import hashlib
import html
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'images' / 'editorial'

MOTIFS = {
    'voucher': '<rect x="12" y="23" width="76" height="53" rx="8"/><path d="M12 41H88 M25 62H47"/>',
    'food': '<path d="M14 44H86L75 85H25Z M32 44L44 15 M68 44L56 15 M34 59H66"/>',
    'plant': '<path d="M84 15C43 13 13 35 19 63C24 89 65 93 84 15Z M20 80C36 57 57 41 78 26"/>',
    'money': '<ellipse cx="50" cy="27" rx="30" ry="12"/><path d="M20 27V68C20 85 80 85 80 68V27 M20 47C20 63 80 63 80 47"/>',
    'study': '<rect x="24" y="14" width="54" height="73" rx="5"/><path d="M37 34H64 M37 49H64 M37 64H64"/>',
    'health': '<path d="M50 85L18 54C-2 33 26 8 50 33C74 8 102 33 82 54Z"/>',
    'work': '<circle cx="33" cy="28" r="12"/><circle cx="69" cy="31" r="10"/><path d="M11 82V69C11 51 57 51 57 69V82 M60 57C84 53 90 65 90 77V82"/>',
    'world': '<circle cx="50" cy="50" r="36"/><path d="M32 18L44 32L41 48L22 52L30 69L52 79L61 65L73 61L66 45L79 32"/>',
    'media': '<rect x="15" y="23" width="70" height="55" rx="8"/><path d="M43 37L63 50L43 63Z"/>',
    'chart': '<path d="M13 13V86H88 M24 68L43 46L57 56L81 25 M68 25H81V38"/>'
}
TOPICS = [
    (('video', 'podcast', 'film'), 'media'),
    (('gift card', 'voucher', 'payment card'), 'voucher'),
    (('fruit', 'vegetable', 'diet', 'food', 'grocery', 'supermarket', 'pantry'), 'food'),
    (('climate', 'environment', 'planet', 'net zero'), 'world'),
    (('tax', 'subsid', 'price', 'promotion', 'inflation'), 'money'),
    (('health', 'obesity', 'fasting', 'stigma'), 'health'),
    (('wage', 'skill', 'worker', 'employment', 'labour'), 'work'),
    (('trial', 'research', 'evaluation', 'study'), 'study'),
]

def ensure_artwork(pub):
    """Return a unique locally hosted image for an article or write it once."""
    ident = re.sub(r'[^a-zA-Z0-9_-]', '-', pub['id'])[:80]
    relative = f'images/editorial/{ident}.svg'
    path = ROOT / relative
    if path.is_file():
        return relative
    title = pub.get('title', 'Research output')
    normalized = title.lower()
    motif = next((name for words, name in TOPICS
                  if any(word in normalized for word in words)), 'chart')
    digest = hashlib.sha256(pub['id'].encode()).digest()
    tones = [
        ('#23514A', '#CBE9D5', '#F3D188'),
        ('#395879', '#C8DFEB', '#F1BE87'),
        ('#63516A', '#DCD0ED', '#E8C77A'),
        ('#725044', '#F0D3BA', '#B9DCC7'),
        ('#355E62', '#C7E5E3', '#EFC49A'),
    ]
    dark, light, accent = tones[digest[0] % len(tones)]
    # Distinctive short label, derived from the specific source title.
    words = re.findall(r"[A-Za-zÀ-ÿ0-9]+", title)
    words = [w for w in words if w.lower() not in ('video', 'podcast', 'news', 'article', 'blog')]
    short = words[:5] or ['Research']
    halfway = min(3, max(1, len(short)//2 + 1))
    line1 = html.escape(' '.join(short[:halfway]).upper())
    line2 = html.escape(' '.join(short[halfway:]).upper())
    # Restrict on-image text lengths to avoid overflow.
    def fit(line):
        return 66 if len(line) < 17 else (48 if len(line) < 24 else 36)
    glyph = MOTIFS[motif]
    overlay = MOTIFS['chart' if motif != 'chart' else 'study']
    x = 975 if digest[1] % 2 else 215
    label_x = 75 if x == 975 else 680
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 740" width="1200" height="740" role="img" aria-label="{html.escape(title, quote=True)}">
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="{light}"/><stop offset="1" stop-color="#FAF8F0"/></linearGradient>
<pattern id="dots" width="27" height="27" patternUnits="userSpaceOnUse"><circle cx="3" cy="3" r="2.3" fill="{dark}" opacity=".08"/></pattern></defs>
<rect width="1200" height="740" fill="url(#bg)"/><rect width="1200" height="740" fill="url(#dots)"/>
<circle cx="{x}" cy="315" r="246" fill="{dark}"/>
<circle cx="{x + 24}" cy="291" r="207" stroke="#fff" stroke-opacity=".22" stroke-width="3" fill="none"/>
<g transform="translate({x - 170} 145) scale(3.4)" fill="none" stroke="white" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">{glyph}</g>
<g transform="translate({x + (-280 if x > 600 else 220)} 465)"><rect width="155" height="155" rx="35" fill="{accent}"/>
<g transform="translate(20 20) scale(1.15)" fill="none" stroke="{dark}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">{overlay}</g></g>
<text x="{label_x}" y="110" font-family="Arial,sans-serif" font-size="24" font-weight="700" letter-spacing="6" fill="{dark}">RESEARCH SPOTLIGHT</text>
<text x="{label_x}" y="447" font-family="Arial,sans-serif" font-size="{fit(line1)}" font-weight="800" fill="{dark}">{line1}</text>
<text x="{label_x}" y="532" font-family="Arial,sans-serif" font-size="{fit(line2)}" font-weight="800" fill="{dark}">{line2}</text></svg>'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding='utf-8')
    return relative
