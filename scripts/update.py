"""Refresh Warwick publications with Playwright and draft source-grounded features.
Requires OPENAI_API_KEY for newly generated 500–1000 word articles.
Existing human-reviewed articles are never overwritten.
"""
import os, re, json, sys, datetime, hashlib
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
ROOT=Path(__file__).resolve().parents[1]
PROFILE='https://profiles.warwick.ac.uk/ecslak-thijs-van-rens/publications'
PUB=ROOT/'data/publications.json'; ARTICLES=ROOT/'data/articles.json'
TYPES=['JOURNAL ARTICLE','PREPRINT / WORKING PAPER','PREPRINT','WORKING PAPER','CONFERENCE','INTERNET PUBLICATION','MEDIA','BOOK','BOOK CHAPTER','CHAPTER','OTHER','REPORT','WRITTEN EVIDENCE']
DATE_RE=re.compile(r'(?<!\d)(\d{1,2}\s+[A-Z][a-z]{2,8}\s+20\d\d|[A-Z][a-z]{2,8}\s+20\d\d)(?!\d)')

def crawl():
    """Fetch every Warwick results page rather than stopping at the first 25."""
    from playwright.sync_api import sync_playwright
    texts, links, visited = [], {}, set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent='Mozilla/5.0 (compatible; ResearchStoriesBot/1.0)')
        page.goto(PROFILE, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(1400)
        for _ in range(20):
            content = page.locator('body').inner_text(timeout=15000)
            marker = re.search(r'Showing page\s+(\d+),?\s+outputs', content, re.I)
            fingerprint = marker.group(1) if marker else hashlib.sha1(content.encode()).hexdigest()
            if fingerprint in visited: break
            visited.add(fingerprint)
            texts.append(content)
            for a in page.locator('a[href]').all():
                try:
                    title = a.inner_text(timeout=300).strip()
                    href = a.get_attribute('href')
                    if title and href and len(title) > 18 and not title.upper().startswith('DOI'):
                        links[title.casefold()] = urljoin(PROFILE, href)
                except Exception: pass
            # Warwick has used button, link and text-only pagination controls.
            # Iterate all visible "Next" controls, rather than assuming role=button.
            changed = False
            controls = page.get_by_text('Next', exact=True)
            print('Pagination controls:',controls.count(),'from page',fingerprint)
            for btn in controls.all():
                try:
                    node = btn.evaluate("(el) => ({tag: el.tagName, role: el.getAttribute('role'), html: el.outerHTML.slice(0,500)})")
                    print('Next control:',node)
                    if not btn.is_visible() or not btn.is_enabled(): continue
                    btn.click(timeout=3500)
                    page.wait_for_timeout(1750)
                    next_text = page.locator('body').inner_text(timeout=12000)
                    next_marker = re.search(r'Showing page\s+(\d+),?\s+outputs',next_text,re.I)
                    next_page = next_marker.group(1) if next_marker else None
                    if next_page and next_page != fingerprint:
                        changed = True
                        break
                except Exception as exc:
                    print('Cannot advance with Next:',str(exc)[:200])
            if not changed: break
        browser.close()
    print(f'Warwick pages retrieved: {len(texts)}; linked titles: {len(links)}')
    return texts, links


def parse(texts, links, today=None):
    """Read records from all pages, including PREPRINT and year-only dates."""
    output = {}
    now = today or datetime.date.today()
    cutoff = now.replace(year=now.year - 4)
    type_pattern = '|'.join(re.escape(t) for t in sorted(TYPES, key=len, reverse=True))
    date_re = re.compile(r'(?<!\d)(?:\d{1,2}\s+[A-Za-z]{3,9}\s+20\d{2}|[A-Za-z]{3,9}\s+20\d{2}|20\d{2})(?!\d)')
    for text in texts:
        # Avoid repeating the introductory pagination and navigation elements.
        area = text.rsplit('Showing page', 1)[-1] if 'Showing page' in text else text
        segments = re.split(r'\n\s*('+type_pattern+r')\s*\n', area)
        for pos in range(1, len(segments)-1, 2):
            output_type = segments[pos]
            seg = segments[pos+1]
            lines = [x.strip() for x in seg.splitlines() if x.strip()]
            if len(lines) < 2: continue
            title = lines[0].strip()
            # Date belongs to first publication detail lines, not to abstract citations.
            date_line = next((l for l in lines[1:5] if date_re.search(l)), '')
            match = date_re.search(date_line)
            if not match or len(title) < 14: continue
            raw_date = match.group(0)
            try:
                dt = dateparser.parse(raw_date, default=datetime.datetime(now.year, 1, 1)).date()
            except (ValueError, OverflowError, TypeError): continue
            if dt < cutoff or dt > now: continue
            link = links.get(title.casefold(), '')
            if not link:
                title_key = title.casefold()
                link = next((v for k,v in links.items()
                             if k.startswith(title_key[:65]) or title_key.startswith(k[:65])), '')
            doi_match = re.search(r'10\.\d{4,9}/[^\s<]+', seg)
            doi = doi_match.group(0).rstrip('.,;') if doi_match else ''
            if not link and doi: link = 'https://doi.org/' + doi
            if not link: continue
            ident = 'publication-' + hashlib.sha1((doi.lower() or title.casefold()).encode()).hexdigest()[:12]
            # Text between the DOI details and MORE VIEW MORE INFO is often the
            # complete Warwick abstract. Do not use the list of coauthors as text.
            abstract = ''
            if doi_match:
                abstract = seg[doi_match.end():]
            elif 'MORE VIEW MORE INFO' in seg:
                abstract = seg.split('MORE VIEW MORE INFO', 1)[-1]
            abstract = re.sub(r'(?i)\b(?:MORE VIEW MORE INFO|VIEW MORE INFO|SEE MORE)\b', ' ', abstract)
            abstract = abstract.strip()[:8000]
            if len(abstract) < 100: abstract = ''
            output[ident] = {
                'id':ident, 'title':title, 'date':dt.isoformat(),
                'type':output_type.title(), 'source':link, 'doi':doi,
                'abstract':abstract, 'angle':title, 'teaser':'',
                'status':'candidate'
            }
    return output


def extract_source(url):
 if 'papers.ssrn.com' in url:return '' # Often blocked; do not rely on incomplete page
 try:
  r=requests.get(url,timeout=25,headers={'User-Agent':'Mozilla/5.0 (academic digest; contact via thijsvanrens.com)'})
  if r.status_code!=200:return ''
  if 'pdf' in r.headers.get('content-type','').lower() or r.content[:4]==b'%PDF':
   from io import BytesIO
   from pypdf import PdfReader
   pdf=PdfReader(BytesIO(r.content))
   return '\n'.join((page.extract_text() or '') for page in pdf.pages[:35])[:45000]
  soup=BeautifulSoup(r.text,'html.parser')
  for tag in soup(['script','style','header','footer','nav','aside']):tag.decompose()
  node=soup.find('main') or soup.find('article') or soup
  lines=[x.strip() for x in node.stripped_strings if len(x.strip())>30]
  return '\n'.join(lines)[:45000]
 except Exception as ex:
  print('Source fetch failed:',url,ex);return ''

def draft(pub,text):
 from openai import OpenAI
 client=OpenAI()
 system=('You are a careful science journalist. Write 500–1000 words of readable UK English with concrete explanations, limited jargon and an engaging headline. '
 'Only state numerical results and causal claims actually supported by the supplied source. Clearly distinguish observational associations, trials and intentions. '
 'Do not invent numbers, quotes, conclusions, image provenance, or dates. If source lacks enough evidence, respond with JSON {"skip":true}. '
 'Output JSON keys: angle (catchy 5–12 word headline), teaser (under 100 words), paragraphs (array of 7–11 substantial paragraphs), category, tags (array of up to 3 topical hashtags without #).')
 user=json.dumps({'title':pub['title'],'date':pub['date'],'record_abstract':pub['abstract'],'original_url':pub['source'],'source_text':text},ensure_ascii=False)
 r=client.chat.completions.create(model=os.getenv('OPENAI_MODEL','gpt-4.1-mini'),response_format={'type':'json_object'},messages=[{'role':'system','content':system},{'role':'user','content':user}])
 j=json.loads(r.choices[0].message.content)
 if j.get('skip'):return None
 paragraphs=j.get('paragraphs',[])
 count=sum(len(x.split()) for x in paragraphs)
 if not 500<=count<=1000 or len(j.get('teaser','').split())>=100:raise ValueError(f'Unexpected content length: {count} words')
 return j


# Published stories remain the authoritative editorial source. Scraped candidates are
# suggestions only; they never become public cards until their content is complete.
import unicodedata
from difflib import SequenceMatcher

POPULAR_HOSTS = ('ox.ac.uk', 'warwick.ac.uk', 'wellcome.org', 'sky.com',
                 'skynews.com', 'committees.parliament.uk', 'nature.com')
POPULAR_PHRASES = ('podcast:', 'blog post:', 'news article:', 'written evidence',
                   'policy consultation', 'internetconsultatie', 'response to the')
ACADEMIC_HINTS = ('doi.org/', 'pubmed.', 'journals.', 'academic.oup.com',
                  'frontiersin.org', 'springer.com', 'ssrn.com')
BANNED_TEASERS = ('explore the research behind', '...see more', 'view more info')

def canonical_doi(value):
    v = str(value or '').strip().lower()
    v = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', v)
    return v.rstrip('.,;')

def normalize_title(title):
    s = unicodedata.normalize('NFKD', title or '').lower()
    s = re.sub(r'\([^)]*(?:minute|starts at|my bit|listen)[^)]*\)', '', s)
    s = re.sub(r'\b(?:video|podcast|news article|blog post)\s*:\s*', '', s)
    s = re.sub(r'\b(p\d{1,3}|op\d{1,3})\s+', '', s)
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    for prefix in ('podcast ', 'blog post ', 'news article '):
        if s.startswith(prefix): s = s[len(prefix):]
    return s

def same_work(a, b):
    da, db = canonical_doi(a.get('doi')), canonical_doi(b.get('doi'))
    if da and db and da == db: return True
    ta, tb = normalize_title(a.get('title')), normalize_title(b.get('title'))
    if not ta or not tb: return False
    if ta == tb: return True
    # Prefixes such as P81 / OP81 and minor wording differences are common
    # in Warwick's publication records.
    return SequenceMatcher(None, ta, tb).ratio() >= 0.86 if (ta.startswith(tb[:35]) or tb.startswith(ta[:35])) else SequenceMatcher(None, ta, tb).ratio() >= 0.91

def classify(p):
    if p.get('kind') in ('academic', 'popular'): return p['kind']
    title = (p.get('title') or '').lower()
    url = (p.get('source') or '').lower()
    if title.startswith(POPULAR_PHRASES + ('video:',)) or 'thesciencebreaker' in url or any(t in url for t in ('/news/','/impact/','/blog/','/podcast/','/writtenevidence/')):
        return 'popular'
    if any(t in url for t in ACADEMIC_HINTS) or canonical_doi(p.get('doi')):
        return 'academic'
    if any(t in url for t in POPULAR_HOSTS): return 'popular'
    return 'academic'

def good_metadata(p):
    a = (p.get('authors') or '').strip()
    v = (p.get('venue') or '').strip()
    return bool(a and v and 'to be verified' not in (a+' '+v).lower())

def good_teaser(p):
    t = (p.get('teaser') or '').strip()
    return bool(20 <= len(t.split()) < 100 and not any(b in t.lower() for b in BANNED_TEASERS)
                and not t.lower().startswith(('10.', 'doi:', 'context:')))

def doi_details(doi):
    """Crossref journal metadata, including abstracts where available."""
    doi = canonical_doi(doi)
    if not doi: return {}
    try:
        response = requests.get('https://api.crossref.org/works/'+doi,
                                timeout=16, headers={'User-Agent':'ResearchSpotlight/1.0 (tvanrens@gmail.com)'})
        if not response.ok: return {}
        msg = response.json().get('message',{})
        authors = ', '.join(' '.join(filter(None,[a.get('given',''),a.get('family','')]))
                            for a in msg.get('author',[]))
        venue = (msg.get('container-title') or [''])[0]
        abstract_html = BeautifulSoup(msg.get('abstract',''), 'html.parser')
        abstract = abstract_html.get_text(' ',strip=True)
        return {'authors':authors,'venue':venue,'abstract':abstract,
                'publisher':msg.get('publisher',''),'doi':doi}
    except Exception as e:
        print('Crossref lookup failed:',doi,str(e))
        return {}


def openalex_details(pub):
    """OpenAlex can resolve DOI metadata and open-access full-text links."""
    from urllib.parse import quote
    doi=canonical_doi(pub.get('doi'))
    title=pub.get('title','')
    urls=[]
    if doi: urls.append('https://api.openalex.org/works/https://doi.org/'+quote(doi,safe='/'))
    if title: urls.append('https://api.openalex.org/works?search='+quote(title)+'&per-page=5')
    for url in urls:
        try:
            response=requests.get(url,timeout=18,headers={'User-Agent':'ResearchSpotlight/1.0'})
            if not response.ok: continue
            payload=response.json()
            works=payload.get('results',[]) if 'results' in payload else [payload]
            for w in works:
                if not same_work(pub, {'title':w.get('display_name',''),
                                       'doi':w.get('doi','')}): continue
                authors=', '.join(a.get('author',{}).get('display_name','')
                                  for a in w.get('authorships',[]) if a.get('author',{}).get('display_name'))
                source=(w.get('primary_location') or {}).get('source') or {}
                venue=source.get('display_name','')
                inv=w.get('abstract_inverted_index') or {}
                terms=[(position,word) for word,positions in inv.items() for position in positions]
                abstract=' '.join(word for _,word in sorted(terms))[:12000]
                oa=w.get('best_oa_location') or {}
                pdf=oa.get('pdf_url') or ''
                return {'authors':authors,'venue':venue,'abstract':abstract,
                        'pdf_url':pdf if pdf.startswith('https://') else ''}
        except Exception as e:
            print('OpenAlex lookup failed:',str(e))
    return {}


def source_material(pub, crossref=None, openalex=None):
    """Prefer full text, fall back to descriptive abstracts with explicit limitations."""
    crossref=crossref or {}
    openalex=openalex or {}
    sources=[pub.get('source','')]
    oa_pdf=openalex.get('pdf_url','')
    if oa_pdf and oa_pdf not in sources: sources.append(oa_pdf)
    candidates=[]
    for link in sources[:2]:
        if not link: continue
        content=extract_source(link)
        if content: candidates.append((len(content),content,link))
    if candidates:
        length,text,url=max(candidates)
        if length>=1900: return text, 'full-text candidate ('+url+')'
    abstract=max([pub.get('abstract',''),crossref.get('abstract',''),
                  openalex.get('abstract','')],key=len)
    # An abstract can support a careful general-audience summary, but the
    # generated article must never invent effects or imply full-text review.
    if len(abstract)>=650: return abstract, 'abstract only'
    if candidates and max(x[0] for x in candidates)>=1100:
        return max(candidates)[1], 'partial source text'
    return '', 'insufficient public source text'


def choose_image(p):
    """Reuse existing local editorial images; never auto-publish an external hotlink."""
    title=(p.get('title') or '').lower()
    rules=[
      (('podcast','food for thought'),'images/microphone.webp'),
      (('parliament','house of lords','committee'),'images/parliament.webp'),
      (('wage','labour','employment','unemployment'),'images/labour-city.webp'),
      (('pantry','food insecurity','food bank','community food'),'images/supermarket-aisle.webp'),
      (('sugar','tax','drink','soda'),'images/supermarket-shopper.webp'),
      (('environment','sustainab','climate','planet'),'images/landscape-sunset.webp'),
      (('grocery','supermarket','shopping','swap','food'),'images/market-feature.webp'),
    ]
    for terms, image in rules:
        if any(term in title for term in terms):
            return image
    return 'images/conference.webp'

def source_details(url):
    """Return publisher-supplied description, byline and venue when available.
    Never assign an unverified individual author."""
    try:
        resp = requests.get(url, timeout=25, headers={'User-Agent':'Mozilla/5.0'})
        if not resp.ok or 'html' not in resp.headers.get('content-type','').lower(): return {}
        soup = BeautifulSoup(resp.text, 'html.parser')
        def meta(*names):
            for name in names:
                tag = soup.find('meta', attrs={'name':name}) or soup.find('meta', attrs={'property':name})
                if tag and tag.get('content'): return tag['content'].strip()
            return ''
        description = meta('description','og:description','twitter:description')
        author = meta('citation_author','author','article:author')
        venue = meta('citation_journal_title','citation_conference_title','og:site_name')
        node = soup.find('article') or soup.find('main') or soup
        paragraphs = [p.get_text(' ', strip=True) for p in node.find_all('p')]
        intro = next((p for p in paragraphs if len(p.split()) >= 18), '')
        return {'intro':intro or description,'authors':author,'venue':venue}
    except Exception as e:
        print('Metadata fetch failed:', url, str(e))
        return {}

def excerpt(text, limit=25):
    # Short attributed source excerpts; don't copy a long copyrighted article.
    words = re.sub(r'\s+', ' ', text or '').strip().split()
    return ' '.join(words[:limit]) + ('…' if len(words)>limit else '')

def main():
    published = json.loads(PUB.read_text())
    articles = json.loads(ARTICLES.read_text())
    candidates_path = ROOT/'data/candidates.json'
    report_path = ROOT/'data/discovery-report.md'
    previous = json.loads(candidates_path.read_text()) if candidates_path.exists() else []
    today = datetime.date.today()
    cutoff = today.replace(year=today.year-4)
    kept, audit = [], []
    for p in published:
        if not cutoff <= datetime.date.fromisoformat(p['date']) <= today: continue
        p['kind'] = classify(p)
        if p['kind'] == 'academic' and not (p['id'] in articles and
                 500 <= len(' '.join(articles[p['id']]).split()) <= 1000): continue
        if p['kind'] == 'popular' and not p.get('source'): continue
        if any(same_work(p,q) for q in kept): continue
        kept.append(p)
    try:
        texts, links = crawl()
        scraped = list(parse(texts, links).values())
        if not texts or not scraped: raise RuntimeError('No Warwick publication records could be parsed')
    except Exception as ex:
        if os.getenv('DISCOVERY_ONLY') == '1':
            raise RuntimeError('Discovery audit failed: Warwick returned no parseable records') from ex
        print('Warwick crawl failed; retaining existing stories:',repr(ex))
        scraped = []
        audit.append(('ERROR','Warwick source could not be parsed; existing publications retained',str(ex),''))
    print('Unique recent records from Warwick:',len(scraped))
    if os.getenv('DISCOVERY_ONLY') == '1':
        report=['# Warwick four-year discovery diagnostic','',
                'Date: '+today.isoformat(),'',
                'Candidate records: '+str(len(scraped)),'',
                '| Date | Output | Source |','|---|---|---|']
        for pub in sorted(scraped,key=lambda x:x['date'],reverse=True):
            report.append('| '+pub['date']+' | '+pub['title'].replace('|','/')+
                          ' | '+pub['source']+' |')
        report_path.write_text('\n'.join(report)+'\n')
        print('\n'.join(report))
        return
    pending=[]
    # Avoid re-querying sources for the same known candidate twice in one run.
    for p in scraped:
        if any(same_work(p,old) for old in kept):
            audit.append(('ALREADY ON SITE',p['title'],p['date'],p['source']))
            continue
        if any(same_work(p,old) for old in pending):
            audit.append(('DUPLICATE',p['title'],p['date'],p['source']))
            continue
        p['kind'] = classify(p)
        p['local_image'] = choose_image(p)
        p['image_alt'] = 'Editorial illustration related to '+p['title'][:80]
        details = source_details(p['source'])
        p['authors'] = details.get('authors','')
        p['venue'] = details.get('venue','')
        if p['kind'] == 'popular':
            p['type'] = 'Popular writing'
            p['angle'] = p['title']
            intro = details.get('intro','')
            if intro and len(intro.split())>=18:
                p['teaser'] = excerpt(intro)
                p['status'] = 'popular-source-excerpt'
                kept.append(p)
                audit.append(('PROPOSED popular link',p['title'],p['date'],p['source']))
                continue
            p['status']='needs-original-introduction'
            p['review_reason']='Original article introduction unavailable (link / login / JS or redirect)'
        else:
            p['type']='Academic publication'
            crossref = doi_details(p.get('doi'))
            openalex = openalex_details(p)
            p['authors'] = crossref.get('authors') or openalex.get('authors') or p['authors']
            p['venue'] = crossref.get('venue') or openalex.get('venue') or p['venue']
            fulltext, basis = source_material(p,crossref,openalex)
            p['evidence_basis'] = basis
            if good_metadata(p) and fulltext and os.getenv('OPENAI_API_KEY'):
                try:
                    p['abstract'] = max([p.get('abstract',''),crossref.get('abstract',''),
                                         openalex.get('abstract','')],key=len)
                    generated = draft(p,fulltext)
                    if generated:
                        for key in ('angle','teaser','tags'):
                            p[key] = generated[key]
                        if not good_teaser(p): raise ValueError('Generated teaser failed editorial checks')
                        articles[p['id']] = generated['paragraphs']
                        p['status']='ai-draft-needs-review'
                        kept.append(p)
                        audit.append(('PROPOSED academic story ('+basis+')',p['title'],p['date'],p['source']))
                        continue
                except Exception as ex:
                    p['review_reason']='Draft generation failed: '+str(ex)[:200]
            if not good_metadata(p):
                p['review_reason']='Missing verified authors or journal/venue'
            elif not fulltext:
                p['review_reason']='Insufficient full text or detailed abstract'
            elif not os.getenv('OPENAI_API_KEY'):
                p['review_reason']='OPENAI_API_KEY secret unavailable'
            p['status']='needs-source-or-metadata-review'
        pending.append(p)
        audit.append(('NEEDS REVIEW: '+p.get('review_reason','unknown'),p['title'],p['date'],p['source']))
    # Do not carry stale duplicates into the register.
    pending = [p for p in previous if not any(same_work(p,x) for x in kept+pending)]+pending
    kept.sort(key=lambda p:p['date'],reverse=True)
    pending.sort(key=lambda p:p.get('date',''),reverse=True)
    candidates_path.write_text(json.dumps(pending,indent=2,ensure_ascii=False)+'\n')
    PUB.write_text(json.dumps(kept,indent=2,ensure_ascii=False)+'\n')
    ARTICLES.write_text(json.dumps(articles,indent=2,ensure_ascii=False)+'\n')
    (ROOT/'data/site-data.js').write_text(
        '/* Generated; do not edit by hand. */\nwindow.RESEARCH_DATA = '+
        json.dumps({'publications':kept,'articles':articles},ensure_ascii=False).replace('</','<\\/')+';\n')
    # The report makes omissions visible and reviewable rather than silent.
    lines=['# Four-year Warwick discovery report','',
           f'Generated: {today.isoformat()} (publication cutoff {cutoff.isoformat()})','',
           f'- Warwick candidate records: **{len(scraped)}**',
           f'- Proposed website stories (including existing): **{len(kept)}**',
           f'- Pending records requiring human review: **{len(pending)}**','',
           'Status | Publication | Date | Source','--- | --- | --- | ---']
    for status,title,date,source in audit:
        title=title.replace('|','/').replace('\n',' ')
        status=status.replace('|','/').replace('\n',' ')
        lines.append(f'{status} | {title} | {date} | {source}')
    report_path.write_text('\n'.join(lines)+'\n')
    print(f'Prepared {len(kept)} unique stories, {len(pending)} review candidates,'
          ' and a full discovery report in data/discovery-report.md')

if __name__ == '__main__':
    main()
