"""Read-only case comparison; thematic evidence never changes semantic labels or DRI."""
import json
import re
import sqlite3
from collections import Counter
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dri.paths import DATA, write_generated
from scripts.annotate_llm_pilot import data, DB
from scripts.bilateral_dri import load_corpora, calculate, institution_group
from scripts.live_dri import review_rows

VERSION = 'DRI-case-topics-1'
TOPICS = {
    'historical_memory': ('историческая память', r'佐渡|사도광산|Sado|徴用|강제동원|강제징용|forced labo[u]?r|慰安婦|위안부|comfort women|靖国|야스쿠니|Yasukuni|歴史認識|역사인식|過去の歴史|과거사|植民|colonial|조세이|長生炭鉱'),
    'trade_economy': ('торгово-экономические отношения', r'貿易|輸出|輸入|経済|通商|サプライチェーン|무역|수출|수입|경제|통상|공급망|trade|export|import|economic|supply chain'),
    'security': ('безопасность', r'安全保障|防衛|軍事|ミサイル|非核|国連軍|地位協定|安保|안보|국방|군사|미사일|비핵|security|defen[cs]e|missile|denuclear|GSOMIA'),
    'diplomatic_cooperation': ('дипломатическое сотрудничество', r'協力|連携|交流|対話|首脳会談|関係改善|협력|공조|교류|대화|정상회담|관계개선|cooperat|dialogue|summit|partnership|exchange'),
    'other_bilateral': ('другие двусторонние вопросы', r'竹島|독도|Dokdo|Takeshima|領土|territor|領有|영유|漁業|어업|fisher'),
}
CASES = [
    dict(id='2019', title='2019 · экспортные ограничения', start='2019-04-02', end='2019-09-29',
         events=[dict(date='2019-07-01', name='Объявление экспортных ограничений',
                      source='https://www.meti.go.jp/policy/external_economy/export_control_korea/index-en.html', status='confirmed_primary')]),
    dict(id='2023', title='2023 · нормализация отношений', start='2022-12-06', end='2023-06-14',
         events=[dict(date='2023-03-06', name='План урегулирования', source='https://www.mofa.go.kr/us-ko/brd/m_4487/view.do?seq=1347533', status='confirmed_primary'),
                 dict(date='2023-03-16', name='Саммит в Токио', source='https://japan.kantei.go.jp/101_kishida/diplomatic/202303/_00009.html', status='confirmed_primary')]),
    dict(id='2026', title='2026 · сотрудничество и Садо', start='2025-10-15', end='2026-11-09',
         events=[dict(date='2026-01-13', name='Саммит в Наре', source='https://www.kantei.go.jp/jp/104/actions/202601/13korea.html', status='confirmed_primary'),
                 dict(date='2026-09-09', first_report='2026-09-08', name='Публичное сообщение об отказе от церемонии Садо',
                      source='https://www.ytn.co.kr/_ln/0101_202609091448425895',
                      earlier_source='https://nwww.newsis.com/view/NISX20260908_0003781575', status='reported_official_position_not_primary')]),
]


def topical_evidence(text):
    """Auditable lexical thematic tagging, not contextual direction classification."""
    found = {}
    for key, (_, pattern) in TOPICS.items():
        matches = list(re.finditer(pattern, text, re.I))
        if matches:
            found[key] = [dict(start=m.start(), end=m.end(), term=m.group()) for m in matches[:5]]
    return found


def source_units(allowed_live_ids=None):
    units, labels = data()
    rows = []
    for label in labels:
        unit = units[label['unit_id']]
        rows.append(dict(id=unit['unit_id'], date=unit['date'], country=unit['country'],
                         institution=institution_group(unit['institution_type']), speaker=unit['speaker_name'],
                         text='\n'.join(f['text'] for f in unit['fragments']), urls=unit['source_urls'],
                         direction=label['direction'], intensity=label['confrontation_intensity'],
                         cooperation=label['cooperation_present'], summary=label['summary_ru']))
    with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro', uri=True) as db:
        for line in (DATA/'kr_hearings_annotations.jsonl').read_text(encoding='utf-8').splitlines():
            label = json.loads(line)
            if not label['analysis_eligible']:
                continue
            text, = db.execute('SELECT text FROM documents WHERE id=?', (label['document_ids'][0],)).fetchone()
            if sha256(text.encode()).hexdigest() != label['input_text_sha256']:
                raise ValueError('Expansion text changed')
            rows.append(dict(id=label['unit_id'], date=label['date'], country=label['country'],
                             institution=institution_group(label['institution_type']), speaker=label['speaker'],
                             text=text, urls=[label['source_url']], direction=label['direction'],
                             intensity=label['confrontation_intensity'], cooperation=label['cooperation_present'],
                             summary=label['summary_ru']))
        for row in review_rows(db):
            if allowed_live_ids is not None and row['id'] not in allowed_live_ids:
                continue
            label = row['annotation']
            if label:
                rows.append(dict(id=row['id'], date=row['spoken_date'], country=row['country'],
                                 institution=row['institution'], speaker=row['speaker'], text=row['text'],
                                 urls=[row['url']], direction=label['direction'], intensity=label['confrontation_intensity'],
                                 cooperation=label['cooperation_present'], summary=label['summary_ru']))
    if len({str(r['id']) for r in rows}) != len(rows):
        raise ValueError('Duplicate analytic identity')
    return rows


