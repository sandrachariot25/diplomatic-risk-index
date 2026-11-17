"""Documented Open Assembly meeting catalogue, not an API of individual speeches.

Resources/fields verified against selectOpenApiMeta.do on 2026-11-01.
Only the explicitly permitted sample mode is implemented. No credentials logged.
"""
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode, urlsplit, parse_qs

BASE='https://open.assembly.go.kr/portal/openapi/'
DATASETS={
    'plenary': {'id':'OO1X9P001017YF13038','name':'본회의 회의록','method':'nzbyfwhwaoanttzje'},
    'committee': {'id':'OR137O001023MZ19321','name':'위원회 회의록','method':'ncwgseseafwbuheph'},
    'detail': {'id':'OOWY4R001216HX11520','name':'회의록별 상세정보','method':'VCONFDETAIL'},
}

class AssemblyResponseError(ValueError):
    pass

def specification_url(kind):
    return 'https://open.assembly.go.kr/portal/data/openapi/selectOpenApiMeta.do?'+urlencode(
        {'infId':DATASETS[kind]['id'],'infSeq':2})

def sample_url(kind, *, term=None, period=None, committee=None, conf_id=None, through=None):
    """No key, no sample pagination/limit evasion. All names come from the spec."""
    params={'Type':'json','pIndex':1,'pSize':5}
    if kind=='detail':
        if not isinstance(conf_id,str) or not conf_id or not conf_id.isalnum():
            raise ValueError('An opaque CONF_ID returned by the API is required')
        if any(v is not None for v in (term,period,committee)):
            raise ValueError('Detail accepts only CONF_ID')
        params['CONF_ID']=conf_id
    else:
        if kind not in {'plenary','committee'}:raise ValueError('Unverified API resource')
        if not isinstance(term,int) or not 19<=term<=22:raise ValueError('Expected research-period term 19..22')
        if not isinstance(period,str):raise ValueError('CONF_DATE required')
        if len(period)==4:
            if not period.isdigit():raise ValueError('Invalid year')
            year=int(period)
        elif len(period)==7:
            parsed=date.fromisoformat(period+'-01');year=parsed.year
        else:raise ValueError('Use a year or year-month, as verified by the service')
        if through is None:
            through=date(2026,10,31)
        if not 2015<=year<=through.year or (len(period)==7 and parsed>through):
            raise ValueError('Outside corpus period')
        params.update(DAE_NUM=term,CONF_DATE=period)
        if committee:
            if kind!='committee':raise ValueError('COMM_NAME is a committee-only filter')
            params['COMM_NAME']=committee
    return BASE+DATASETS[kind]['method']+'?'+urlencode(params)

def parse_response(payload,kind):
    """Return catalogue rows only. Never converts rows, agendas or names to quotes."""
    method=DATASETS[kind]['method']
    result=payload.get('RESULT')
    if result:
        if result.get('CODE')=='INFO-200':return [],0
        raise AssemblyResponseError(str(result.get('CODE'))+': '+str(result.get('MESSAGE')))
    blocks=payload.get(method)
    if not isinstance(blocks,list):raise AssemblyResponseError('Expected verified resource envelope')
    heads=[h for b in blocks for h in b.get('head',[])]
    statuses=[h['RESULT']['CODE'] for h in heads if 'RESULT' in h]
    if statuses!=['INFO-000']:raise AssemblyResponseError('Unexpected result status: '+str(statuses))
    counts=[h['list_total_count'] for h in heads if 'list_total_count' in h]
    if len(counts)!=1 or not isinstance(counts[0],int):raise AssemblyResponseError('Missing total count')
    rows=[r for b in blocks for r in b.get('row',[])]
    if len(rows)>5:raise AssemblyResponseError('Response exceeds permitted sample size')
    if counts[0]>0 and not rows:raise AssemblyResponseError('Nonempty total without sample rows')
    return rows,counts[0]

@dataclass(frozen=True)
class MeetingReference:
    conf_id:str
    record_number:str
    meeting_date:str
    organ:str
    title:str
    pdf_url:str
    agenda_titles:tuple[str,...]

def meeting_references(rows, *, through=date(2026,10,31)):
    """One meeting per authoritative CONF_ID; repeated agenda rows are metadata."""
    groups={}
    for row in rows:
        required=('CONF_ID','CONFER_NUM','CONF_DATE','TITLE','PDF_LINK_URL')
        if any(row.get(k) is None or row.get(k)=='' for k in required):
            raise ValueError('Incomplete meeting reference')
        d=date.fromisoformat(row['CONF_DATE'])
        if not date(2015,1,1)<=d<=through:continue
        p=urlsplit(row['PDF_LINK_URL'])
        if p.scheme!='https' or p.netloc!='record.assembly.go.kr' or p.path!='/assembly/viewer/minutes/download/pdf.do':
            raise ValueError('Unverified PDF origin/route; never follow arbitrary source links')
        if parse_qs(p.query)!={'id':[str(row['CONFER_NUM'])]} or p.fragment:
            raise ValueError('PDF record identifier differs from CONFER_NUM')
        key=str(row['CONF_ID'])
        signature=(str(row['CONFER_NUM']),row['CONF_DATE'],row.get('COMM_NAME') or row['CLASS_NAME'],row['TITLE'],row['PDF_LINK_URL'])
        if key in groups and groups[key][0]!=signature:raise ValueError('Conflicting metadata for same meeting')
        groups.setdefault(key,(signature,[]))[1].append(row.get('SUB_NAME') or '')
    return [MeetingReference(k,*sig,tuple(dict.fromkeys(agenda))) for k,(sig,agenda) in groups.items()]
