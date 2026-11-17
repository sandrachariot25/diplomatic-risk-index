"""Compare coverage without recalculating any frozen risk score."""
import json
import sys
from collections import Counter
from datetime import date,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.paths import DATA
from scripts.annotate_llm_pilot import data
from scripts.prediction_backtest import csv_rows,load_speeches,select_speeches,EXCLUDED_DIRECTIONS

def coverage():
    units,labels=data()
    extra=[json.loads(l) for l in (DATA/'kr_hearings_annotations.jsonl').read_text(encoding='utf-8').splitlines()]
    speeches,_=load_speeches((units,labels))
    windows=[]
    for row in csv_rows(DATA/'dri_prediction_snapshots.csv'):
        if row['mode']!='retrospective' or row['min_units']!='5' or row['assessment_date']>'2026-10-31':continue
        day=date.fromisoformat(row['assessment_date']);start=day-timedelta(days=89)
        old=Counter(units[s.unit_id]['country'] for s,_,_ in select_speeches(day,speeches,mode='retrospective') if s.direction not in EXCLUDED_DIRECTIONS)
        new=[r for r in extra if r.get('analysis_eligible',True) and start.isoformat()<=r['date']<=day.isoformat() and r['direction'] not in EXCLUDED_DIRECTIONS]
        after=old.copy();after['ROK']+=len(new)
        windows.append(dict(date=day.isoformat(),before=dict(old),after=dict(after),
                            added_unique_speakers=len({r['speaker'] for r in new}),
                            added_unique_meetings=len({r['meeting_id'] for r in new})))
    summary={}
    for stage in ('before','after'):
        counts=[r[stage] for r in windows]
        summary[stage]={'both_at_least_5':sum(c.get('ROK',0)>=5 and c.get('JPN',0)>=5 for c in counts),
                        'both_any':sum(c.get('ROK',0)>0 and c.get('JPN',0)>0 for c in counts),
                        'one_country_only':sum(bool(c.get('ROK',0))!=bool(c.get('JPN',0)) for c in counts),
                        'empty':sum(not any(c.values()) for c in counts)}
    annual=Counter((u['date'][:4],u['country'],u['institution_type']) for u in units.values())
    annual.update((r['date'][:4],'ROK',r['institution_type']) for r in extra)
    result=dict(window_mode='retrospective_speech_date_proxies',windows_total=len(windows),summary=summary,
                previous_balance=dict(Counter(u['country'] for u in units.values())),
                new_balance=dict(Counter(u['country'] for u in units.values())+Counter(r['country'] for r in extra)),
                expansion_eligible=sum(r.get('analysis_eligible',True) for r in extra),
                expansion_context_only=sum(not r.get('analysis_eligible',True) for r in extra),
                years=dict(Counter(r['date'][:4] for r in extra)),
                annual=[dict(year=y,country=c,institution=i,units=n) for (y,c,i),n in sorted(annual.items())],
                windows=windows)
    (DATA/'kr_hearings_coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    r=coverage();print(json.dumps({k:v for k,v in r.items() if k not in {'annual','windows'}},ensure_ascii=False))
