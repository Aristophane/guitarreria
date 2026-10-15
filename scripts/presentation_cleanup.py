"""Remove legacy decorative leaders; present useful catalogue details directly."""
import copy,re
from lxml import html,etree
from navigation_copy import update_navigation_copy

ORNAMENT=re.compile(r'\.{4,}|_{5,}|-{7,}|\*{5,}|={5,}|…{2,}')

def clean_text(value):
 if not value:return value
 # Dotted wrappers and standalone separator lines are layout, not prose.
 wrapped=bool(re.match(r'^\s*(?:'+ORNAMENT.pattern+r')',value))
 if wrapped:
  value=re.sub(r'^\s*(?:'+ORNAMENT.pattern+r')\s*','',value)
  value=re.sub(r'\s*(?:'+ORNAMENT.pattern+r')\s*$','',value)
 return ORNAMENT.sub(lambda m:'…' if m.group().lstrip().startswith(('.','…')) else ' ',value)

def normal(value):return re.sub(r'\s+',' ',value or '').strip()

def prioritize_available(tree):
 # Keep the catalogue's categories and anchors while partitioning the cards.
 for catalogue in tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," catalog-list ")]'):
  before=list(catalogue.xpath('./article[@data-catalog-entry]'))
  if not before:continue
  groups=[];pending=[]
  for child in list(catalogue):
   if child.tag=='article' and child.get('data-catalog-entry'):
    if pending or not groups:groups.append({'headings':pending,'cards':[]});pending=[]
    groups[-1]['cards'].append(child)
   else:pending.append(child)
  for child in list(catalogue):catalogue.remove(child)
  emitted=set()
  for available in (True,False):
   for index,group in enumerate(groups):
    cards=[card for card in group['cards'] if (card.get('data-status')=='disponible')==available]
    if not cards:continue
    batch=etree.SubElement(catalogue,'div',{'class':'catalog-batch','data-catalog-batch':str(index)+('-available' if available else '-other')})
    for heading in group['headings']:
     clone=copy.deepcopy(heading)
     if index in emitted:
      for element in clone.iter():element.attrib.pop('id',None)
     batch.append(clone)
    emitted.add(index)
    for card in cards:batch.append(card)
  for child in pending:catalogue.append(child)
  expected=[card for card in before if card.get('data-status')=='disponible']+[card for card in before if card.get('data-status')!='disponible']
  assert catalogue.xpath('.//article[@data-catalog-entry]')==expected,'Catalogue partition changed the instruments or their stable order'

def catalogue_details(original,label):
 tree=html.fragment_fromstring(original,create_parent='div')
 result=etree.Element('div',{'class':'instrument-specs'})
 seen=set();heading=normal(clean_text(label)).casefold()
 candidates=tree.xpath('.//p | .//*[contains(concat(" ",normalize-space(@class)," ")," source-cell ") and not(.//p) and not(.//*[contains(concat(" ",normalize-space(@class)," ")," source-cell ")])]')
 for source in candidates:
  value=normal(clean_text(''.join(source.itertext())))
  key=value.casefold()
  if not value or not re.search(r'\w',value) or key in heading or key in seen:continue
  # Availability is already shown by the reconciled status above the instrument.
  if re.fullmatch(r'[\s:./,;()\-–—]*(?:(?:disponible|available|vendu[e]?|sold|réservé[e]?|reserved|indisponible|unavailable|non disponible|not available)[\s:./,;()\-–—]*)+',value,re.I):continue
  seen.add(key);node=copy.deepcopy(source);node.tag='p';node.attrib.clear()
  for image in list(node.xpath('.//img')):image.getparent().remove(image)
  node.tail='\n';result.append(node)
 # Keep any original fragment destinations, including entries grouped as duplicates.
 for identifier in set(tree.xpath('.//@id'))-set(result.xpath('.//@id')):etree.SubElement(result,'span',{'id':identifier})
 return etree.tostring(result,encoding='unicode',method='html') if len(result) else ''

def clean_presentation(markup,route=''):
 tree=html.document_fromstring(markup)
 update_navigation_copy(tree,route)
 if route=='fr_guitars.html':prioritize_available(tree)
 for node in tree.iter():
  if not isinstance(node.tag,str) or node.tag in ('script','style'):continue
  node.text=clean_text(node.text)
  for child in node:child.tail=clean_text(child.tail)
 # Empty ornamental paragraphs should not leave a large blank gap.
 for paragraph in list(tree.xpath('//main//p')):
  if not normal(''.join(paragraph.itertext())) and not paragraph.xpath('.//img | .//a | .//*[@id]') and not paragraph.get('id') and not paragraph.get('role') and not paragraph.get('aria-live'):
   paragraph.getparent().remove(paragraph)
 return '<!doctype html>'+etree.tostring(tree,encoding='unicode',method='html')
