"""Rebuild the complete static site from archived, traceable original content."""
from __future__ import annotations
import argparse,copy,csv,hashlib,html as stdhtml,json,re,shutil,urllib.parse as up,zipfile
from pathlib import Path
from lxml import html,etree
from editorial_layout import philosophy_layout
from others_layout import others_layout,reflow,shop_page,move_accessories
from contact_layout import contact_layout
from presentation_cleanup import catalogue_details,clean_presentation
from navigation_copy import NAVIGATION_EDITS

SCRIPT=Path(__file__).resolve()
ROOT=SCRIPT.parents[1]
SITE=ROOT/'site' if (ROOT/'audit').exists() else ROOT
DIST=SITE/'dist'
BASE='https://www.guitarreria.eu/'
HOSTS={'www.guitarreria.eu','guitarreria.eu'}
PLUS='<svg class="action-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path d="M12 4v16M4 12h16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="square"/></svg>'
DECOR={'line_grey.gif','mail_red.gif','icon_up_red.gif','close_red.gif','arrow_down_grey.gif','icon_enlarge.gif','icon_enlarge2.gif','attention_red.jpg','image006.jpg','image006a.jpg','image006b.jpg','punto_red.gif','punto_green.gif','punto_green1.gif','punto_orange.gif'}
NAV=[('Accueil','index.html'),('Guitares','fr_guitars.html'),('Luthiers','fr_luthiers.html'),('Boutique','fr_boutique.html'),('Philosophie','fr_philo.html'),('Autres','fr_others.html'),('Contact','fr_contact.html')]
LANGS={'fr':'Français','en':'English','nl':'Nederlands','es':'Español'}
AUDIT=[]
ASSETS={}
MEDIA_STATUS={}
PAGE_MAP={}
CURRENT_TITLE=''
INSTRUMENTS={}

def stock_status(value):
 # Negative phrases must precede the positive word they contain.
 if re.search(r'\bindisponible\b|\bunavailable\b|\bnon\s+disponible\b|\bnot\s+available\b',value,re.I):return 'indisponible'
 if re.search(r'\bvendu(?:e|s|es)?\b|\bsold\b',value,re.I):return 'vendu'
 if re.search(r'\br[eé]serv[eé](?:e)?\b|\breserved\b|\ben option\b',value,re.I):return 'reserve'
 if re.search(r'bient[oô]t|coming|prochainement|available soon',value,re.I):return 'prochainement'
 if re.search(r'\bdisponible\b|\bavailable\b',value,re.I):return 'disponible'
 return 'non-precise'

def instrument_index(pages,archive):
 result={}
 for page in pages:
  name=route(page['url'])
  if not name.startswith('g_'):continue
  node,_,_=content_node(page,decode(archive.read(page['archive'])))
  signals=[text(n) for n in node.xpath('.//*[contains(@class,"Style5")]') if 0<len(text(n))<120 and stock_status(text(n))!='non-precise']
  status=stock_status(' '.join(signals))
  photos=[n for n in node.xpath('.//img') if up.unquote(up.urlsplit(n.get('src','')).path).rsplit('/',1)[-1] not in DECOR and 'audio' not in n.get('src','').lower() and '/objects/' not in up.urljoin(page['url'],n.get('src',''))]
  valid=[n for n in photos if (photo_record(n.get('src',''),page['url'])[1] or {}).get('ok')]
  primary=copy.deepcopy(valid[0] if valid else photos[0]) if valid or photos else None
  if primary is not None:primary.set('src',up.urljoin(page['url'],primary.get('src','')))
  result[name]={'status':status,'status_evidence':' '.join(signals),'primary':primary,'source':page['url']}
 return result

def catalog_card(node,base,original):
 label=node.get('data-heading','');href=node.get('data-instrument-href','');status=node.get('data-status')
 labels={'disponible':'Disponible','vendu':'Vendu','indisponible':'Indisponible','reserve':'Réservé','prochainement':'Prochainement','non-precise':'Disponibilité non précisée','incertain':'À vérifier'}
 picture=node.get('data-primary-image','');attrs=' '.join(f'{k}="{esc(v)}"' for k,v in node.attrib.items() if k in ('data-catalog-entry','data-search','data-type','data-status','data-wood','data-instrument-href'))
 if picture:
  image=etree.Element('img',src=picture,alt='Photographie — '+label)
  photo=image_html(image,base)
  if href and '<img ' in photo:photo='<a class="instrument-photo" href="'+esc(local_link(href,base))+'" aria-label="'+esc(label)+'">'+photo+'</a>'
  else:photo='<div class="instrument-photo">'+photo+'</div>'
 else:photo='<div class="instrument-photo no-photo"><span>Photographie non publiée</span></div>'
 title='<a href="'+esc(local_link(href,base))+'">'+esc(label)+'</a>' if href else esc(label)
 action='<a class="instrument-action" href="'+esc(local_link(href,base))+'">Voir l’instrument '+PLUS+'</a>' if href else ''
 return '<article class="catalog-item instrument-card" '+attrs+'>'+photo+'<div class="instrument-copy"><p class="stock-status '+esc(status)+'">'+labels.get(status,'À vérifier')+'</p><h3>'+title+'</h3>'+catalogue_details(original,label)+action+'</div></article>'

def esc(s):return stdhtml.escape(str(s),quote=True)
def norm(s):return re.sub(r'\s+',' ',s or '').strip()
def text(el):return norm(''.join(el.itertext())) if isinstance(el.tag,str) else ''
def route(url):
 p=up.urlsplit(url)
 return up.unquote(p.path).lstrip('/') or 'index.html'
def lang_for(url):
 n=route(url)
 return next((l for l in LANGS if n.startswith(l+'_') or '_'+l+'_' in n),'fr')
def section_for(url):
 n=route(url)
 if n in ('fr_boutique.html','vt_g_granada.html','vt_courtnall.html','vt_440wood.html','vt_fustero.html'):return 'Boutique'
 if n.startswith('g_') or n.startswith('fr_guitars') or n=='a_recordings.html':return 'Guitares'
 if n.startswith('l_') or n=='fr_luthiers.html':return 'Luthiers'
 if n=='fr_philo.html' or n=='fr_rights.html':return 'Philosophie'
 if 'contact' in n:return 'Contact'
 if 'index' in n:return 'Accueil'
 return 'Autres'
def decode(raw):
 m=re.search(br'charset\s*=\s*["\']?([\w-]+)',raw[:5000],re.I)
 enc=m.group(1).decode('ascii') if m else 'utf-8'
 try:return raw.decode(enc)
 except (UnicodeDecodeError,LookupError):
  try:return raw.decode('utf-8')
  except UnicodeDecodeError:return raw.decode('cp1252',errors='replace')

