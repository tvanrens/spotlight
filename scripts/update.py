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
TYPES=['JOURNAL ARTICLE','PREPRINT / WORKING PAPER','CONFERENCE','INTERNET PUBLICATION','MEDIA','BOOK','CHAPTER','OTHER','REPORT']
DATE_RE=re.compile(r'(?<!\d)(\d{1,2}\s+[A-Z][a-z]{2,8}\s+20\d\d|[A-Z][a-z]{2,8}\s+20\d\d)(?!\d)')

def crawl():
 from playwright.sync_api import sync_playwright
 texts=[]; links={}
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True)
  page=browser.new_page(user_agent='Mozilla/5.0 (compatible; ResearchStoriesBot/1.0; personal academic publication digest)')
  page.goto(PROFILE,wait_until='domcontentloaded',timeout=60000)
  page.wait_for_timeout(2200)
  for i in range(8):
   content=page.locator('body').inner_text(timeout=15000)
   if content in texts:break
   texts.append(content)
   for a in page.locator('a[href]').all():
    try:
     title=a.inner_text(timeout=500).strip();href=a.get_attribute('href')
     if title and href and len(title)>24 and not title.startswith('DOI'): links[title.lower()]=urljoin(PROFILE,href)
    except Exception:pass
   buttons=page.get_by_role('button',name='Next',exact=True)
   advanced=False
   for btn in buttons.all():
    if btn.is_enabled():
     try:btn.click(timeout=2500);page.wait_for_timeout(1200);advanced=True;break
     except Exception:pass
   if not advanced:break
  browser.close()
 return texts,links

def parse(texts,links):
 output={};now=datetime.date.today();cutoff=now.replace(year=now.year-2)
 for text in texts:
  area=text.split('Showing page',1)[-1]
  segments=re.split(r'\n\s*(?:'+'|'.join(re.escape(t) for t in TYPES)+r')\s*\n',area)
  for seg in segments[1:]:
   lines=[x.strip() for x in seg.splitlines() if x.strip()]
   if len(lines)<2:continue
   title=lines[0];match=DATE_RE.search('\n'.join(lines[1:7]))
   if not match or len(title)<14:continue
   try:dt=dateparser.parse(match.group(1),default=datetime.datetime(now.year,1,1)).date()
   except (ValueError,OverflowError):continue
   if dt<cutoff or dt>now:continue
   link=links.get(title.lower(),'')
   if not link:
    link=next((v for k,v in links.items() if k.startswith(title.lower()[:65])),'')
   doi_match=re.search(r'10\.\d{4,9}/[^\s]+',seg)
   doi=doi_match.group(0).rstrip('.,') if doi_match else ''
   if not link and doi:link='https://doi.org/'+doi
   if not link:continue
   ident='publication-'+hashlib.sha1((doi or title.lower()).encode()).hexdigest()[:12]
   abstract=seg.split('DOI:',1)[-1] if 'DOI:' in seg else ''
   abstract=re.split('MOREVIEW MORE INFO|\nPDF\n|Co-authors:',abstract)[-1].strip()[:3800]
   if len(abstract)<80:abstract=''
   output[ident]={'id':ident,'title':title,'date':dt.isoformat(),'type':'Research output','source':link,'doi':doi,'category':'Research','abstract':abstract,'angle':title,'teaser':(abstract[:230].rsplit(' ',1)[0]+'…') if abstract else 'Explore the research behind this recent output.','image':'https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=1200&q=85','local_image':'images/market-feature.webp','image_alt':'Research notes and data','tags':['Research'],'status':'metadata-only'}
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
    return SequenceMatcher(None, ta, tb).ratio() >= 0.91

