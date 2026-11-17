"""Language-specific, deterministic analysis tokens and source-relative offsets."""
from dataclasses import dataclass
from functools import lru_cache
import re
import unicodedata

EN_FORMS={}
for root,forms in {
    'condemn':['condemns','condemned','condemning'],
    'protest':['protests','protested','protesting'],
    'lodge':['lodges','lodged','lodging'],
    'take':['takes','took','taken','taking'],
    'impose':['imposes','imposed','imposing'],
    'suspend':['suspends','suspended','suspending'],
    'terminate':['terminates','terminated','terminating'],
    'restriction':['restrictions'],'measure':['measures'],
    'sanction':['sanctions'],'warning':['warnings'],'claim':['claims'],
    'agreement':['agreements'],'violation':['violations'],
}.items():
    for form in forms:EN_FORMS[form]=root

@dataclass(frozen=True)
class Token:
    surface:str
    lemma:str
    pos:str
    start:int
    end:int
    sentence:int
    content:bool=True

def prepare(text):
    # No translation, OCR or guessed repair of PDF word wrapping.
    return ' '.join(unicodedata.normalize('NFC',text).split())

def sentence_spans(text):
    start=0;out=[]
    for m in re.finditer(r'[。！？!?;；]|\.(?=\s|$)',text):
        out.append((start,m.end()));start=m.end()
    if start<len(text):out.append((start,len(text)))
    return out

class Segmenter:
    def __init__(self):self.kiwi=None;self.janome=None

    @lru_cache(maxsize=4096)
    def tokenize(self,text,language):
        if language not in {'en','ko','ja'}:raise ValueError('Unsupported language')
        text=prepare(text);spans=sentence_spans(text)
        def sentence(pos):
            return next((i for i,(a,b) in enumerate(spans) if a<=pos<b),max(0,len(spans)-1))
        out=[]
        if language=='en':
            for m in re.finditer(r"[^\W\d_]+(?:['’][^\W\d_]+)*|\d+(?:[.,]\d+)*",text,re.UNICODE):
                form=m[0].casefold().replace('’',"'")
                out.append(Token(m[0],EN_FORMS.get(form,form),'WORD',m.start(),m.end(),sentence(m.start())))
        elif language=='ko':
            if self.kiwi is None:
                from kiwipiepy import Kiwi
                self.kiwi=Kiwi(num_workers=1,model_type='cong')
                self.kiwi.global_config.space_tolerance=1
            for t in self.kiwi.tokenize(text):
                pos=t.tag.split('-')[0]
                if pos.startswith(('S','W')) and pos not in {'SL','SH','SN'}:continue
                if not any(c.isalnum() for c in t.form):continue
                out.append(Token(text[t.start:t.start+t.len],t.form.casefold(),pos,t.start,t.start+t.len,
                                 sentence(t.start),not pos.startswith(('J','E'))))
        else:
            if self.janome is None:
                from janome.tokenizer import Tokenizer
                self.janome=Tokenizer()
            cursor=0
            for t in self.janome.tokenize(text):
                start=text.find(t.surface,cursor)
                if start<0:raise ValueError('Janome surface cannot be aligned to analysis text')
                cursor=start+len(t.surface);pos=t.part_of_speech
                if pos.startswith('記号') or not any(c.isalnum() for c in t.surface):continue
                lemma=t.base_form if t.base_form!='*' else t.surface
                out.append(Token(t.surface,lemma.casefold(),pos,start,cursor,sentence(start),
                                 not pos.startswith(('助詞','助動詞'))))
        return tuple(out)

    def phrase(self,text,language):
        return tuple(t.lemma for t in self.tokenize(text,language) if t.content)