def local_link(href,base):
 href=(href or '').strip()
 if not href:return ''
 if href.startswith('#'):return href
 if href.lower().startswith(('javascript:','data:','vbscript:')):return ''
 absolute=up.urljoin(base,href);p=up.urlsplit(absolute)
 if p.scheme not in ('http','https','mailto','tel'):return ''
 if p.hostname in HOSTS:
  target=up.urlunsplit(('https','www.guitarreria.eu',p.path or '/',p.query,''))
  if p.path in ('/','/index.html'):target=BASE
  if target in PAGE_MAP:return up.quote(PAGE_MAP[target],safe='/._-')+('#'+p.fragment if p.fragment else '')
  if target in ASSETS and ASSETS[target].get('ok'):return ASSETS[target]['public_path']+('#'+p.fragment if p.fragment else '')
  if p.path.endswith(('.html','.htm')):return '404.html?source='+up.quote(absolute,safe='')
 return absolute

def photo_record(url,base):
 absolute=up.urljoin(base,url)
 if up.urlsplit(absolute).hostname in HOSTS:absolute=up.urlunsplit(('https','www.guitarreria.eu',up.urlsplit(absolute).path,'',''))
 a=ASSETS.get(absolute)
 return absolute,a

def image_html(node,base,gallery=False,index=0):
 url,a=photo_record(node.get('src',''),base)
 name=up.unquote(up.urlsplit(url).path).rsplit('/',1)[-1]
 if name in DECOR or (route(base)=='fr_luthiers.html' and name in {'guitarreria_az2g.jpg','guitarreria_az2.jpg','guitarreria_az2d.jpg'}):return ''
 label=node.get('alt') or node.get('title') or 'Photographie — '+CURRENT_TITLE
 if name=='audio1_red.gif':return '<span class="audio-link">'+esc(node.get('title') or node.get('alt') or 'Audio')+' '+PLUS+'</span>'
 if not a or not a.get('ok'):
  if not gallery and node.xpath('ancestor::a[@href]'):
   return '<span class="missing-photo" data-photo-source="'+esc(url)+'"><span>Photographie indisponible</span><span>'+esc(label)+'</span><span>Ouvrir '+PLUS+'</span></span>'
  return '<a class="missing-photo" data-photo-source="'+esc(url)+'" href="'+esc(url)+'" rel="noopener" target="_blank"><span>Photographie indisponible</span><span>'+esc(label)+'</span><span>Voir la source '+PLUS+'</span></a>'
 w,h=a.get('dimensions',[400,300]);src=a['public_path']
 image=f'<img src="{esc(src)}" data-photo-source="{esc(url)}" width="{w}" height="{h}" loading="lazy" alt="{esc(label)}">'
 if gallery:
  button=f'<button class="gallery-photo" type="button" data-photo="{esc(src)}" data-caption="{esc(label)}" aria-label="Agrandir : {esc(label)}">{image}<span class="gallery-plus" aria-hidden="true">{PLUS}</span></button>'
  linked=next(iter(node.xpath('ancestor::a[@href]')),None)
  if linked is not None and up.urlsplit(linked.get('href','')).path.endswith(('.html','.htm')):
   return '<figure class="gallery-item">'+button+'<figcaption><a href="'+esc(local_link(linked.get('href'),base))+'">'+esc(linked.get('title') or node.get('title') or label)+' '+PLUS+'</a></figcaption></figure>'
  return button
 return image

def sanitize(node,base,extract_photos=False,skip_heading=None):
 if not isinstance(node.tag,str):return ''
 tag=node.tag.lower()
 if tag in ('script','style','noscript'):return ''
 if tag=='img':
  filename=up.unquote(up.urlsplit(node.get('src','')).path).rsplit('/',1)[-1]
  return '' if extract_photos and filename not in ('audio1_red.gif','coupdecoeur.jpg','skype_logo.jpg','asset_find_us_on_facebook_lg1.png') else image_html(node,base)
 if tag=='iframe':
  src=up.urljoin(base,node.get('src','')).replace('http://player.vimeo.com','https://player.vimeo.com')
  return f'<div class="video-frame"><iframe src="{esc(src)}" title="{esc(node.get("title") or CURRENT_TITLE)}" loading="lazy" allow="fullscreen; picture-in-picture" allowfullscreen></iframe></div>'
 if tag in ('object','embed','param'):
  if tag=='param':return ''
  url=node.get('src') or node.get('data') or next(iter(node.xpath('./param[translate(@name,"MOVIE","movie")="movie"]/@value')),'')
  if not url:return ''
  url=up.urljoin(base,url)
  asset=ASSETS.get(url,{})
  mp3=next((s for s in asset.get('strings',[]) if s.startswith('http') and s.lower().endswith('.mp3')),'')
  if mp3 and MEDIA_STATUS.get(mp3,{}).get('available'):
   return '<audio controls preload="none" src="'+esc(mp3)+'"></audio>'
  return '<div class="legacy-media"><p>Extrait audio indisponible sur son hébergement d’origine.</p>'+('<a href="'+esc(mp3)+'">Source MP3 '+PLUS+'</a> · ' if mp3 else '')+'<a href="'+esc(local_link(url,base))+'" download>Fichier d’origine '+PLUS+'</a></div>'
 if tag=='br':return '<br>'
 if tag=='hr':return '<hr>'
 if node is skip_heading:return ''
 raw_text=node.text or ''
 raw_text=re.sub(r'(?i)\bx{5,}\b','',raw_text)
 if node.xpath('ancestor::*[@data-catalog-navigation]'):raw_text=re.sub(r'^\s*-->\s*','',raw_text)
 children=esc(raw_text)
 if not node.xpath('ancestor-or-self::a[@href]'):children=re.sub(r'(\+\s*33\.648164495)',r'<a href="tel:+33648164495">\1</a>',children)
 for child in node:
  children+=sanitize(child,base,extract_photos,skip_heading)+esc(re.sub(r'(?i)\bx{5,}\b','',child.tail or ''))
 if tag=='a' and not norm(html.fromstring('<div>'+children+'</div>').text_content()) and node.get('href','').lower().startswith('mailto:'):
  children='Contact '+PLUS
 if tag=='a' and extract_photos and not norm(html.fromstring('<div>'+children+'</div>').text_content()) and node.xpath('.//img') and up.urlsplit(node.get('href','')).path.endswith(('.html','.htm')):
  children=esc(node.get('title') or next(iter(node.xpath('.//img/@title')),'') or CURRENT_TITLE)+' '+PLUS
 if not norm(html.fromstring('<div>'+children+'</div>').text_content()) and not any(t in children for t in ('<img','<iframe','gallery-photo','missing-photo','id=')) and not node.get('name') and not node.get('id'):return ''
 original_id=node.get('id') or (node.get('name') if tag=='a' else '')
 idattr=f' id="{esc(original_id)}"' if original_id else ''
 if tag=='a':
  href=local_link(node.get('href',''),base)
  if not href and node.get('title') and re.fullmatch(r'\+?[\d. ]{8,}',node.get('title')):href='tel:'+re.sub(r'[^\d+]','',node.get('title'))
  if not href:return '<span'+idattr+'>'+children+'</span>'
  title=f' title="{esc(node.get("title"))}"' if node.get('title') else ''
  external=up.urlsplit(href).scheme in ('http','https')
  unavailable_audio=href in MEDIA_STATUS and not MEDIA_STATUS[href].get('available')
  return f'<a href="{esc(href)}"{idattr}{title}'+(' rel="noopener"' if external else '')+'>'+children+'</a>'+('<span class="audio-unavailable"> — audio indisponible sur son hébergement d’origine</span>' if unavailable_audio else '')
 if tag in ('h1','h2','h3','h4'):
  if not original_id:
   identifier='s-'+hashlib.sha256((base+text(node)).encode()).hexdigest()[:10]
   idattr=f' id="{identifier}"'
  return '<'+('h2' if tag=='h1' else tag)+idattr+'>'+children+'</'+('h2' if tag=='h1' else tag)+'>'
 if tag in ('p','blockquote','ul','ol','li','strong','em','b','i','sup','sub','details','summary'):
  cls=' class="catalog-intro"' if tag=='details' and node.get('data-catalog-intro') else ''
  return '<'+tag+idattr+cls+'>'+children+'</'+tag+'>'
 if tag=='article' and node.get('data-catalog-entry'):
  return catalog_card(node,base,children)
 if tag in ('table','tbody','thead','tfoot','tr','td','th','div','center'):
  cls='source-row' if tag=='tr' else 'source-cell' if tag in ('td','th') else 'source-group'
  if node.get('data-catalog-list'):cls+=' catalog-list'
  if node.get('data-catalog-navigation'):cls+=' catalog-navigation'
  if node.get('data-catalog-heading'):cls+=' catalog-entry-line'
  if tag=='tr' and not text(node) and node.xpath('.//a[@name]'):cls+=' catalog-anchor'
  return '<div class="'+cls+'"'+idattr+'>'+children+'</div>'
 if tag in ('input','select','option','form'):return ''
 return '<span'+idattr+'>'+children+'</span>'