def classify(p):
    if p.get('kind') in ('academic', 'popular'): return p['kind']
    title = (p.get('title') or '').lower()
    url = (p.get('source') or '').lower()
    if title.startswith(POPULAR_PHRASES) or any(t in url for t in ('/news/','/impact/','/blog/','/podcast/','/writtenevidence/')):
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
    """Retrieve indexed academic attribution instead of inventing a byline."""
    doi = canonical_doi(doi)
    if not doi: return {}
    try:
        response = requests.get('https://api.crossref.org/works/'+doi,
                                timeout=20, headers={'User-Agent':'ResearchSpotlight/1.0 (academic bibliography)'})
        if not response.ok: return {}
        msg = response.json().get('message',{})
        authors = ', '.join(' '.join(filter(None,[a.get('given',''),a.get('family','')]))
                            for a in msg.get('author',[]))
        venue = (msg.get('container-title') or [''])[0]
        return {'authors':authors, 'venue':venue}
    except Exception as e:
        print('Crossref lookup failed:',doi,str(e))
        return {}

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
    previous = json.loads(candidates_path.read_text()) if candidates_path.exists() else []
    today = datetime.date.today()
    cutoff = today.replace(year=today.year-2)
    # Retain approved, complete, unique articles; avoid changing their copy.
    kept = []
    for p in published:
        if not cutoff <= datetime.date.fromisoformat(p['date']) <= today: continue
        p['kind'] = classify(p)
        if p['kind'] == 'academic' and not (p['id'] in articles and
                 500 <= len(' '.join(articles[p['id']]).split()) <= 1000): continue
        if p['kind'] == 'popular' and not p.get('source'): continue
        if any(same_work(p, q) for q in kept): continue
        kept.append(p)
    try:
        texts, links = crawl()
        scraped = list(parse(texts, links).values())
    except Exception as ex:
        print('Warwick crawl failed; retaining existing stories:', repr(ex))
        scraped = []
    print('New Warwick records discovered:', len(scraped))
    pending = []
    for p in scraped:
        if any(same_work(p, old) for old in kept): continue
        if any(same_work(p, old) for old in pending): continue
        p['kind'] = classify(p)
        details = source_details(p['source'])
        if p['kind'] == 'academic':
            crossref = doi_details(p.get('doi'))
            details['authors'] = crossref.get('authors') or details.get('authors','')
            details['venue'] = crossref.get('venue') or details.get('venue','')
        p['authors'] = details.get('authors','')
        p['venue'] = details.get('venue','')
        p['local_image'] = choose_image(p)
        p['image_alt'] = 'Editorial illustration related to '+p['title'][:80]
        if p['kind'] == 'popular':
            # No AI article: use a short source excerpt and link to the original.
            intro = details.get('intro','')
            if intro:
                p['teaser'] = excerpt(intro)
                p['status'] = 'popular-source-excerpt'
            else:
                p['status'] = 'needs-source-review'
            p['angle'] = p['title']
            p['type'] = 'Popular writing'
            if p['status'] == 'popular-source-excerpt':
                kept.append(p)
                continue
        else:
            source_text = extract_source(p['source'])
            if good_metadata(p) and len(source_text) >= 1300 and os.getenv('OPENAI_API_KEY'):
                try:
                    generated = draft(p, source_text)
                    if generated:
                        for key in ('angle','teaser','tags'): p[key] = generated[key]
                        articles[p['id']] = generated['paragraphs']
                        p['status'] = 'ai-draft-needs-review'
                        if good_teaser(p):
                            kept.append(p)
                            continue
                except Exception as ex:
                    print('Draft needs manual attention:', p['title'], repr(ex))
            p['status'] = 'needs-source-or-metadata-review'
        pending.append(p)
    # Store source candidates for review, not on the public site.
    pending = [p for p in previous if not any(same_work(p, x) for x in kept + pending)] + pending
    kept.sort(key=lambda p:p['date'], reverse=True)
    candidates_path.write_text(json.dumps(pending,indent=2,ensure_ascii=False)+'\n')
    PUB.write_text(json.dumps(kept,indent=2,ensure_ascii=False)+'\n')
    ARTICLES.write_text(json.dumps(articles,indent=2,ensure_ascii=False)+'\n')
    (ROOT/'data/site-data.js').write_text(
        '/* Generated; do not edit by hand. */\nwindow.RESEARCH_DATA = '+
        json.dumps({'publications':kept,'articles':articles},ensure_ascii=False).replace('</','<\\/')+';\n')
    print(f'Prepared {len(kept)} unique stories and {len(pending)} source candidates for PR approval.')

if __name__ == '__main__':
    main()
