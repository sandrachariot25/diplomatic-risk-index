"""Frozen-label, descriptive calendar-window experiment; no classification or fitting."""
import csv
import hashlib
import json
import os
from pathlib import Path
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.annotate_llm_pilot import data

EVENTS = [
    ('2015_agreement', ['2015-12-28'], -1, 'Comfort women agreement',
     ['https://2009-2017.state.gov/secretary/remarks/2015/12/250874.htm']),
    ('2016_gsomia', ['2016-11-23'], -1, 'GSOMIA signing',
     ['https://www.defense.gov/News/Releases/Release/Article/1012704/statement-by-secretary-of-defense-ash-carter-on-signing-of-the-japan-rok-genera/']),
    ('2018_judgment', ['2018-10-30'], 1, 'Forced labor judgment',
     ['https://www.scourt.go.kr/eng/supreme/decisions/NewDecisionsView.work?mode=6&pageIndex=1&searchWord=&seq=400']),
    ('2019_exports', ['2019-07-01'], 1, 'Export controls announcement',
     ['https://www.meti.go.jp/policy/external_economy/export_control_korea/index-en.html']),
    ('2019_gsomia', ['2019-08-22'], 1, 'GSOMIA termination announced',
     ['https://www.korea.kr/briefing/presidentView.do?newsId=148863963']),
    ('2023_rapprochement', ['2023-03-06', '2023-03-16'], -1, 'Compensation plan and summit',
     ['https://www.mofa.go.kr/us-ko/brd/m_4487/view.do?seq=1347533',
      'https://japan.kantei.go.jp/101_kishida/diplomatic/202303/_00009.html']),
]