def content_node(page,raw):
 tree=html.fromstring(raw)
 name=route(page['url'])
 if name.startswith(('g_','l_','vt_','art_','Al_')) or name=='fr_rights.html':
  markers=list(re.finditer(r'<!--([\s\S]*?)-->',raw))
  start=next((m for m in markers if re.search(r'\bcontent\b',m.group(1),re.I) and len(m.group(1))<200),None)
  if start:
   end=next((m.start() for m in markers if m.start()>start.end() and re.search(r'\b(picto|navigation)\b',m.group(1),re.I) and len(m.group(1))<200),len(raw))
   node=html.fragment_fromstring(raw[start.end():end],create_parent='div')
   if name=='fr_rights.html':
    prefix=tree.xpath('//p[contains(normalize-space(.),"Pour toute question")]')
    if prefix:node.insert(0,copy.deepcopy(prefix[0]))
   return node,tree,'content marker'
 first=tree.xpath('//h2')[0] if tree.xpath('//h2') else None
 if first is not None:
  cells=first.xpath('ancestor::td[@width="50%"]')
  if cells:return copy.deepcopy(cells[-1]),tree,'central content cell'
 if name=='a_recordings.html':
  for td in tree.xpath('//td'):
   if td.xpath('./h2') and td.xpath('.//iframe'):return copy.deepcopy(td),tree,'recordings content cell'
  first=tree.xpath('//h2')[0]
  return copy.deepcopy(first.getparent()),tree,'recordings content'
 raise ValueError('No reliable extraction rule for '+page['url'])

def enhance_catalog(node,page):
 entries=[]
 for tr in list(node.xpath('.//tr[td[@nowrap]]')):
  if tr.xpath('ancestor::table[@border="5"]'):continue
  label=text(tr)
  links=tr.xpath('./td//a[starts-with(@href,"g_")]/@href')
  if len(label)>260 or not (links or re.search(r'\b(classical|classique|clásica|flamenc\w*|folk|jazz|crossover|mandolin\w*|oud|bouzouki)\b',label,re.I)):continue
  if tr.getparent() is None:continue
  detail=None;following=tr.getnext()
  for _ in range(4):
   if following is None:break
   if isinstance(following.tag,str) and following.xpath('.//table[@border="5"]'):
    detail=following;break
   if isinstance(following.tag,str) and text(following):break
   following=following.getnext()
  detailtext=text(detail) if detail is not None else ''
  source_status=' '.join(tr.xpath('.//a/@title'))+' '+detailtext
  catalog_status=stock_status(source_status)
  instrument=INSTRUMENTS.get(up.unquote(up.urlsplit(links[0]).path),{}) if links else {}
  # A sold/unavailable signal always excludes a listing from Available, even
  # when an older detail page still carries a positive availability phrase.
  status=stock_status(source_status+' '+instrument.get('status_evidence',''))
  typ='flamenco' if re.search('flamenc',label,re.I) else 'classique' if re.search('classi|clásica',label,re.I) else 'autres'
  material='cedre' if re.search('c[eè]dre',label,re.I) else 'epicea' if re.search('[eé]pi?c[eé]a|epicea',label,re.I) else 'non-precise'
  article=etree.Element('article',{'data-catalog-entry':'true','data-search':norm(label+' '+detailtext),'data-type':typ,'data-status':status,'data-wood':material,'data-heading':label,'data-instrument-href':links[0] if links else ''})
  if catalog_status!=status:article.set('data-stock-corrected','true')
  primary=instrument.get('primary')
  if primary is None and detail is not None:
   images=[n for n in detail.xpath('.//img') if up.unquote(up.urlsplit(n.get('src','')).path).rsplit('/',1)[-1] not in DECOR and '/objects/' not in up.urljoin(page['url'],n.get('src',''))]
   local=[n for n in images if (photo_record(n.get('src',''),page['url'])[1] or {}).get('ok')]
   primary=local[0] if local else images[0] if images else None
  if primary is not None:article.set('data-primary-image',up.urljoin(page['url'],primary.get('src','')))
  tr.set('data-catalog-heading','true')
  parent=tr.getparent();at=parent.index(tr);parent.remove(tr);article.append(tr)
  if detail is not None:
   detail.getparent().remove(detail);article.append(detail)
  parent.insert(at,article)
  entries.append({'label':label,'href':links[0] if links else None,'status':status,'catalog_status':catalog_status,'detail_status':instrument.get('status'),'detail_status_evidence':instrument.get('status_evidence'),'primary_image':article.get('data-primary-image'),'type':typ,'source_status':source_status})
 # Repeated listings share one visible instrument while retaining both source entries.
 seen={}
 for article in list(node.xpath('.//article[@data-catalog-entry]')):
  key=article.get('data-instrument-href')
  if not key:continue
  if key in seen:
   first=seen[key];first.set('data-search',first.get('data-search','')+' '+article.get('data-search',''))
   repeat=etree.SubElement(first,'div',{'class':'original-repeat'})
   for child in list(article):article.remove(child);repeat.append(child)
   article.getparent().remove(article)
  else:seen[key]=article
 for table in node.xpath('.//table'):
  if len(table.xpath('./article'))>=3:table.set('data-catalog-list','true')
 # Keep the original introduction in a disclosure so instruments are reached directly.
 introductory=etree.Element('details',{'data-catalog-intro':'true'})
 summary=etree.SubElement(introductory,'summary');summary.text='EDITO :' if 'EDITO' in text(node) else 'Informations'
 lists=node.xpath('.//table[@data-catalog-list]')
 for table in lists:
  first=next((ch for ch in table if isinstance(ch.tag,str) and ch.tag=='article'),None)
  if first is None:continue
  for child in list(table)[:table.index(first)]:
   if isinstance(child.tag,str) and (child.xpath('.//a[@name]') or text(child)=='liste actuelle :'):continue
   table.remove(child);introductory.append(child)
 for child in list(node):
  if isinstance(child.tag,str) and child.tag=='p' and text(child):node.remove(child);introductory.append(child)
 anchors=node.xpath('.//a[@href="#ac"]')
 if anchors:
  navtable=next(iter(anchors[0].xpath('ancestor::table')),None)
  if navtable is not None:navtable.set('data-catalog-navigation','true')
 if len(introductory)>1:
  at=node.index(lists[0]) if lists and lists[0].getparent() is node else 0
  node.insert(at,introductory)
 return entries

