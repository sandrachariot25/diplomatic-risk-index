"""Descriptive institutional metadata; no hierarchy, significance weights or sentiment inference."""
import json
from .identity import fingerprint

def institutional_metadata(record, source_ids):
    role=record.get('speaker_office')
    result=dict(institution_type='unknown',venue_institution_type=None,speaker_role=role,
                speaker_category='unknown',political_affiliation=None,government_opposition_status=None,
                political_status_date=None,statement_context='unknown',position_scope='unclear')
    evidence={'basis':'retained source identity, stated role and context only',
              'source_ids':sorted(source_ids),'observed_role':role,
              'party_status':'not established; no name-to-party or present-to-past inference',
              'significance_weights':'not assigned'}
    if 'mofa_kr' in source_ids or 'mofa_jp' in source_ids:
        result.update(institution_type='foreign_ministry',statement_context='official_statement',
                      position_scope='institutional_position')
        if 'spokes' in (role or '').casefold():result['speaker_category']='institutional_spokesperson'
        elif 'minister' in (role or '').casefold():result['speaker_category']='cabinet_member'
    if 'assembly_kr' in source_ids:
        result.update(venue_institution_type='parliament',statement_context='parliamentary_debate')
        if role in {'위원','의원'}:
            result.update(institution_type='parliament',speaker_category='legislator',position_scope='individual_position')
        elif '외교부' in (role or ''):
            result.update(institution_type='foreign_ministry',speaker_category='cabinet_member',position_scope='official_state_position')
    if 'kokkai_jp' in source_ids:
        result.update(venue_institution_type='parliament',statement_context='parliamentary_debate')
        text=role or ''
        # The venue is not the actor's institution. Cabinet Secretariat is not a party.
        if '外務' in text:
            result['institution_type']='foreign_ministry'
        elif any(t in text for t in ('内閣','省','大臣','副大臣')):
            result['institution_type']='government'
        elif any(t in text for t in ('議員','委員長')):
            result['institution_type']='parliament'
        if '委員長' in text:
            result.update(speaker_category='committee_chair',position_scope='unclear')
        elif '議員' in text:
            result.update(speaker_category='legislator',position_scope='individual_position')
        elif '内閣総理大臣' in text:
            result.update(speaker_category='head_of_government',position_scope='official_state_position')
        elif '官房' in text or '参事官' in text or '審議官' in text:
            result.update(speaker_category='executive_official',position_scope='official_state_position')
        elif any(t in text for t in ('大臣','副大臣')):
            result.update(speaker_category='cabinet_member' if '副大臣' not in text else 'executive_official',position_scope='official_state_position')
        evidence['selection_bias']='Legacy collection used substring speakerPosition=大臣; this includes ministerial-secretariat officials and excludes most ordinary MPs.'
    result['evidence_json']=json.dumps(evidence,ensure_ascii=False,sort_keys=True)
    return result

def insert_metadata(db, sid, values, timestamp):
    columns=('institution_type','venue_institution_type','speaker_role','speaker_category','political_affiliation',
             'government_opposition_status','political_status_date','statement_context','position_scope','evidence_json')
    db.execute('INSERT INTO statement_metadata(statement_id,'+','.join(columns)+',updated_at) VALUES('+','.join('?' for _ in range(len(columns)+2))+') ON CONFLICT(statement_id) DO NOTHING',
               (sid,*(values.get(c) for c in columns),timestamp))

def records(db):
    cursor=db.execute('SELECT * FROM statements ORDER BY id')
    cols=[c[0] for c in cursor.description]
    result=[]
    for row in cursor.fetchall():
        record=dict(zip(cols,row))
        record['quotes']=[dict(id=q[0],text=q[1],language=q[2],version_kind=q[3]) for q in db.execute(
            'SELECT id,text,published_language,version_kind FROM quotes WHERE statement_id=? ORDER BY id',(record['id'],))]
        record['sources']=[dict(document_id=d[0],source_id=d[1],source_type=d[2],url=d[3],title=d[4]) for d in db.execute(
            '''SELECT d.id,d.source,d.source_type,d.url,json_extract(d.metadata_json,'$.title') FROM statement_sources ss
             JOIN documents d ON d.id=ss.document_id WHERE ss.statement_id=? ORDER BY d.id''',(record['id'],))]
        record['year']=(record['spoken_date'] or record['published_date'])[:4]
        record['metadata']=institutional_metadata(record,{s['source_id'] for s in record['sources']})
        result.append(record)
    return result

def stratified_sample(rows, size=50):
    """Reproducible country/year anchors, then balanced country and rare strata coverage."""
    if len(rows)<size:raise ValueError('Corpus smaller than requested audit sample')
    ranked=sorted(rows,key=lambda r:fingerprint('DRI-stratified-50-v1',r['event_key'],r['id']))
    selected=[]
    groups=sorted({(r['year'],r['country']) for r in ranked})
    if len(groups)>size:raise ValueError('Sample cannot cover all country/year strata')
    for year,country in groups:
        selected.append(next(r for r in ranked if (r['year'],r['country'])==(year,country)))
    def tags(r):
        m=r['metadata']
        return {('theme',r['theme']),('institution',m['institution_type']),('role',m['speaker_category']),
                ('venue',m['venue_institution_type']),('source_type',tuple(sorted({s['source_type'] for s in r['sources']})))}
    while len(selected)<size:
        used={r['id'] for r in selected}
        counts={c:sum(r['country']==c for r in selected) for c in ('ROK','JPN')}
        eligible=[r for r in ranked if r['id'] not in used and counts[r['country']]<size//2]
        if not eligible:eligible=[r for r in ranked if r['id'] not in used]
        def priority(r):
            rarity=sum(1/(1+sum(tag in tags(old) for old in selected)) for tag in tags(r))
            year_count=sum(old['year']==r['year'] for old in selected)
            return (counts[r['country']],-rarity,year_count,fingerprint('DRI-stratified-50-v1',r['event_key'],r['id']))
        selected.append(min(eligible,key=priority))
    return sorted(selected,key=lambda r:(r['spoken_date'] or r['published_date'],r['country'],r['id']))
