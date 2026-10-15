"""Reflow the original philosophy prose; assert unchanged wording and order."""
import copy,re
from lxml import html,etree

def normalized(value):return re.sub(r'\s+',' ',value).strip()

def append_text(node,value):
 if not value:return
 if len(node):node[-1].tail=(node[-1].tail or '')+value
 else:node.text=(node.text or '')+value

def slice_inline(node,start,end):
 result=etree.Element(node.tag,dict(node.attrib));cursor=0
 if start:result.attrib.pop('id',None)
 value=node.text or '';append_text(result,value[max(0,start):min(len(value),end)]);cursor+=len(value)
 for child in node:
  length=len(''.join(child.itertext()))
  if length and start<cursor+length and end>cursor:
   result.append(slice_inline(child,max(0,start-cursor),min(length,end-cursor)))
  cursor+=length
  tail=child.tail or ''
  if start<cursor+len(tail) and end>cursor:append_text(result,tail[max(0,start-cursor):min(len(tail),end-cursor)])
  cursor+=len(tail)
 return result

def blocks(node):
 for child in node:
  if not isinstance(child.tag,str):continue
  if child.tag in ('p','h2','h3','blockquote') or not child.xpath('.//p | .//h2 | .//h3'):
   if normalized(''.join(child.itertext())) or child.xpath('.//img'):yield copy.deepcopy(child)
  else:yield from blocks(child)

def paragraphs(node):
 value=''.join(node.itertext())
 if not value.strip() or len(normalized(value))<270:return [node]
 # Record existing line breaks without inserting or editing any characters.
 line_breaks=[];cursor=0
 def walk(el):
  nonlocal cursor
  cursor+=len(el.text or '')
  for child in el:
   if child.tag=='br':line_breaks.append(cursor)
   else:walk(child)
   cursor+=len(child.tail or '')
 walk(node)
 boundaries=set(line_breaks)
 introductory=value.lstrip().startswith('Nous vous offrons ce que vous ne trouverez nulle part ailleurs :')
 if introductory:boundaries.add(value.index(':')+1)
 boundaries.update(m.end() for m in re.finditer(r'[.!?]\s+(?=[A-ZÀÂÉÈÊÎÔÙÛÇ])',value))
 # Long sentences stay verbatim; a clause can start a separate paragraph.
 boundaries.update(m.end() for m in re.finditer(r'[,;]\s+',value))
 cuts=[0];last=0
 for boundary in sorted(boundaries):
  distance=len(normalized(value[last:boundary]))
  if introductory or (distance>=170 and (boundary in line_breaks or re.search(r'[.!?]\s*$',value[:boundary]) or distance>=240)):cuts.append(boundary);last=boundary
 cuts.append(len(value));etree.strip_tags(node,'br')
 result=[]
 for start,end in zip(cuts,cuts[1:]):
  fragment=slice_inline(node,start,end)
  if normalized(''.join(fragment.itertext())):result.append(fragment)
 assert normalized(''.join(node.itertext()))==normalized(' '.join(''.join(p.itertext()) for p in result))
 return result

def philosophy_layout(rich):
 tree=html.fragment_fromstring(rich,create_parent='div');original=normalized(''.join(tree.itertext()))
 content=etree.Element('div',{'class':'philosophy-prose','data-original-content':'fr_philo.html'})
 section=etree.SubElement(content,'section',{'class':'philosophy-section','id':'philosophie-concept'})
 navigation=[('philosophie-concept','Notre philosophie')]
 for block in blocks(tree):
  if block.tag in ('h2','h3'):
   title=normalized(''.join(block.itertext()))
   section=etree.SubElement(content,'section',{'class':'philosophy-section'})
   block.tail='\n';section.append(block);navigation.append((block.get('id'),title));continue
  parts=paragraphs(block) if block.tag=='p' and not block.xpath('.//img') else [block]
  for part in parts:
   part_text=normalized(''.join(part.itertext()))
   if part.xpath('.//img'):part.set('class','philosophy-mark')
   elif part_text.startswith('Nous vous offrons ce que vous ne trouverez nulle part ailleurs :'):part.set('class','philosophy-lead')
   elif part.tag!='p' and part.xpath('.//strong'):part.set('class','philosophy-callout')
   part.tail='\n';section.append(part)
 target=normalized(' '.join(''.join(block.itertext()) for block in content))
 if original!=target:
  import difflib
  changes=[(tag,original[a:b],target[c:d]) for tag,a,b,c,d in difflib.SequenceMatcher(None,original,target).get_opcodes() if tag!='equal']
  raise AssertionError('Philosophy wording or order changed: '+repr(changes[:8]))
 toc='<nav class="philosophy-toc" aria-label="Sommaire">'+''.join('<a href="#'+identifier+'">'+title+'</a>' for identifier,title in navigation if identifier)+'</nav>'
 return '<div class="philosophy-layout">'+toc+etree.tostring(content,encoding='unicode',method='html')+'</div>'