def header(section,lang='fr',current=''):
 links=''.join(f'<a href="{r}"'+(' aria-current="page"' if s==section else '')+'>'+s+'</a>' for s,r in NAV)
 languages=''.join(f'<a href="{l}_'+('contact.html' if section=='Contact' else 'index.html')+f'" lang="{l}">{name}</a>' for l,name in LANGS.items() if l!='fr')
 return f'<a class="skip-link" href="#contenu">Aller au contenu</a><header class="header" id="accueil"><div class="header-inner"><a class="brand" href="index.html" aria-label="Guitarreria.eu, accueil"><span class="brand-name">GUITARRERIA <span>.eu</span></span><span class="brand-caption">coopérative de Luthiers</span></a><nav class="nav" aria-label="Navigation principale" id="navigation">{links}</nav><div class="header-actions"><details class="languages"><summary>{LANGS[lang]} <span aria-hidden="true">⌄</span></summary><div><a href="'+('fr_contact.html' if section=='Contact' else 'index.html')+f'" lang="fr">Français</a>{languages}</div></details><button class="menu" aria-label="Ouvrir le menu" aria-expanded="false" aria-controls="navigation"><span></span><span></span></button></div></div></header>'

def footer(note=''):
 return '<footer class="footer wrap"><div class="footer-top"><a class="brand" href="index.html"><span class="brand-name">GUITARRERIA <span>.eu</span></span><span class="brand-caption">coopérative de Luthiers</span></a><nav aria-label="Langues"><a href="index.html" lang="fr">Français</a><a href="en_index.html" lang="en">English</a><a href="nl_index.html" lang="nl">Nederlands</a><a href="es_index.html" lang="es">Español</a></nav></div>'+('<p class="language-note" lang="en">'+esc(note)+'</p>' if note else '')+'<div class="footer-bottom"><a href="fr_rights.html">© Guitarreria .eu 1999-2026 All contents of this site are copyrighted by Guitarreria .eu</a><a href="#accueil" aria-label="Haut de page">'+PLUS+'</a></div></footer>'

def dialog():
 return '<dialog class="photo-dialog" aria-label="Photographie agrandie"><div class="dialog-toolbar"><p class="photo-caption"></p><button type="button" data-close-photo>Fermer</button></div><img class="photo-large" alt=""><div class="dialog-controls"><button type="button" data-prev-photo>Précédente</button><span class="photo-number" aria-live="polite"></span><button type="button" data-next-photo>Suivante</button></div></dialog>'

def filters(kind):
 if kind=='catalog':return '<form class="filters" role="search" aria-label="Rechercher une guitare"><label>Recherche<input type="search" name="q" placeholder="Luthier, modèle, bois…" autocomplete="off"></label><label>Type<select name="type"><option value="">Tous</option><option value="classique">Classique</option><option value="flamenco">Flamenco</option><option value="autres">Autres</option></select></label><label>Disponibilité<select name="status"><option value="">Tous</option><option value="disponible">Disponible</option><option value="vendu">Vendu</option><option value="indisponible">Indisponible</option><option value="reserve">Réservé</option><option value="prochainement">Prochainement</option><option value="incertain">À vérifier</option><option value="non-precise">Non précisé</option></select></label><label>Table<select name="wood"><option value="">Toutes</option><option value="epicea">Épicéa</option><option value="cedre">Cèdre</option></select></label><button type="reset">Réinitialiser</button></form><p class="result-count" role="status" aria-live="polite"></p><p class="empty-results" hidden>Aucun instrument ne correspond à ces critères.</p>'
 return '<form class="directory-search" role="search" aria-label="Rechercher un luthier"><label>Rechercher un luthier<input type="search" name="q" placeholder="Nom du luthier" autocomplete="off"></label></form><p class="result-count" role="status" aria-live="polite"></p><p class="empty-results" hidden>Aucun luthier ne correspond à cette recherche.</p>'

def gallery(photos,base):return '<div class="gallery-grid">'+''.join(image_html(n,base,True,i) for i,n in enumerate(photos))+'</div>'

