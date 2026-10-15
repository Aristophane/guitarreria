"""Structure the existing Autres content without dropping prose, images or anchors."""
import copy,html as stdhtml,re
from collections import Counter
from lxml import html,etree
from editorial_layout import blocks,paragraphs,normalized

def reflow(rich,route):
 tree=html.fragment_fromstring(rich,create_parent='div')
 result=etree.Element('div',{'class':'rich-text book-prose','data-original-content':route})
 for block in blocks(tree):
  for part in paragraphs(block) if block.tag=='p' and not block.xpath('.//img') else [block]:
   part.tail='\n';result.append(part)
 assert normalized(''.join(tree.itertext()))==normalized(''.join(result.itertext()))
 return etree.tostring(result,encoding='unicode',method='html')

def others_layout(rich,route):
 tree=html.fragment_fromstring(rich,create_parent='div');original=normalized(''.join(tree.itertext()))
 result=etree.Element('div',{'class':'others-content rich-text','data-original-content':route})
 section=etree.SubElement(result,'section',{'class':'others-intro'})
 current=section;summary=None;event=None;mode='intro';book_grid=None;accessory_grid=None
 is_archive=route.endswith('_archives.html')
 if is_archive:mode='archive'
 def new_section(kind):
  nonlocal section,current,mode,event,summary
  mode=kind;event=None;summary=None
  section=etree.SubElement(result,'section',{'class':'others-section others-'+kind});current=section
 def new_event(block=None,label=None):
  nonlocal current,event,summary
  event=etree.SubElement(section,'details',{'class':'archive-event'})
  summary=etree.SubElement(event,'summary')
  if label:
   title=etree.SubElement(summary,'h3',{'class':'archive-title','data-ui-copy':'true'});title.text=label;title.tail='\n'
  if block is not None:
   block.tag='h3';block.set('class','archive-title');block.tail='\n';summary.append(block)
  current=etree.SubElement(event,'div',{'class':'archive-copy'})
 for block in blocks(tree):
  value=normalized(''.join(block.itertext()));ids=set(block.xpath('.//@id'))|{block.get('id')}
  if not is_archive:
   if 'in' in ids:new_section('workshop');block.tag='h2'
   elif value=='Cours':new_section('lessons');block.tag='h2';block.set('id','cours')
   elif 'bo' in ids:
    new_section('books');block.tag='h2'
   elif block.tag=='h2' and 'diapason' in value:
    new_section('accessories')
    title=etree.SubElement(section,'h2',{'data-ui-copy':'true','id':'accessoires'});title.text='Accessoires'
    accessory_grid=etree.SubElement(section,'div',{'class':'accessory-grid'})
   elif 'anipo' in ids:new_section('anipo')
   elif 'ag' in ids:new_section('agenda');block.tag='h2'
   elif 'ar' in ids:new_section('archive');block.tag='h2'
  if mode=='books' and block.tag=='h2' and 'bo' not in ids:
   if book_grid is None:book_grid=etree.SubElement(section,'div',{'class':'others-book-grid'})
   current=etree.SubElement(book_grid,'article',{'class':'others-book'});block.tag='h3'
  if mode=='accessories' and block.tag=='h2':
   current=etree.SubElement(accessory_grid,'article',{'class':'accessory-item'});block.tag='h3'
  if mode=='archive':
   if block.tag=='h2' and 'ar' not in ids:
    new_event(block);continue
   if value.startswith('hommage à un ami disparu') or value.startswith('..... Hasta siempre'):
    new_event(block);continue
   if value.startswith("non, ...ce site n'est pas dédié"):
    new_event(label='Bill Collings')
   if value.startswith('... pour que notre libre conscience'):
    new_event(label='... pour que notre libre conscience')
   if event is not None and len(current)==0 and block.tag=='p' and len(value)<180 and re.search(r'\b20\d{2}\b',value) and not block.xpath('.//img'):
    block.set('class','archive-date');block.tail='\n';summary.append(block);continue
  if block.xpath('.//img') and mode in ('workshop','archive','anipo'):block.set('class','editorial-photos')
  parts=paragraphs(block) if block.tag=='p' and not block.xpath('.//img') else [block]
  kept={i for part in parts for i in part.xpath('.//@id')}
  for identifier in ids-kept-{None}:etree.SubElement(parts[0],'span',{'id':identifier})
  for part in parts:
   part.tail='\n';current.append(part)
 # Keep the original small book presentations here, with a direct route to the new shop.
 for paragraph in result.xpath('.//section[contains(@class,"others-workshop")]/p'):
  value=normalized(''.join(paragraph.itertext()))
  if 'atelier de lutherie' in value:paragraph.set('class','service-name')
  elif 'toutes réparation' in value:paragraph.set('class','service-description')
  elif 'sur devis' in value:paragraph.set('class','service-terms')
 for paragraph in result.xpath('.//section[contains(@class,"others-lessons")]/p'):
  if 'cours guitare ' in normalized(''.join(paragraph.itertext())):paragraph.set('class','lesson-type')
 books=result.xpath('./section[contains(@class,"others-books")]')
 if books:
  action=etree.Element('p',{'class':'shop-bridge','data-ui-copy':'true'})
  link=etree.SubElement(action,'a',{'href':'fr_boutique.html','class':'text-link'});link.text='Voir la Boutique +'
  books[0].insert(1,action)
 # Validate complete original wording, including the prose in closed archive panels.
 check=copy.deepcopy(result)
 for item in check.xpath('.//*[@data-ui-copy]'):item.getparent().remove(item)
 assert normalized(''.join(check.itertext()))==original,'Autres wording or order changed'
 return etree.tostring(result,encoding='unicode',method='html')

def shop_page(books,image):
 cards=[]
 for book in books:
  cover=image(book['cover_url'],book['title_exact'])
  status='<p class="book-status">temporairement épuisé · en attente de réédition</p>' if book.get('availability_exact') else '<p class="book-status">'+stdhtml.escape(book['list_language_exact'])+'</p>'
  cards.append('<article class="shop-book"><a class="book-cover" href="'+book['route']+'" aria-label="'+stdhtml.escape(book['title_exact'],quote=True)+'">'+cover+'</a><div class="book-overview">'+status+'<h2><a href="'+book['route']+'">'+stdhtml.escape(book['title_exact'])+'</a></h2><p class="book-description">'+stdhtml.escape(book['list_description_exact'])+'</p><p class="book-price">'+stdhtml.escape(book['list_price_exact'])+'</p><a class="text-link" href="'+book['route']+'">Voir le livre <span aria-hidden="true">+</span></a></div></article>')
 return '<section class="shop-books" aria-label="Livres">'+''.join(cards)+'</section>'
