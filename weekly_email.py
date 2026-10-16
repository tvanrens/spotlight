"""Weekly story + platform-specific draft email. Requires SMTP credentials."""
import os,json,datetime,ssl,smtplib,html
from pathlib import Path
from email.message import EmailMessage
ROOT=Path(__file__).resolve().parents[1]
posts=json.loads((ROOT/'data/publications.json').read_text())
posts.sort(key=lambda p:p['date'],reverse=True)
articles=json.loads((ROOT/'data/articles.json').read_text())
ready=[p for p in posts if p['id'] in articles and articles[p['id']]]
posts=ready or posts
index=max(0,(datetime.date.today()-datetime.date(2026,10,12)).days//7)%len(posts)
p=posts[index];base=os.getenv('SITE_URL','https://YOUR-USERNAME.github.io/research-spotlight').rstrip('/')
url=base+'/#article/'+p['id'];tags=' '.join('#'+x.replace(' ','') for x in p.get('tags',[])[:3]);short_tags=' '.join('#'+x.replace(' ','') for x in p.get('tags',[])[:2]);
linkedin=f"{p['angle']}\n\n{p['teaser']}\n\nI explore the research, what the evidence does (and doesn't) show, and why it matters.\n\nRead the story: {url}\nOriginal output: {p['source']}\n\n{tags} #Research #Economics"
x=f"{p['angle']}\n\n{p['teaser'].split('.')[0]}.\n\n{url}\n{short_tags}"
if len(x)>275:x=f"{p['angle']}\n{url}\n{short_tags}"
bluesky=f"{p['angle']}\n\n{p['teaser'].split('.')[0]}.\n\n{url}\n{short_tags}"
if len(bluesky)>295:bluesky=f"{p['angle']}\n{url}\n{short_tags}"
text=f"WEEKLY RESEARCH SPOTLIGHT — {datetime.date.today():%d %B %Y}\n\n{p['title']}\n{p['teaser']}\n\nStory: {url}\nOriginal: {p['source']}\n\nLINKEDIN DRAFT\n{linkedin}\n\nX DRAFT\n{x}\n\nBLUESKY DRAFT\n{bluesky}\n\nReview before posting; these are drafts, not published posts."
(ROOT/'data/weekly-drafts.txt').write_text(text)
print(text)
if os.getenv('SMTP_HOST') and os.getenv('SMTP_USERNAME') and os.getenv('SMTP_PASSWORD'):
 msg=EmailMessage();msg['Subject']='Research spotlight + social posts: '+p['angle'];msg['From']=os.getenv('EMAIL_FROM',os.getenv('SMTP_USERNAME'));msg['To']='tvanrens@gmail.com';msg.set_content(text)
 host=os.environ['SMTP_HOST'];port=int(os.getenv('SMTP_PORT','465'))
 with smtplib.SMTP_SSL(host,port,context=ssl.create_default_context()) as smtp:
  smtp.login(os.environ['SMTP_USERNAME'],os.environ['SMTP_PASSWORD']);smtp.send_message(msg)
 print('Email delivered to SMTP server')
else:print('No SMTP credentials: generated draft locally, email not sent.')