def geography_directory(profiles):
 source=SITE/'source/geography.json'
 if (ROOT/'audit/geography/geography.json').exists():shutil.copy2(ROOT/'audit/geography/geography.json',source)
 data=json.loads(source.read_text(encoding='utf-8'));by_route={p['route']:p for p in data}
 assert set(by_route)=={p['route'] for p in profiles},'Geographic coverage must match the 59 original profiles'
 if (ROOT/'tools/map_assets').exists():shutil.copytree(ROOT/'tools/map_assets',SITE/'source/map',dirs_exist_ok=True)
 if (ROOT/'tools/site_map.js').exists():shutil.copy2(ROOT/'tools/site_map.js',SITE/'source/map.js')
 shutil.copytree(SITE/'source/map',DIST/'assets/map',dirs_exist_ok=True)
 shutil.copy2(SITE/'source/map.js',DIST/'map.js');shutil.copy2(source,DIST/'geography.json')
 countries=sorted({place['country'] for p in data for place in p.get('locations',[p]) if place.get('country')})
 controls='<div class="geography-countries" role="group" aria-label="Pays des ateliers"><button type="button" data-country="" aria-pressed="true">Tous les pays</button>'+''.join('<button type="button" data-country="'+esc(c)+'" aria-pressed="false">'+esc(c)+'</button>' for c in countries)+'</div>'
 map_html='<section class="geography" aria-labelledby="geography-heading"><div class="geography-heading"><div><p class="eyebrow">Géographie</p><h2 id="geography-heading">Les ateliers dans le monde</h2></div><button type="button" data-world>Vue mondiale '+PLUS+'</button></div>'+controls+'<div class="map-frame"><div id="makers-map" aria-label="Carte des villes d’atelier des luthiers" tabindex="0"></div><p class="map-loading" role="status">Chargement de la carte…</p></div><div class="map-caption"><p>Repères à l’échelle des villes. Le nombre indique les luthiers regroupés.</p><p><span class="map-key"></span>Atelier documenté <span class="map-key historical"></span>Atelier historique</p></div><p id="map-selection" class="map-selection" tabindex="-1">Monde</p><noscript><p>Activez JavaScript pour explorer la carte. Les villes des ateliers restent indiquées dans la liste.</p></noscript></section><div class="directory-heading"><h2 id="directory-heading">Tous les luthiers</h2><p id="geography-status" role="status" aria-live="polite">'+str(len(data))+' luthiers</p><button type="button" data-show-all>Afficher tous</button></div>'
 entries=[]
 map_html=map_html.replace('Atelier historique</p>','Atelier historique <span class="map-key uncertain"></span>À confirmer</p>')
 for p in sorted(profiles,key=lambda p:p['name'].casefold()):
  geo=by_route[p['route']];places=geo.get('locations',[geo]);location=' · '.join(esc(str(place.get('city') or 'Localisation non établie'))+(' — '+esc(place['country']) if place.get('country') else '') for place in places)
  labels={'historical':'Atelier historique','uncertain':'Localisation à confirmer','unknown':'Localisation non établie'}
  annotation='<span class="location-status">'+esc(labels[geo['status']])+'</span>' if geo['status'] in labels else ''
  locate='<button type="button" class="locate-maker" data-locate="'+p['route']+'">Voir sur la carte '+PLUS+'</button>' if geo.get('lat') is not None else ''
  entries.append('<article class="maker-entry" data-directory-entry data-route="'+p['route']+'"><a href="'+p['route']+'"><h3>'+esc(p['name'])+'</h3>'+PLUS+'</a><p class="maker-location">'+location+'</p>'+annotation+locate+'</article>')
 return map_html+'<section class="maker-directory" aria-label="Annuaire des luthiers">'+''.join(entries)+'</section>'

def page_shell(page,body,title,section,origin):
 lang=lang_for(page['url']);description=page.get('meta',{}).get('description','')
 note=re.search(r'the complete site[\s\S]*?other languages',page.get('text',''))
 return '<!doctype html><html lang="'+lang+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(page['title'] or title)+' — Guitarreria.eu</title><meta name="description" content="'+esc(description)+'"><link rel="canonical" href="'+esc(origin+'/'+PAGE_MAP[page['url']])+'"><link rel="stylesheet" href="style.css"><link rel="stylesheet" href="pages.css"><script src="app.js" defer></script></head><body>'+header(section,lang)+body+footer(norm(note.group()) if note else '')+dialog()+'</body></html>'

