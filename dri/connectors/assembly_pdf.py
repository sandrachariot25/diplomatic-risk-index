"""Text-layer extraction of two-column public Assembly minutes; no OCR.

Turn boundaries follow printed circle speaker markers. A turn is not a whole
political event: adjacent question/answer context is retained separately.
"""
import re
from dataclasses import dataclass,asdict

VERSION='assembly-pdf-columns-v4'
MARKER=re.compile(r'^[◯○]\s*(.+)$')
LABEL=re.compile(r'^([가-힣·ㆍ]{2,30})\s+([가-힣]{2,5})(?:\s+(.*))?$')
JAPAN=re.compile(r'일본|한[·ㆍ․-]?일|(?:^|\s)일[·ㆍ․-]한')

@dataclass
class Turn:
    ordinal:int
    label:str
    speaker_name:str|None
    role:str|None
    text:str
    spans:list
    closed:bool=False
    rejection:str|None=None

    def metadata(self):return asdict(self)

def parse_label(value):
    m=LABEL.match(value)
    if not m:return None,None,''
    a,b,body=m.groups()
    # Printed 의원/위원 label order: name first, role second.
    if b in {'위원','의원'}:return a,b,body or ''
    if not re.search(r'(위원장대리|의장대리|위원장|의장|장관|차관|총리|국장|실장|청장|처장|총장|대표|대통령|비서관)$',a):
        return None,None,''
    return b,a,body or ''

def segment(lines):
    """lines: (page, column, top, bottom, text); provenance survives wrapping."""
    result=[];current=None
    for page,column,top,bottom,text in lines:
        # The appendix can contain hundreds of circles denoting bills, not speakers.
        if re.match(r'^\(\d+시.*산회\)',text.strip()):
            if current:current.closed=True;result.append(current)
            current=None
            break
        m=MARKER.match(text.strip())
        if m:
            if current:current.closed=True;result.append(current)
            name,role,body=parse_label(m[1])
            current=Turn(len(result)+1,m[1],name,role,body,[[page,column,top,bottom]])
            if name is None:current.rejection='unparsed_speaker_label'
        elif current:
            # Exclude document-level closure/attendance/annex sections, not speech.
            if re.match(r'^\(\d+시.*(?:산회|정회)\)|^[◯○](?:출석|청가)|^출석(?:위원|국무)',text.strip()):
                current.closed=True;result.append(current);current=None
                continue
            current.text+='\n'+text
            current.spans.append([page,column,top,bottom])
    if current:
        current.rejection=current.rejection or 'unclosed_at_document_end'
        result.append(current)
    for turn in result:
        turn.text=turn.text.strip()
        if '\ufffd' in turn.text or '(cid:' in turn.text:turn.rejection='unmapped_text_glyphs'
    return result

def extract(path):
    import pdfplumber
    lines=[];quality=[]
    with pdfplumber.open(path) as pdf:
        for number,page in enumerate(pdf.pages,1):
            # Header rule is at y~72, body starts at y~86 on the verified A4 layout.
            if abs(page.width-595)>3 or abs(page.height-842)>3:
                raise ValueError('Unverified page dimensions; manual layout review required')
            chars=len(page.chars)
            if chars<20:quality.append({'page':number,'issue':'sparse_text_layer'})
            for col,x0,x1 in [('L',0,page.width/2),('R',page.width/2,page.width)]:
                region=page.crop((x0,78,x1,810))
                for line in region.extract_text_lines(x_tolerance=1.5,y_tolerance=3):
                    lines.append((number,col,round(line['top'],2),round(line['bottom'],2),line['text']))
            page.close()
        pages=len(pdf.pages)
    return {'version':VERSION,'pages':pages,'layout_issues':quality,
            'text':'\n'.join(line[4] for line in lines),
            'turns':[t.metadata() for t in segment(lines)]}

def eligible(turn):
    return (turn['closed'] and not turn['rejection'] and turn['speaker_name']
            and turn['role'] not in {'의사국장'}
            and len(turn['text'])>=120 and bool(JAPAN.search(turn['text'])))

def classification(turn):
    if turn['rejection'] or not turn['closed']:return 'segmentation_needs_review'
    if turn['role']=='의사국장':return 'procedural_official_report'
    if len(turn['text'])<120:return 'short_or_procedural'
    if not JAPAN.search(turn['text']):return 'not_explicitly_japan_related'
    return 'japan_candidate_needs_review'

def floor_episodes(turns):
    """Conservative floor ownership; interruptions do not manufacture new events.

    Separate later floor appearances stay separate. Unknown standalone officials
    are never joined across turns without an identified MP's floor episode.
    """
    owner=None;episode=None;result={}
    for t in turns:
        if t['role'] in {'의원','위원'} and t['speaker_name']:
            if owner!=t['speaker_name']:
                owner=t['speaker_name'];episode=str(t['ordinal'])
        result[t['ordinal']]=episode or ('standalone-'+str(t['ordinal']))
    return result

def literal_quote_blocks(text):
    # Stage directions and anonymous interjections remain in the protocol context.
    # Keep contiguous source blocks; never concatenate around removed annotations.
    chunks=re.split(r'\((?:장내|영상자료|자료를|발언시간|마이크|｢)[\s\S]*?\)',text)
    return [part.strip() for part in chunks if len(part.strip())>=80]