def aggregate(rows):
    eligible = [r for r in rows if r['direction'] not in {'irrelevant', 'uncertain'}]
    n = len(eligible)
    return dict(n=n, all_units=len(rows), excluded=len(rows)-n,
                speakers=len({r['speaker'].strip().casefold() for r in eligible if r['speaker']}),
                unknown_speakers=sum(not r['speaker'] for r in eligible),
                directions=dict(Counter(r['direction'] for r in eligible)),
                confrontation_share=sum(r['direction'] in {'confrontational','mixed'} for r in eligible)/n if n else None,
                cooperation_share=sum(r['cooperation'] for r in eligible)/n if n else None,
                mean_intensity=sum(r['intensity'] for r in eligible)/n if n else None,
                coverage='empty' if not n else 'low' if n<5 else 'observed',
                topics=dict(Counter(t for r in eligible for t in r['topics'])),
                topic_cooperation=dict(Counter(t for r in eligible if r['cooperation'] for t in r['topics'])),
                topic_conflicts=dict(Counter(t for r in eligible if r['direction'] in {'confrontational','mixed'} for t in r['topics'])))


def periods(event, end):
    day = date.fromisoformat(event['date'])
    early = date.fromisoformat(event.get('first_report', event['date']))
    return [('before', early-timedelta(days=90), early-timedelta(days=1)),
            ('event', early, day), ('after', day+timedelta(days=1), min(day+timedelta(days=90), date.fromisoformat(end)))]


def build():
    context_path = DATA/'dri_research_context.json'
    context = json.loads(context_path.read_text(encoding='utf-8')) if context_path.exists() else None
    raw = source_units(set(context['reviewed_ids']) if context else None)
    rows = []
    for row in raw:
        if not any(c['start']<=row['date']<=c['end'] for c in CASES):
            continue
        text = row.pop('text')
        evidence = topical_evidence(text)
        rows.append(dict(row, text_sha256=sha256(text.encode()).hexdigest(), topics=list(evidence),
                         topic_evidence=evidence, thematic_status='lexical_evidence_not_expert_validated',
                         unassigned_topic=not bool(evidence)))
    original, expanded = load_corpora()
    results = []
    for case in CASES:
        selected = [r for r in rows if case['start']<=r['date']<=case['end']]
        monthly = []
        cursor = date.fromisoformat(case['start']).replace(day=1)
        while cursor.isoformat() <= case['end']:
            month = cursor.strftime('%Y-%m')
            for country in ('ROK','JPN'):
                for institution in ('government','parliament','other'):
                    group = [r for r in selected if r['date'].startswith(month) and r['country']==country and r['institution']==institution]
                    monthly.append(dict(month=month,country=country,institution=institution,**aggregate(group)))
            cursor = (cursor.replace(day=28)+timedelta(days=4)).replace(day=1)
        windows = []
        scores = []
        for event in case['events']:
            for phase, start, end in periods(event, case['end']):
                for country in ('ROK','JPN'):
                    for institution in ('government','parliament','other'):
                        group = [r for r in selected if start.isoformat()<=r['date']<=end.isoformat() and r['country']==country and r['institution']==institution]
                        windows.append(dict(event=event['date'],phase=phase,start=start.isoformat(),end=end.isoformat(),
                                            country=country,institution=institution,**aggregate(group)))
            # Pre-event cutoff excludes the first public report, not only the requested marker.
            day = date.fromisoformat(event.get('first_report',event['date']))-timedelta(days=1)
            for mode in ('strict','retrospective'):
                scores.append(dict(event=event['date'], **calculate(day,mode,original,expanded)))
        results.append(dict(**case, monthly=monthly, windows=windows, pre_event_dri=scores,
                            unit_ids=[r['id'] for r in selected], summary=aggregate(selected)))
    protected = ['dri_llm_annotations.jsonl','kr_hearings_annotations.jsonl','dri_event_truth.csv',
                 'dri_event_calendar.csv','dri_backtest.csv','dri_prediction_snapshots.csv']
    result = dict(version=VERSION, as_of='2026-11-09',
                  collection_cutoff=context['collection_cutoff'] if context else None,
                  source_hashes={name:sha256((DATA/name).read_bytes()).hexdigest() for name in protected},
                  method='Fixed event windows; original semantic labels; lexical multi-topic evidence; no new index.',
                  warnings=['Counts are units, not independent speakers.', 'Unknown institutions remain other.',
                            'Topics concern the whole unit: no claim that every topic has its own directional label.',
                            'March 2023 windows overlap: one normalization episode, not independent successes.',
                            '2026 after-Sado window is right-censored at 9 November.',
                            'Source texts with no lexical evidence remain unassigned; no forced other category.'],
                  topics={k:v[0] for k,v in TOPICS.items()}, units=rows, cases=results)
    write_generated(DATA/'dri_research_cases.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    result=build()
    print(json.dumps({c['id']:c['summary'] for c in result['cases']},ensure_ascii=False))