def main():
 global ASSETS,PAGE_MAP,CURRENT_TITLE,MEDIA_STATUS,INSTRUMENTS
 NAVIGATION_EDITS.clear()
 DIST.mkdir(parents=True,exist_ok=True)
 if (ROOT/'tools/branding').exists():shutil.copytree(ROOT/'tools/branding',SITE/'source/branding',dirs_exist_ok=True)
 for icon in ('favicon.svg','favicon.ico','favicon-32.png'):shutil.copy2(SITE/'source/branding'/icon,DIST/icon)
 if (SITE/'.openai/hosting.json').exists():
  manifest=json.loads((SITE/'.openai/hosting.json').read_text(encoding='utf-8'))
  manifest['static']={'directory':'dist'}
  (SITE/'.openai/hosting.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
 configuration=json.loads((SITE/'site-config.json').read_text(encoding='utf-8')) if (SITE/'site-config.json').exists() else {}
 origin=configuration.get('origin','https://guitarreria-refonte.mruppdahlem.chatgpt.site').rstrip('/')
 if (ROOT/'audit').exists():
  data=json.loads((ROOT/'audit/inventory.json').read_text(encoding='utf-8'))
  downloads=[]
  for name in ('asset-downloads.json','additional-asset-downloads.json'):
   if (ROOT/'audit'/name).exists():downloads+=json.loads((ROOT/'audit'/name).read_text(encoding='utf-8'))
  ASSETS={a['url']:a for a in downloads}
  for a in ASSETS.values():
   if a.get('ok'):
    source=ROOT/a['path'];relative=source.relative_to(ROOT/'audit/original-assets')
    a['public_path']='assets/original/'+str(relative).replace('\\','/')
    target=DIST/a['public_path'];target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists() or target.stat().st_size!=source.stat().st_size:shutil.copy2(source,target)
  source_dir=SITE/'source';source_dir.mkdir(exist_ok=True)
  if (ROOT/'audit/audio-availability.json').exists():shutil.copy2(ROOT/'audit/audio-availability.json',source_dir/'audio-availability.json')
  (source_dir/'inventory.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
  (source_dir/'assets.json').write_text(json.dumps(ASSETS,ensure_ascii=False),encoding='utf-8')
  with zipfile.ZipFile(source_dir/'original-html.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
   for p in data['pages']:z.write(ROOT/'audit'/p['archive'],p['archive'])
  for name in ('style.css','index.html'):
   if not (source_dir/('homepage-'+name)).exists():shutil.copy2(ROOT/'preview'/name,source_dir/('homepage-'+name))
  shutil.copytree(ROOT/'preview/assets/fonts',DIST/'assets/fonts',dirs_exist_ok=True)
  shutil.copytree(ROOT/'preview/assets/photos',DIST/'assets/photos',dirs_exist_ok=True)
  shutil.copy2(source_dir/'homepage-style.css',DIST/'style.css')
  shutil.copy2(source_dir/'homepage-index.html',DIST/'index.html')
  shutil.copy2(ROOT/'tools/site_pages.css',SITE/'source/pages.css')
  shutil.copy2(ROOT/'tools/catalog_editorial.css',SITE/'source/catalog-editorial.css')
  shutil.copy2(ROOT/'tools/site_app.js',SITE/'source/app.js')
  shutil.copy2(SITE/'source/pages.css',DIST/'pages.css');shutil.copy2(SITE/'source/app.js',DIST/'app.js')
 else:
  data=json.loads((SITE/'source/inventory.json').read_text(encoding='utf-8'))
  ASSETS=json.loads((SITE/'source/assets.json').read_text(encoding='utf-8'))
  shutil.copy2(SITE/'source/homepage-style.css',DIST/'style.css');shutil.copy2(SITE/'source/homepage-index.html',DIST/'index.html')
  shutil.copy2(SITE/'source/pages.css',DIST/'pages.css');shutil.copy2(SITE/'source/app.js',DIST/'app.js')
 if (SITE/'source/audio-availability.json').exists():MEDIA_STATUS={m['url']:m for m in json.loads((SITE/'source/audio-availability.json').read_text(encoding='utf-8'))}
 shutil.copy2(SITE/'source/catalog-editorial.css',DIST/'catalog-editorial.css')
 if (ROOT/'tools/others_shop.css').exists():shutil.copy2(ROOT/'tools/others_shop.css',SITE/'source/others-shop.css')
 if (ROOT/'audit/book-shop-findings.json').exists():shutil.copy2(ROOT/'audit/book-shop-findings.json',SITE/'source/book-shop.json')
 shutil.copy2(SITE/'source/others-shop.css',DIST/'others-shop.css')
 if (ROOT/'tools/contact.css').exists():shutil.copy2(ROOT/'tools/contact.css',SITE/'source/contact.css')
 shutil.copy2(SITE/'source/contact.css',DIST/'contact.css')
 books=json.loads((SITE/'source/book-shop.json').read_text(encoding='utf-8'))['books'];book_map={book['route']:book for book in books}
 PAGE_MAP={p['url']:route(p['url']) for p in data['pages']}
 by_url={p['url']:p for p in data['pages']}
 catalog_records=[];profiles=[];report=[];links_in_main=[];shop_accessories=''
 z=zipfile.ZipFile(SITE/'source/original-html.zip')
 INSTRUMENTS=instrument_index(data['pages'],z)
 for page in data['pages']:
  name=PAGE_MAP[page['url']];CURRENT_TITLE=page['headings'][0]['text'] if page['headings'] else norm(page['title'])
  if name=='index.html':
   raw=(DIST/'index.html').read_text(encoding='utf-8')
   for url,target in sorted(PAGE_MAP.items(),key=lambda x:-len(x[0])):
    if url!=BASE:raw=raw.replace('href="'+url+'"','href="'+up.quote(target,safe='/._-')+'"')
   raw=raw.replace('<meta name="robots" content="noindex,nofollow">','<link rel="canonical" href="'+origin+'/">')
   raw=raw.replace('<link rel="stylesheet" href="style.css">','<link rel="stylesheet" href="style.css"><link rel="stylesheet" href="pages.css">')
   raw=raw.replace('<script src="app.js" defer></script>','<script src="app.js" defer></script>')
   raw=raw.replace('</body>',dialog()+'</body>')
   replacement=re.search(r'<nav class="nav"[\s\S]*?</nav>',header('Accueil')).group()
   raw=re.sub(r'<nav class="nav"[\s\S]*?</nav>',lambda _:replacement,raw,count=1)
   (DIST/name).write_text(clean_presentation(raw,name),encoding='utf-8');report.append({'source':page['url'],'target':name,'kind':'approved-homepage','text_preserved':True});continue
  source=decode(z.read(page['archive']))
  node,tree,rule=content_node(page,source)
  first_heading=next(iter(node.xpath('.//h2')),None)
  if first_heading is None:first_heading=next(iter(node.xpath('.//h1')),None)
  core_original=text(node)
  kind='guitar' if name.startswith('g_') else 'luthier' if name.startswith('l_') else 'catalog' if name.startswith('fr_guitars') else 'editorial'
  if kind=='catalog':
   records=enhance_catalog(node,page);catalog_records+=records
  else:records=[]
  for i,h in enumerate(node.xpath('.//h1 | .//h2 | .//h3 | .//h4')):
   if not h.get('id'):h.set('id','s-'+hashlib.sha256((page['url']+text(h)+str(i)).encode()).hexdigest()[:10])
  photos=[n for n in node.xpath('.//img') if up.unquote(up.urlsplit(n.get('src','')).path).rsplit('/',1)[-1] not in DECOR]
  seen=set();unique=[]
  for photo in photos:
   absolute=up.urljoin(page['url'],photo.get('src',''))
   if absolute not in seen and not absolute.endswith('audio1_red.gif'):seen.add(absolute);unique.append(photo)
  extract=kind in ('guitar','luthier') or name.startswith(('vt_','art_'))
  rich=sanitize(node,page['url'],extract,first_heading)
  section=section_for(page['url'])
  breadcrumb='<nav class="breadcrumb" aria-label="Fil d’Ariane"><a href="index.html">Accueil</a><span>/</span><a href="'+dict(NAV).get(section,'index.html')+'">'+section+'</a></nav>'
  subtitle=''
  if kind=='guitar':
   cells=tree.xpath('//td[contains(concat(" ",normalize-space(@class)," ")," Style1a ")]')
   subtitle=next((text(c) for c in cells if re.search('cl[aá]s|flamenc|folk|jazz|crossover|bouzouki|mandolin',text(c),re.I)), '')
   if not subtitle:subtitle=next((line for line in page['text'].splitlines()[1:6] if len(line)<250 and re.search('cl[aá]s|flamenc|folk|jazz|crossover|bouzouki|mandolin',line,re.I)), '')
  controls=filters('catalog') if kind=='catalog' else ''
  toc=[]
  for h in node.xpath('.//h2 | .//h3'):
   if h is first_heading:continue
   ident=h.get('id')
   toc.append('<a href="#'+esc(ident)+'">'+esc(text(h))+'</a>')
  toc_html='<nav class="contents" aria-label="Sommaire">'+''.join(toc)+'</nav>' if len(toc)>1 else ''
  page_title='<div class="page-title">'+breadcrumb+'<p class="eyebrow">'+section+'</p><h1>'+esc(CURRENT_TITLE)+'</h1>'+('<p class="page-subtitle">'+esc(subtitle)+'</p>' if subtitle else '')+'</div>'
  if kind in ('guitar','luthier'):
   relationship=''
   if kind=='guitar':
    maker=next((l for l in page['links'] if '/l_fr_' in l['href']),None)
    if maker:relationship='<a class="text-link" href="'+esc(local_link(maker['href'],page['url']))+'">'+esc(maker['text'] or CURRENT_TITLE)+' '+PLUS+'</a>'
   else:
    profiles.append({'name':CURRENT_TITLE,'route':name,'source':page['url'],'photo':image_html(unique[0],page['url']) if unique else ''})
    relationship='<a class="text-link" href="fr_guitars.html?q='+up.quote(CURRENT_TITLE)+'">Les Guitares '+PLUS+'</a>'
   layout='<div class="detail-layout '+kind+'-layout"><div class="detail-gallery">'+gallery(unique,page['url'])+'</div><div class="detail-copy"><div class="rich-text" data-original-content="'+esc(name)+'">'+rich+'</div><div class="detail-actions">'+relationship+'<a class="button" href="fr_contact.html">Contact '+PLUS+'</a></div></div></div>'
  else:
   layout=controls+toc_html+'<div class="rich-text '+('catalog-content' if kind=='catalog' else 'editorial-content')+'" data-original-content="'+esc(name)+'">'+rich+'</div>'
   if name=='fr_philo.html':layout=philosophy_layout(rich)
   if name in ('fr_others.html','fr_others_archives.html'):
    shortcuts='<nav class="others-nav" aria-label="Rubriques"><a href="#in">Atelier</a><a href="#cours">Cours</a><a href="#ag">Agenda</a><a href="#ar">Archives</a></nav>' if name=='fr_others.html' else '<p class="back-link"><a href="fr_others.html#ar">Autres +</a></p>'
    layout=others_layout(rich,name)
    if name=='fr_others.html':layout,shop_accessories=move_accessories(layout)
    layout=shortcuts+layout
   if name in book_map:
    book=book_map[name]
    status='<p class="book-status">temporairement épuisé · en attente de réédition</p>' if book.get('availability_exact') else ''
    english='<a class="text-link" href="'+esc(book['english_ordering_email_href'])+'">'+esc(book['english_ordering_exact'])+' '+PLUS+'</a>' if book.get('english_ordering_email_href') else ''
    layout='<div class="book-detail-layout"><div class="book-detail-gallery">'+gallery(unique,page['url'])+'</div><div class="book-detail-copy">'+status+'<p class="book-price">'+esc(book['list_price_exact'])+'</p>'+reflow(rich,name)+english+'</div></div>'
   if extract and unique and name not in book_map:layout+='<section class="additional-photos"><h2>Photographies</h2>'+gallery(unique,page['url'])+'</section>'
  if name=='fr_contact.html':
   layout=contact_layout(rich,CURRENT_TITLE)
   page_title=page_title.replace('<h1>'+esc(CURRENT_TITLE)+'</h1>','<h1>Contact</h1>')
   brochure=next((l for l in page['links'] if '.pdf' in l['href'].lower()),None)
   if brochure:layout+='<div class="detail-actions"><a class="text-link" href="'+esc(local_link(brochure['href'],page['url']))+'" download>téléchargez ici la plaquette de contact '+PLUS+'</a></div>'
  used_urls={up.urljoin(page['url'],n.get('src','')) for n in photos}
  extras=[]
  for img in page['images']:
   url=img['url'];filename=up.unquote(up.urlsplit(url).path).rsplit('/',1)[-1]
   if url in used_urls or filename in DECOR or filename in ('guitar_2a.JPG','guitarreria1.jpg','ES-01-26(70)w.jpg','Logo_25blk.gif') or url in {up.urljoin(page['url'],n.get('src','')) for n in extras}:continue
   el=etree.Element('img',{k:str(v) for k,v in {'src':url,'alt':img.get('alt',''),'title':img.get('title','')}.items()});extras.append(el)
  if extras:layout+='<details class="supplement"><summary>Photographies complémentaires</summary>'+gallery(extras,page['url'])+'</details>'
  body='<main id="contenu" class="page-main wrap">'+page_title+layout+'</main>'
  out=page_shell(page,body,CURRENT_TITLE,section,origin)
  if name=='fr_contact.html':
   out=out.replace('<body>','<body class="contact-route">')
   out=out.replace('</head>','<link rel="stylesheet" href="contact.css?v='+hashlib.sha256((DIST/'contact.css').read_bytes()).hexdigest()[:12]+'"></head>')
  if name in ('fr_others.html','fr_others_archives.html') or name in book_map:
   out=out.replace('<body>','<body class="others-page '+('book-page' if name in book_map else '')+'">')
   out=out.replace('</head>','<link rel="stylesheet" href="others-shop.css?v='+hashlib.sha256((DIST/'others-shop.css').read_bytes()).hexdigest()[:12]+'"></head>')
   out=out.replace('src="app.js"','src="app.js?v='+hashlib.sha256((DIST/'app.js').read_bytes()).hexdigest()[:12]+'"')
  if kind=='catalog' or name=='fr_philo.html':
   out=out.replace('<body>','<body class="'+('catalog-page' if kind=='catalog' else 'philosophy-page')+'">')
   out=out.replace('</head>','<link rel="stylesheet" href="catalog-editorial.css?v='+hashlib.sha256((DIST/'catalog-editorial.css').read_bytes()).hexdigest()[:12]+'"></head>')
   out=out.replace('src="app.js"','src="app.js?v='+hashlib.sha256((DIST/'app.js').read_bytes()).hexdigest()[:12]+'"')
  if name=='fr_others.html':out=re.sub(r'(?m)[ \t]+$', '',out)
  target=DIST/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(clean_presentation(out,name),encoding='utf-8')
  # Complete source transcripts are retained in source/inventory.json, outside the UI.
  report.append({'source':page['url'],'target':name,'kind':kind,'extraction_rule':rule,'source_core_text':core_original,'core_characters':len(core_original),'images':len(unique),'extra_images':len(extras),'catalog_entries':len(records),'text_preserved':True,'source_sha256':page['sha256']})
  links_in_main.extend([{'page':name,'href':l.get('href','')} for l in node.xpath('.//a[@href]')])
 # Complete directory, including artisans whose links occur outside the homepage's sidebar.
 directory=geography_directory(profiles)
 p=DIST/'fr_luthiers.html';markup=p.read_text(encoding='utf-8');markup=markup.replace('<div class="rich-text editorial-content"',directory+'<div class="rich-text editorial-content"',1);markup=markup.replace('</head>','<link rel="stylesheet" href="assets/map/leaflet/leaflet.css"><script src="assets/map/leaflet/leaflet.js" defer></script><script src="map.js" defer></script></head>');p.write_text(markup,encoding='utf-8')
 for asset in ('pages.css','map.js'):
  markup=markup.replace('"'+asset+'"','"'+asset+'?v='+hashlib.sha256((DIST/asset).read_bytes()).hexdigest()[:12]+'"')
 markup=re.sub(r'(?m)^[ \t]+$', '',markup)
 p.write_text(markup,encoding='utf-8')
 # Dedicated shop, using the original books and accessories with their ordering routes.
 shop_info={'url':BASE+'fr_boutique.html','title':'Boutique','meta':{'description':'Livres et accessoires — Guitarreria.eu'}}
 def cover(url,title):return image_html(etree.Element('img',src=url,alt=title),BASE)
 shop_body='<main id="contenu" class="page-main wrap"><div class="page-title"><nav class="breadcrumb" aria-label="Fil d’Ariane"><a href="index.html">Accueil</a><span>/</span><span>Boutique</span></nav><p class="eyebrow">Livres et accessoires</p><h1>Boutique</h1></div>'+shop_page(books,cover,shop_accessories)+'</main>'
 PAGE_MAP[shop_info['url']]='fr_boutique.html'
 shop=page_shell(shop_info,shop_body,'Boutique','Boutique',origin).replace('<body>','<body class="shop-page">').replace('</head>','<link rel="stylesheet" href="others-shop.css?v='+hashlib.sha256((DIST/'others-shop.css').read_bytes()).hexdigest()[:12]+'"></head>')
 (DIST/'fr_boutique.html').write_text(re.sub(r'(?m)[ \t]+$', '',shop),encoding='utf-8')
 # A real missing-page response document, without a fabricated instrument description.
 (DIST/'404.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta name="robots" content="noindex"><title>Page indisponible — Guitarreria.eu</title><link rel="stylesheet" href="style.css"><link rel="stylesheet" href="pages.css"><body>'+header('Guitares')+'<main id="contenu" class="page-main wrap"><div class="page-title"><h1>Page indisponible</h1><p>Cette page n’est pas accessible dans le site d’origine.</p><a class="text-link" href="fr_guitars.html">Les Guitares '+PLUS+'</a></div></main>'+footer()+'</body></html>',encoding='utf-8')
 # All routes, including the approved homepage and the 404 document, share the icon.
 icon_version=hashlib.sha256((DIST/'favicon.svg').read_bytes()).hexdigest()[:12]
 icon_links='<link rel="icon" href="favicon.ico?v='+icon_version+'" sizes="16x16 32x32 48x48"><link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png?v='+icon_version+'"><link rel="icon" type="image/svg+xml" href="favicon.svg?v='+icon_version+'">'
 for page_path in DIST.glob('*.html'):
  markup=page_path.read_text(encoding='utf-8')
  page_path.write_text(markup.replace('</title>','</title>'+icon_links,1),encoding='utf-8')
 (DIST/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+esc(origin+'/'+r)+'</loc></url>' for r in PAGE_MAP.values())+'</urlset>',encoding='utf-8')
 (DIST/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+origin+'/sitemap.xml\n',encoding='utf-8')
 (SITE/'migration-report.json').write_text(json.dumps({'pages':len(report),'guitar_pages':sum(r['kind']=='guitar' for r in report),'luthier_pages':len(profiles),'catalog_entries':len(catalog_records),'source_404':data['errors'],'unavailable_assets':[a for a in ASSETS.values() if not a.get('ok')],'legacy_audio':list(MEDIA_STATUS.values()),'coverage':report},ensure_ascii=False,indent=2),encoding='utf-8')
 (SITE/'source/catalog-records.json').write_text(json.dumps(catalog_records,ensure_ascii=False,indent=2),encoding='utf-8')
 PAGE_MAP.pop(shop_info['url'],None) # This is a new page, not an original URL migration.
 with (SITE/'migration-routes.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f,delimiter=';');w.writerow(['URL source','Chemin cible']);w.writerows(PAGE_MAP.items())
 (SITE/'scripts').mkdir(exist_ok=True)
 if SCRIPT!=(SITE/'scripts/build_site.py'):shutil.copy2(SCRIPT,SITE/'scripts/build_site.py')
 if (SCRIPT.parent/'build_favicon.py')!=(SITE/'scripts/build_favicon.py'):shutil.copy2(SCRIPT.parent/'build_favicon.py',SITE/'scripts/build_favicon.py')
 if (SCRIPT.parent/'editorial_layout.py')!=(SITE/'scripts/editorial_layout.py'):shutil.copy2(SCRIPT.parent/'editorial_layout.py',SITE/'scripts/editorial_layout.py')
 if (SCRIPT.parent/'others_layout.py')!=(SITE/'scripts/others_layout.py'):shutil.copy2(SCRIPT.parent/'others_layout.py',SITE/'scripts/others_layout.py')
 if (SCRIPT.parent/'contact_layout.py')!=(SITE/'scripts/contact_layout.py'):shutil.copy2(SCRIPT.parent/'contact_layout.py',SITE/'scripts/contact_layout.py')
 if (SCRIPT.parent/'presentation_cleanup.py')!=(SITE/'scripts/presentation_cleanup.py'):shutil.copy2(SCRIPT.parent/'presentation_cleanup.py',SITE/'scripts/presentation_cleanup.py')
 if (SCRIPT.parent/'navigation_copy.py')!=(SITE/'scripts/navigation_copy.py'):shutil.copy2(SCRIPT.parent/'navigation_copy.py',SITE/'scripts/navigation_copy.py')
 (SITE/'navigation-copy-changes.json').write_text(json.dumps(NAVIGATION_EDITS,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'pages':len(report),'guitar_pages':sum(r['kind']=='guitar' for r in report),'luthier_pages':len(profiles),'catalog_entries':len(catalog_records),'archived_assets':sum(a.get('ok',False) for a in ASSETS.values()),'unavailable_assets':sum(not a.get('ok') for a in ASSETS.values())}),flush=True)

if __name__=='__main__':main()
