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

def main():
 existing=json.loads(PUB.read_text());article=json.loads(ARTICLES.read_text());known={p.get('doi') or p['title'].lower():p for p in existing}
 try:texts,links=crawl();found=parse(texts,links)
 except Exception as ex:print('Warwick crawl failed; keeping existing content:',repr(ex));found={}
 print(f'Found {len(found)} recent candidate records')
 for item in found.values():
  key=item.get('doi') or item['title'].lower()
  if key in known:continue
  known[key]=item
 today=datetime.date.today();cutoff=today.replace(year=today.year-2)
 kept=[p for p in known.values() if cutoff<=datetime.date.fromisoformat(p['date'])<=today]
 for p in kept:
  if p['id'] in article or not os.getenv('OPENAI_API_KEY'):continue
  text=extract_source(p['source'])
  if len(text)<1300 and len(p.get('abstract',''))<850:
   print('Insufficient source information; no invented article:',p['title']);continue
  try:
   result=draft(p,text)
   if result:
    for key in ('angle','teaser','category','tags'):p[key]=result[key]
    article[p['id']]=result['paragraphs'];p['status']='ai-draft-needs-review'
  except Exception as ex:print('Article generation skipped:',p['title'],ex)
 kept.sort(key=lambda p:p['date'],reverse=True)
 PUB.write_text(json.dumps(kept,indent=2,ensure_ascii=False)+'\n')
 ARTICLES.write_text(json.dumps(article,indent=2,ensure_ascii=False)+'\n')
 (ROOT/'data/site-data.js').write_text('/* Generated; do not edit by hand. */\nwindow.RESEARCH_DATA = '+json.dumps({'publications':kept,'articles':article},ensure_ascii=False).replace('</','<\\/')+';\n')
 print(f'Prepared data for editorial review: {len(kept)} recent outputs, {len(article)} complete articles')
if __name__=='__main__':main()
