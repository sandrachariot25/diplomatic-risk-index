"""Public build of the DRI site: data/dri_v2_monitor.json + site/content.json -> site/index.html.

    python scripts/export_public_v2.py

Only public material goes out: index and layer deviations, calendar triggers, court docket, verified diplomatic
actions (our one-line descriptions with primary sources), episodes in hand-written public wording, and for
parliamentary statements only date, country, speaker, role, severity and a link to the official record.
Internal annotation texts (summaries, quotes, expert notes) are NOT exported.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA, SITE = ROOT / 'data', ROOT / 'site'
RISK = {'повышен': 'high', 'внимание': 'watch', 'обычный': 'normal'}
COURT_GROUPS = {'все решения': ('Все решения', 'All rulings'), 'Верховный суд': ('Верховный суд', 'Supreme Court'),
                'с протестом Японии': ('С протестом Японии', 'Japan protested'),
                'без протеста Японии': ('Без протеста Японии', 'No Japanese protest'),
                'неблагоприятные (отказ, отклонение)': ('Отказы истцам', 'Rulings against plaintiffs')}


def trigger_en(text, kind, c):
    if text in c['recurring']:
        return c['recurring'][text]
    if ':' in text and '—' in text:
        court, rest = text.split(':', 1)
        dfn, dec = [s.strip() for s in rest.split('—', 1)]
        return f"{c['courts'].get(court.strip(), court)}: {c['defendants'].get(dfn, dfn)} — {c['decisions'].get(dec, dec)}"
    sys.exit(f'no English for trigger: {text}')


def month_add(m, k):
    y, mm = map(int, m.split('-'))
    y, mm = divmod(y * 12 + mm - 1 + k, 12)
    return f'{y:04d}-{mm + 1:02d}'


def load_stats(c, month_list):
    """Monthly series for the researcher view, indexed by the month the data describe (publication lags undone)."""
    import csv
    def read(name):
        return list(csv.DictReader((DATA / name).open(encoding='utf-8-sig')))
    tables = {'gdelt': {r['month']: r for r in read('gdelt_kor_jpn_monthly.csv')},
              'parl': {r['month']: r for r in read('dri_v2_monthly.csv')},
              'econ': {r['data_month']: r for r in read('dri_v2_econ_monthly.csv') if r.get('data_month')},
              'riv': {r['data_month']: r for r in read('dri_v2_rivalry_monthly.csv') if r.get('data_month')},
              'm2': {r['month']: r for r in read('dri_v2_material2_monthly.csv')},
              'appr': {r['month']: r for r in read('approval_monthly.csv')}}
    acts = {}
    for r in read('dri_event_truth.csv'):
        a = acts.setdefault(r['event_date'][:7], {'esc': 0, 'coop': 0})
        if r['direction'] == 'escalation':
            a['esc'] += 1
        elif r['direction'] == 'cooperation':
            a['coop'] += 1
    tables['acts'] = {m: {'esc': acts.get(m, {}).get('esc', 0), 'coop': acts.get(m, {}).get('coop', 0)} for m in month_list}
    out = []
    for s in c['stats']:
        tab, lag = tables[s['file']], s.get('lag', 0)
        vals = []
        for m in month_list:
            row = tab.get(month_add(m, lag)) if s['file'] == 'm2' else tab.get(m)
            v = row.get(s['col']) if row else None
            vals.append(None if v in (None, '', 'nan') else round(float(v), 5))
        if all(v is None for v in vals):
            sys.exit(f"stat {s['id']}: no data")
        item = dict(id=s['id'], unit=s['unit'], group=s['group'], src=s['src'], layer=s.get('layer'),
                    ru=s['ru'], en=s['en'], v=vals)
        if s.get('ncol'):  # sample size behind a share: shown as "x of n statements"
            item['n'] = [int(float(tab[m][s['ncol']])) if m in tab and tab[m].get(s['ncol']) not in (None, '') else None
                         for m in month_list]
        out.append(item)
    return out


SECTOR_EN = {'C26': 'Electronics, optics and computers', 'C20': 'Chemicals', 'C28': 'Machinery and equipment',
             'C29': 'Motor vehicles and parts', 'C27': 'Electrical equipment incl. batteries', 'C24FER': 'Iron and steel',
             'C24': 'Basic metals', 'C301': 'Ships and boats', 'B06': 'Crude oil and natural gas',
             'C19': 'Coke and refined petroleum'}
GOODS_EN = {'271111': 'Liquefied natural gas', '280920': 'Phosphoric and polyphosphoric acids',
            '720839': 'Hot-rolled coil under 3 mm', '848620': 'Semiconductor manufacturing equipment',
            '850760': 'Lithium-ion batteries', '854231': 'Processors and controllers', '854232': 'Memory chips',
            '870899': 'Other motor-vehicle parts', '890120': 'Tankers'}


def load_economy():
    """Korea-Japan trade from the first-version economic screen: monthly flows, industries, critical goods."""
    import csv
    sys.path.insert(0, str(ROOT))
    from scripts.economic_trade import SECTORS, SOURCES
    rd = lambda n: list(csv.DictReader((DATA / n).open(encoding='utf-8')))
    num = lambda v, k=1e9, d=3: round(float(v) / k, d) if v not in (None, '') else None
    monthly = {}
    for r in rd('trade_monthly.csv'):
        monthly.setdefault(r['period'], {})[r['reporter']] = r
    periods = sorted(monthly)
    trade = dict(periods=periods, sources=SOURCES)
    for rep in ('KOR', 'JPN'):
        rows = [monthly[p].get(rep) for p in periods]
        trade[rep] = {f: [num(r[f]) if r else None for r in rows] for f in ('exports_usd', 'imports_usd', 'balance_usd')}
        trade[rep]['import_share'] = [num(r['import_share'], 1, 5) if r else None for r in rows]
        trade[rep]['export_share'] = [num(r['export_share'], 1, 5) if r else None for r in rows]
        trade[rep]['source'] = [r['source'] if r else None for r in rows]
    sectors = []
    struct = [r for r in rd('trade_structure.csv') if r['flow'] == 'M']
    for code, ru in SECTORS.items():
        for rep in ('KOR', 'JPN'):
            rows = sorted((r for r in struct if r['commodity'] == 'CPA_2_1_' + code and r['reporter'] == rep),
                          key=lambda r: r['period'])
            if rows:
                sectors.append(dict(code=code, ru=ru, en=SECTOR_EN[code], rep=rep, years=[r['period'] for r in rows],
                                    usd=[num(r['bilateral_usd']) for r in rows],
                                    share=[num(r['partner_share'], 1, 4) for r in rows]))
    goods = {}
    for r in rd('trade_dependency.csv'):
        if r['source'] == 'un_comtrade' and r['frequency'] == 'M':
            g = goods.setdefault(r['commodity'], dict(code=r['commodity'], ru=r['label'], en=GOODS_EN.get(r['commodity'], r['label']), KOR={}, JPN={}))
            g[r['reporter']][r['period']] = [num(r['partner_share'], 1, 4), num(r['bilateral_usd'], 1e6, 1),
                                             num(r['world_usd'], 1e6, 1)]
    gp = sorted({p for g in goods.values() for rep in ('KOR', 'JPN') for p in g[rep]})

    def series(cells):
        """[monthly share, bilateral US$ m, 12-month share]; the 12-month share = sum of imports from the partner /
        sum of all imports over the trailing year (needs >= 6 reported months) - steadier for lumpy goods like ships."""
        out = []
        for i, (sh, bil, world) in enumerate(cells):
            win = [c for c in cells[max(0, i - 11): i + 1] if c[2]]
            s12 = round(sum(c[1] or 0 for c in win) / sum(c[2] for c in win), 4) if len(win) >= 6 and sum(c[2] for c in win) else None
            out.append([sh, bil, s12])
        return out
    goods_out = [dict(code=g['code'], ru=g['ru'], en=g['en'],
                      **{rep: series([g[rep].get(p, [None, None, None]) for p in gp]) for rep in ('KOR', 'JPN')})
                 for g in goods.values()]
    return dict(trade=trade, sectors=sectors, goods=dict(periods=gp, items=goods_out))


def write_csvs(out):
    """Open data files next to the page (site/data/*.csv)."""
    import csv
    d = SITE / 'data'
    d.mkdir(exist_ok=True)
    ms = [m['m'] for m in out['months']]
    with (d / 'dri_monthly.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['month', 'tension_index', 'risk_3m', 'gdelt_conflict_share'] + [s['id'] for s in out['stats']])
        for i, m in enumerate(out['months']):
            w.writerow([m['m'], m['idx'], m['risk'], m['g']] + [s['v'][i] if s['v'][i] is not None else '' for s in out['stats']])
    t = out['economy']['trade']
    with (d / 'trade_monthly.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['month', 'kor_exports_to_jpn_bn_usd', 'kor_imports_from_jpn_bn_usd', 'kor_balance_bn_usd',
                    'jpn_share_in_kor_imports', 'jpn_exports_to_kor_bn_usd', 'jpn_imports_from_kor_bn_usd',
                    'kor_share_in_jpn_imports'])
        for i, p in enumerate(t['periods']):
            w.writerow([p, t['KOR']['exports_usd'][i], t['KOR']['imports_usd'][i], t['KOR']['balance_usd'][i],
                        t['KOR']['import_share'][i], t['JPN']['exports_usd'][i], t['JPN']['imports_usd'][i],
                        t['JPN']['import_share'][i]])
    with (d / 'trade_industries.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['industry_cpa21', 'industry', 'importer', 'year', 'imports_from_partner_bn_usd', 'partner_share'])
        for s in out['economy']['sectors']:
            for y, u, sh in zip(s['years'], s['usd'], s['share']):
                w.writerow([s['code'], s['en'], s['rep'], y, u, sh])
    g = out['economy']['goods']
    with (d / 'trade_critical_goods.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['hs6', 'product', 'importer', 'month', 'partner_share', 'imports_from_partner_mn_usd',
                    'partner_share_12m'])
        for it in g['items']:
            for rep in ('KOR', 'JPN'):
                for p, (sh, u, s12) in zip(g['periods'], it[rep]):
                    if sh is not None or u is not None:
                        w.writerow([it['code'], it['en'], rep, p, sh, u, s12])
    with (d / 'court_rulings.csv').open('w', encoding='utf-8', newline='') as f:
        src = list(csv.DictReader((DATA / 'court_rulings.csv').open(encoding='utf-8')))
        dfn = json.loads((SITE / 'content.json').read_text(encoding='utf-8'))['defendants']
        w = csv.writer(f)
        w.writerow(['date', 'level', 'case_type', 'defendant', 'decision', 'japan_protest', 'source'])
        for r in src:
            w.writerow([r['date'], r['level'], r['case_type'], dfn.get(r['defendant'], r['defendant']), r['decision'],
                        r['japan_protest'], r['source']])
    return sorted(p.name for p in d.glob('*.csv'))


def main():
    mon = json.loads((DATA / 'dri_v2_monitor.json').read_text(encoding='utf-8'))
    c = json.loads((SITE / 'content.json').read_text(encoding='utf-8'))
    courts = json.loads((DATA / 'dri_v2_courts.json').read_text(encoding='utf-8'))
    layer_cols = list(c['layers'])
    triggers, actions, months = {}, {}, []
    for m in mon['months']:
        trig = []
        for t in m['triggers_ahead']:
            key = t['trigger']
            triggers.setdefault(key, [key, trigger_en(key, t['kind'], c)])
            trig.append([t['month'], t['kind'], key])
        for a in m['evidence_actions']:
            if a['date'] not in c['actions_en']:
                sys.exit(f"no English for action {a['date']}")
            actions[a['date']] = dict(d=a['date'], dir=a['direction'][:3], ru=a['description'],
                                      en=c['actions_en'][a['date']], url=a['url'])
        z = {l['column']: l['z'] for l in m['layers']}
        months.append(dict(
            m=m['month'], idx=m['index'], risk=RISK[m['risk']], g=m['gdelt_conflict_share'],
            z=[z[k] for k in layer_cols], trig=trig, out=[o['month'] for o in m['outcome']],
            turns=[[t['date'], 'kr' if t['country'] == 'РК' else 'jp', t['speaker'], t['level'], t['rung'], t['url']]
                   for t in m['evidence_turns']],
            acts=sorted({a['date'] for a in m['evidence_actions']})))
    eps = {}
    for m in mon['months']:
        for o in m['outcome']:
            if o['month'] not in c['episodes']:
                sys.exit(f"no public text for episode {o['month']}")
            eps[o['month']] = dict(type=c['types'][o['type']][2], **c['episodes'][o['month']])
    chk = mon['rule_check']
    out = dict(
        months=months, layers=[[k, *v] for k, v in c['layers'].items()], groups=c['groups'],
        stats=load_stats(c, [m['m'] for m in months]), stat_groups=c['stat_groups'], sources=c['sources'],
        types={v[2]: v[:2] for v in c['types'].values()}, episodes=eps,
        triggers=triggers, actions=actions, pipeline=c['pipeline'], rungs=c['rungs'], levels=c['levels'],
        check=dict(base=chk['base_rate'], high=chk['повышен']['share'], watch=chk['внимание']['share'],
                   normal=chk['обычный']['share'], idx70=chk['index_ge_70_share'], months=chk['months'],
                   episodes=chk['episodes']),
        courts=dict(base=courts['base_share_any_month'],
                    groups=[dict(ru=v[0], en=v[1], **{k: courts['groups'][g][k] for k in ('n', 'followed', 'share', 'mean_gap_sd')})
                            for g, v in COURT_GROUPS.items()]))
    out['economy'] = load_economy()
    out['files'] = write_csvs(out)
    blob = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    (SITE / 'data.json').write_text(blob, encoding='utf-8')
    tpl = (SITE / 'template.html').read_text(encoding='utf-8')
    page = tpl.replace('/*__DATA__*/null', blob)
    (SITE / 'artifact.html').write_text(page, encoding='utf-8')  # claude.ai Artifact adds its own skeleton
    head = ('<!doctype html>\n<html lang="ru">\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')
    (SITE / 'index.html').write_text(head + page, encoding='utf-8')  # standalone, for any static hosting
    # Deploy folder: only what the public site needs (no templates, no content sources).
    import shutil
    pub = SITE / 'public'
    if pub.exists():
        shutil.rmtree(pub)
    (pub / 'data').mkdir(parents=True)
    shutil.copy(SITE / 'index.html', pub / 'index.html')
    for f in (SITE / 'data').glob('*.csv'):
        shutil.copy(f, pub / 'data' / f.name)
    print(f'site/index.html: {len(months)} months, {len(eps)} episodes, {len(actions)} actions, {len(blob) // 1024} KB data')


if __name__ == '__main__':
    main()
