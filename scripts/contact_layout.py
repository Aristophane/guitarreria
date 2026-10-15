"""Group the original contact information without rewriting its wording."""
from collections import Counter
from lxml import html,etree
from editorial_layout import blocks,normalized,slice_inline

def contact_layout(rich,location_title):
 tree=html.fragment_fromstring(rich,create_parent='div')
 items=list(blocks(tree));used=set()
 result=etree.Element('div',{'class':'contact-content','data-original-content':'fr_contact.html'})
 def take(index,parent,css=None,tag=None):
  assert index not in used
  used.add(index);node=items[index]
  if css:node.set('class',css)
  if tag:node.tag=tag
  node.tail='\n';parent.append(node)
  return node
 def section(parent,css):return etree.SubElement(parent,'section',{'class':css})
 intro=section(result,'contact-opening')
 take(6,intro,'contact-question')
 take(7,intro,'contact-lead')
 channels=etree.SubElement(result,'div',{'class':'contact-channels'})
 phone=section(channels,'contact-phone')
 take(10,phone,'contact-label')
 take(11,phone,'contact-channel-title')
 take(12,phone,'contact-number')
 take(13,phone,'contact-whatsapp')
 take(8,phone,'contact-phone-note')
 email=section(channels,'contact-email')
 take(16,email,'contact-label','h2')
 take(17,email,'contact-email-address')
 hours=etree.SubElement(email,'div',{'class':'contact-hours'})
 # The source already separates hours, workshop activity and callback advice with br.
 original=items[9];value=''.join(original.itertext());cursor=0;cuts=[0]
 def walk(node):
  nonlocal cursor
  cursor+=len(node.text or '')
  for child in node:
   if child.tag=='br':cuts.append(cursor)
   else:walk(child)
   cursor+=len(child.tail or '')
 walk(original);cuts.append(len(value));used.add(9)
 for start,end in zip(cuts,cuts[1:]):
  part=slice_inline(original,start,end)
  if normalized(''.join(part.itertext())):part.tail='\n';hours.append(part)
 visit=etree.SubElement(result,'div',{'class':'contact-visit'})
 place=section(visit,'contact-place')
 title=etree.SubElement(place,'h2',{'class':'contact-location-title'});title.text=location_title;title.tail='\n'
 take(0,place,'contact-label')
 take(1,place,'contact-location')
 take(2,place,'contact-place-note')
 appointment=section(visit,'contact-appointment')
 take(4,appointment,'contact-appointment-title')
 # Preserve the original calendar wording and line breaks, without the empty lines.
 calendar=take(5,appointment,'contact-calendar')
 etree.strip_tags(calendar,'br')
 note=section(result,'contact-identity-note')
 take(3,note)
 social=etree.SubElement(result,'div',{'class':'contact-social'})
 skype=section(social,'contact-social-item');take(14,skype);take(15,skype)
 facebook=section(social,'contact-social-item');take(18,facebook);take(19,facebook)
 assert used==set(range(len(items))),'Unplaced contact source content'
 # Reordering changes hierarchy only: no word, destination, image or anchor is lost.
 source_tokens=Counter(normalized(''.join(tree.itertext())).split())
 target_tokens=Counter(normalized(''.join(result.itertext())).split())
 assert target_tokens==source_tokens+Counter(normalized(location_title).split()),'Contact wording changed'
 for attribute in ('href','src','id'):
  assert Counter(tree.xpath('.//@'+attribute))==Counter(result.xpath('.//@'+attribute)),attribute+' changed'
 return etree.tostring(result,encoding='unicode',method='html')
