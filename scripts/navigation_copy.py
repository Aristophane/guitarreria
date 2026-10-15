"""Update only interface instructions that describe the former website."""
import copy,re
from lxml import html,etree
from editorial_layout import slice_inline,append_text,normalized

NAVIGATION_EDITS=[]

def replace_phrase(paragraph,old,replacement,route):
 value=''.join(paragraph.itertext())
 match=re.search(r'\s+'.join(re.escape(word) for word in old.split()),value)
 if not match:return paragraph
 result=etree.Element(paragraph.tag,dict(paragraph.attrib))
 pieces=[slice_inline(paragraph,0,match.start()),html.fragment_fromstring(replacement,create_parent='div'),slice_inline(paragraph,match.end(),len(value))]
 for piece in pieces:
  append_text(result,piece.text)
  for child in piece:result.append(copy.deepcopy(child))
 for identifier in set(paragraph.xpath('.//@id'))-set(result.xpath('.//@id')):etree.SubElement(result,'span',{'id':identifier})
 result.tail=paragraph.tail
 paragraph.getparent().replace(paragraph,result)
 NAVIGATION_EDITS.append({'page':route,'before':normalized(value),'after':normalized(''.join(result.itertext()))})
 return result

def update_navigation_copy(tree,route):
 maker=tree.xpath('//div[contains(@class,"detail-actions")]/a[starts-with(@href,"l_")]')
 maker_href=maker[0].get('href') if maker else None
 def biography(label='biographie'):
  assert maker_href,'A real maker link is required for '+route
  return '<a href="'+maker_href+'">'+label+'</a>'
 for paragraph in list(tree.xpath('//main//p | //main//*[contains(concat(" ",normalize-space(@class)," ")," source-cell ") and not(.//p) and not(.//*[contains(concat(" ",normalize-space(@class)," ")," source-cell ")])]')):
  value=normalized(''.join(paragraph.itertext()))
  if route in ('fr_guitars.html','fr_guitars_archives.html'):
   paragraph=replace_phrase(paragraph,'infos si la page existe vous la trouverez en lien ci-dessous si la ligne apparaît en surbrillance lorsque vous y passez votre pointeur, sinon, patience...nous y travaillons...','infos. Lorsqu’une fiche est disponible, ouvrez-la avec le lien « Voir l’instrument ».',route)
   if value.startswith('ouvrez la page de chaque guitare au départ de la liste ci-dessous'):
    paragraph=replace_phrase(paragraph,value,'Pour consulter une fiche, sélectionnez la photo ou le nom de la guitare, ou le lien « Voir l’instrument ».',route)
   elif 'nom en bleu' in value and 'liste des luthiers' in value:
    paragraph=replace_phrase(paragraph,value,'Les présentations des luthiers sont accessibles depuis les fiches des instruments et la page « <a href="fr_luthiers.html">Luthiers</a> ».',route)
  if route=='fr_luthiers.html':
   paragraph=replace_phrase(paragraph,'Dans cette liste ici à votre gauche,','Dans cette liste,',route)
   if value.startswith('plusieurs pages sont déjà ouvertes (en cliquant sur les noms en bleu'):
    paragraph=replace_phrase(paragraph,value,'Explorez la carte pour situer les ateliers, ou sélectionnez un nom dans la liste pour ouvrir la présentation du luthier.',route)
  if route=='fr_philo.html':
   paragraph=replace_phrase(paragraph,'Dans la liste ici à votre gauche,','Dans la page « <a href="fr_luthiers.html">Luthiers</a> »,',route)
   paragraph=replace_phrase(paragraph,"Si ces pages ne sont pas encore composées la ligne n'apparaît pas en surbrillance lorsque vous y passez le pointeur",'Sélectionnez un nom dans la page « <a href="fr_luthiers.html">Luthiers</a> » pour consulter sa présentation.',route)
  if route.startswith('g_') and ('bleu' in value):
   replacements=[
    ('(pour voir sa biographie : cliquez sur son nom -le lien en bleu- en haut de cette page)',lambda:'(voir sa '+biography()+')'),
    ('(voir la biographie : cliquez sur son nom en bleu en haut de page)',lambda:'(voir sa '+biography()+')'),
    ('voyez en détail la biographie du luthier: lien sur le nom en bleu en haut de cette page',lambda:'Consultez la '+biography('biographie du luthier')+'.'),
    ('voir le lien sur le nom en bleu en haut de cette page',lambda:'consultez la '+biography('présentation du luthier')),
    ('(voyez en détail sur la page du luthier: lien sur le nom en bleu)',lambda:'(voir la '+biography('présentation du luthier')+')'),
    ('dont vous trouverez le lien au départ de son nom sur le haut de cette page en bleu (comme sur chacune des pages de présentation)',lambda:'accessible par le lien « '+biography('Pierre Abondance')+' »'),
    ('sa page de biographie (accessible à partir du ien en cliquant sur nom en bleu au haut de cette page...)',lambda:'sa '+biography())
   ]
   for old,replacement in replacements:
    if re.search(r'\s+'.join(re.escape(word) for word in old.split()),''.join(paragraph.itertext())):
     paragraph=replace_phrase(paragraph,old,replacement(),route)
  if route.startswith('l_') and value=="-> cliquez sur l'image pour voir la page de chaque guitare":
   paragraph=replace_phrase(paragraph,value,'Agrandissez les photos en les sélectionnant. Les liens sous les photos donnent accès aux fiches des guitares.',route)