def sha(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


def main():
    frozen = {str(p.relative_to(ROOT)): sha(p.relative_to(ROOT)) for p in
              [ROOT/'data/dri.sqlite3', *ROOT.glob('data/dri_llm_*'),
               *ROOT.glob('data/dri_v01*'), *ROOT.glob('data/dri_v02*'), *ROOT.glob('data/dri_expert*')] if p.is_file()}
    units, annotations = data()
    assert len(units) == len(annotations) == 1017
    monthly = list(csv.DictReader((ROOT/'data/dri_llm_monthly.csv').open(encoding='utf-8-sig', newline='')))
    assert len(monthly) == 144
    months = {r['month']: r for r in monthly if r['month'] <= '2026-10'}
    keys = list(months)
    event_windows = {e[0]: keys[keys.index(e[1][0][:7])-3:keys.index(e[1][0][:7])+4] for e in EVENTS}
    union = set().union(*map(set, event_windows.values()))
    controls = [m for m in keys if m not in union]
    eligible = lambda m: int(months[m]['scored_units']) >= 5
    val = lambda m: float(months[m]['mean_confrontation_intensity'])
    control_good = [m for m in controls if eligible(m)]
    baseline = mean(val(m) for m in control_good)
    results = []
    for episode, dates, direction, title, urls in EVENTS:
        window = event_windows[episode]
        pre = window[:3]
        pre_ok = all(eligible(m) for m in pre)
        pre_mean = mean(val(m) for m in pre) if pre_ok else None
        for phase, selected in [('before', pre), ('event', window[3:4]), ('after', window[4:])]:
            good = [m for m in selected if eligible(m)]
            complete = len(good) == len(selected)
            observed = [m for m in selected if months[m]['mean_confrontation_intensity']]
            phase_mean = mean(val(m) for m in selected) if complete else None
            ref = baseline if phase == 'before' else pre_mean
            delta = phase_mean-ref if phase_mean is not None and ref is not None else None
            row = dict(kind='episode_phase', episode=episode, dates=';'.join(dates), title=title,
                       expected_direction='increase' if direction == 1 else 'decrease', phase=phase,
                       months=';'.join(selected), source_urls=';'.join(urls),
                       overlapping_episodes=';'.join(k for k,v in event_windows.items() if k != episode and set(selected)&set(v)),
                       annotated_units=sum(int(months[m]['annotated_units']) for m in selected),
                       scored_units=sum(int(months[m]['scored_units']) for m in selected),
                       missing_month_share=1-len(observed)/len(selected),
                       low_volume_months=';'.join(m for m in selected if 0<int(months[m]['scored_units'])<5),
                       adequate_months=len(good), calendar_months=len(selected),
                       partial_observed_mean=mean(val(m) for m in observed) if observed else None,
                       dri=phase_mean, reference=ref, delta=delta,
                       comparison='оценить невозможно' if delta is None else 'соответствует направлению' if direction*delta>0 else 'противоположное направление' if direction*delta<0 else 'без изменения')
            for c in ['ROK', 'JPN']:
                cr = [json.loads(months[m]['country_results'])[c] for m in selected]
                row[c+'_annotated'] = sum(x['annotated'] for x in cr)
                row[c+'_scored'] = sum(x['scored_units'] for x in cr)
                row[c+'_missing_month_share'] = sum(x['scored_units']==0 for x in cr)/len(cr)
            results.append(row)
        for m in window:
            offset=keys.index(m)-keys.index(dates[0][:7])
            i=keys.index(m); previous=keys[i-1] if i else None
            d=val(m)-val(previous) if previous is not None and eligible(m) and eligible(previous) else None
            row=dict(results[-1])
            row.update(kind='episode_month',phase='before' if offset<0 else 'event' if offset==0 else 'after',
                       months=m,annotated_units=int(months[m]['annotated_units']),scored_units=int(months[m]['scored_units']),
                       missing_month_share=int(not months[m]['mean_confrontation_intensity']),
                       low_volume_months=m if 0<int(months[m]['scored_units'])<5 else '',
                       adequate_months=int(eligible(m)),calendar_months=1,
                       partial_observed_mean=float(months[m]['mean_confrontation_intensity']) if months[m]['mean_confrontation_intensity'] else None,
                       dri=val(m) if eligible(m) else None,reference=val(previous) if d is not None else None,delta=d,
                       comparison='оценить невозможно' if d is None else 'соответствует направлению' if direction*d>0 else 'противоположное направление' if direction*d<0 else 'без изменения',
                       overlapping_episodes=';'.join(k for k,v in event_windows.items() if k!=episode and m in v))
            for c in ['ROK','JPN']:
                cr=json.loads(months[m]['country_results'])[c]
                row[c+'_annotated']=cr['annotated'];row[c+'_scored']=cr['scored_units'];row[c+'_missing_month_share']=int(cr['scored_units']==0)
            results.append(row)
    # Every control month, and only consecutive calendar pairs wholly outside all windows.
    for m in controls:
        i = keys.index(m)
        previous = keys[i-1] if i else None
        d = val(m)-val(previous) if previous in controls and eligible(m) and eligible(previous) else None
        row = dict(kind='control_month', episode='', dates='', title='', expected_direction='', phase='control',
                   months=m, source_urls='', overlapping_episodes='', annotated_units=int(months[m]['annotated_units']),
                   scored_units=int(months[m]['scored_units']), missing_month_share=int(not months[m]['mean_confrontation_intensity']),
                   low_volume_months=m if 0<int(months[m]['scored_units'])<5 else '', adequate_months=int(eligible(m)),
                   calendar_months=1, partial_observed_mean=float(months[m]['mean_confrontation_intensity']) if months[m]['mean_confrontation_intensity'] else None,
                   dri=val(m) if eligible(m) else None, reference=val(previous) if d is not None else None, delta=d,
                   comparison='оценить невозможно' if d is None else 'рост' if d>0 else 'снижение' if d<0 else 'без изменения')
        for c in ['ROK','JPN']:
            cr=json.loads(months[m]['country_results'])[c]
            row[c+'_annotated']=cr['annotated'];row[c+'_scored']=cr['scored_units'];row[c+'_missing_month_share']=int(cr['scored_units']==0)
        results.append(row)
    target=ROOT/'data/dri_historical_check.csv'
    with target.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    os.environ['MPLCONFIGDIR']=str(ROOT/'.venv/matplotlib-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,(ax,bx)=plt.subplots(2,1,figsize=(15,8),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    values=[float(months[m]['mean_confrontation_intensity']) if months[m]['mean_confrontation_intensity'] else float('nan') for m in keys]
    ax.plot(range(len(keys)),values,color='#334155',lw=.8,marker='.',label='Existing pooled DRI (unvalidated)')
    low=[i for i,m in enumerate(keys) if 0<int(months[m]['scored_units'])<5]
    ax.scatter(low,[values[i] for i in low],facecolors='white',edgecolors='#dc2626',s=40,label='1–4 scored units: insufficient')
    for n,(episode,dates,sign,title,urls) in enumerate(EVENTS):
        i=keys.index(dates[0][:7]);color='#b91c1c' if sign>0 else '#047857'
        ax.axvspan(i-3-.45,i+3+.45,color=color,alpha=.045)
        ax.axvline(i,color=color,ls='--',lw=.8)
        ax.text(i,3.12+(n%2)*.25,dates[0][:7],rotation=35,fontsize=8,color=color)
    ax.set_ylim(-.1,3.8);ax.set_yticks([0,1,2,3]);ax.set_ylabel('Mean intensity (0–3)');ax.legend(loc='upper right',fontsize=8)
    rok=[json.loads(months[m]['country_results'])['ROK']['scored_units'] for m in keys]
    jpn=[json.loads(months[m]['country_results'])['JPN']['scored_units'] for m in keys]
    bx.bar(range(len(keys)),rok,color='#d97706',label='ROK scored')
    bx.bar(range(len(keys)),jpn,bottom=rok,color='#2563eb',label='JPN scored')
    bx.set_ylabel('Scored units');bx.legend();bx.set_xticks(range(0,len(keys),12),range(2015,2027))
    ax.set_title('First historical experiment — fixed labels and formula; calendar windows ±3 months')
    fig.text(.04,.02,'Missing ≠ zero. Monthly event bins cannot establish within-month precedence. Overlapping 2019 episodes are dependent.',fontsize=9)
    fig.tight_layout(rect=[0,.04,1,1]);fig.savefig(ROOT/'docs/DRI_historical_check.png',dpi=150);plt.close(fig)
    assert all(sha(p)==h for p,h in frozen.items()), 'Protected inputs changed'
    manifest=dict(formula='Monthly arithmetic mean of intensity among confrontational/cooperative/mixed/neutral; other categories excluded; no weights',
                  frozen_sha256=frozen, events=[dict(episode=e[0],dates=e[1],expected_direction=e[2],title=e[3],sources=e[4]) for e in EVENTS],
                  protocol='Calendar ±3 months. Equal-month phase means of the unchanged monthly DRI, not a new index. All months must have >=5 scored units. Pre vs all adequate control months; event/post vs pre. Only sign, no tuned effect threshold. Descriptive, not preregistered or predictive validation.',
                  control_months=controls, adequate_control_months=control_good,control_month_mean=baseline,
                  results_sha256={str(p):sha(p) for p in ['data/dri_historical_check.csv','docs/DRI_historical_check.png']})
    (ROOT/'data/dri_historical_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(control_months=len(controls),adequate_controls=len(control_good),baseline=baseline,
                         phases=[{k:r[k] for k in ['episode','phase','adequate_months','dri','delta','comparison']} for r in results if r['kind']=='episode_phase'],
                         control_changes={k:sum(r['comparison']==k for r in results if r['kind']=='control_month') for k in ['рост','снижение','без изменения','оценить невозможно']}),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
