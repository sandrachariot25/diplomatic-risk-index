"""Monthly leader approval: Korean president (Gallup Korea + Realmeter) and Japanese cabinet (all pollsters, NHK).

    python scripts/fetch_approval.py     # network: raw wikitext -> data/approval/
    python scripts/approval_v2.py        # offline: -> data/approval_monthly.csv

Korea: ko.wikipedia "대한민국의 대통령 지지율", weekly table rows "YYYY년 M월 N주" with Gallup Korea and Realmeter
cells; monthly value = mean of all weekly readings of both pollsters in the month (they differ by a few points;
the monthly change is what matters). Months without a sitting elected president (acting presidents after the
2016-2017 and 2024-2025 impeachments) stay empty - the page deliberately excludes acting presidents.
Japan: en.wikipedia "Opinion polling for the 2021/2024/2026/next Japanese general election", cabinet approval
tables (fieldwork end date, pollster, approve). Coverage starts 2017-10 (no monthly compilation found for
2015-2017-09; NHK's archive could not be fetched by the project tools). Monthly value = mean over pollsters,
plus the NHK value separately.
Wikipedia is a secondary compilation; spot-check against the pollsters' releases before publication.
"""
import csv
from collections import defaultdict
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'data' / 'approval'
OUT = ROOT / 'data' / 'approval_monthly.csv'
MON = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov',
                                    'Dec'], 1)}


def clean(cell):
    cell = re.sub(r'\{\{efn[^{}]*\}\}', '', cell)
    cell = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>', '', cell, flags=re.S)
    cell = cell.split('|')[-1] if 'style=' in cell else cell
    return re.sub(r"'''|''|<[^>]+>", '', cell).strip()


def num(cell):
    m = re.search(r'(\d+(?:\.\d+)?)\s*%?', clean(cell))
    return float(m.group(1)) if m else None


def korea():
    t = (SRC / 'kr_president.wiki').read_text(encoding='utf-8')
    t = re.sub(r'<!--.*?-->', '', t, flags=re.S)
    vals = defaultdict(list)
    current = None
    # Tables mix one-cell-per-line and inline "||" layouts: walk all cells in order; a date cell opens a week,
    # the following numeric cells (Gallup, Realmeter) belong to it; a table end closes it.
    for line in t.splitlines():
        if line.startswith('|}') or line.startswith('{|'):
            current = None
            continue
        if not line[:1] in ('|', '!'):
            continue
        for cell in re.split(r'\|\||!!', line[1:]):
            d = re.search(r'(\d{4})년\s*(\d{1,2})월\s*\d주', cell)
            if d:
                current = f'{int(d.group(1)):04d}-{int(d.group(2)):02d}'
                continue
            if current and '미조사' not in cell and '%' in cell:
                v = num(cell)
                if v is not None and 3 <= v <= 95:
                    vals[current].append(v)
    return vals


def japan():
    allv, nhk = defaultdict(list), defaultdict(list)
    seen = set()

    def add(month, day, pollster, approve):
        key = (month, day, pollster, approve)
        if key in seen or not 5 <= approve <= 95:
            return
        seen.add(key)
        allv[month].append(approve)
        if pollster.startswith('NHK'):
            nhk[month].append(approve)

    # 2017-10..2021-10 page: year in "=== YYYY ===" headers, dates like "21–22 Dec", no sample-size column.
    t = (SRC / 'jp_2021.wiki').read_text(encoding='utf-8')
    sec = t[t.find('Cabinet approval/disapproval ratings'):]
    sec = sec[:sec.find('==See also')]
    for ym in re.finditer(r'^===\s*(\d{4})\s*===\s*$(.*?)(?=^===|\Z)', sec, re.M | re.S):
        year = int(ym.group(1))
        for row in ym.group(2).split('\n|-'):
            cells = [x.strip() for x in row.split('\n|')][1:]
            if len(cells) < 3:
                continue
            d = re.search(r'(\d{1,2})\s*([A-Z][a-z]{2})\s*$', re.sub(r'<.*', '', cells[0]).strip())
            if not d or d.group(2) not in MON:
                continue
            pollster = clean(re.sub(r'\[\S+\s([^\]]+)\]', r'\1', re.sub(r'\{\{.*?\}\}', '', cells[1])))
            vals = [num(c) for c in cells[2:] if '[[' not in c and 'rowspan' not in c.split('|')[0] or
                    ('rowspan' in c and '[[' not in c)]
            vals = [v for v in vals if v is not None]
            if vals:
                add(f'{year:04d}-{MON[d.group(2)]:02d}', d.group(1), pollster, vals[0])
    for f in ('jp_2024', 'jp_2026', 'jp_next'):
        t = (SRC / f'{f}.wiki').read_text(encoding='utf-8')
        i = t.find('approval/disapproval ratings')
        sec = t[i:]
        end = re.search(r'^==\s*See also', sec, re.M)
        sec = sec[:end.start()] if end else sec
        for row in sec.split('\n|-'):
            d = re.search(r'\{\{Opdrts\|(\d*)\|(\d+)\|([A-Z][a-z]{2})\|(\d{4})\}\}', row)
            if not d:
                continue
            cells = [x.strip() for x in row.split('\n|')]
            start = next((k for k, c in enumerate(cells) if '{{Opdrts' in c), None)
            if start is None or start.startswith('!') if isinstance(start, str) else False:
                continue
            cells = cells[start:]            # [date, pollster, sample size, (PM), approve, disapprove, ...]
            if len(cells) < 5 or cells[0].startswith('!'):
                continue
            pollster = re.sub(r'\[\S+\s([^\]]+)\]', r'\1', cells[1])
            pollster = clean(re.sub(r'\{\{.*?\}\}|<ref.*', '', pollster)).strip()
            numeric = [num(c) for c in cells[3:] if '[[' not in c]
            numeric = [v for v in numeric if v is not None]
            if not numeric:
                continue
            add(f'{int(d.group(4)):04d}-{MON[d.group(3)]:02d}', d.group(2), pollster, numeric[0])
    return allv, nhk


def main():
    kr = korea()
    jp, nhk = japan()
    months = sorted(set(kr) | set(jp))
    months = [m for m in months if '2014-12' < m]
    rows = [dict(month=m, kr_approval=round(float(np.mean(kr[m])), 2) if kr.get(m) else '', kr_n=len(kr.get(m, [])),
                 jp_approval=round(float(np.mean(jp[m])), 2) if jp.get(m) else '', jp_n=len(jp.get(m, [])),
                 jp_approval_nhk=round(float(np.mean(nhk[m])), 2) if nhk.get(m) else '') for m in months]
    with OUT.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    kr_m = [r['month'] for r in rows if r['kr_approval'] != '']
    jp_m = [r['month'] for r in rows if r['jp_approval'] != '']
    print(f'{OUT.name}: KR {len(kr_m)} months {kr_m[0]}..{kr_m[-1]}; JP {len(jp_m)} months {jp_m[0]}..{jp_m[-1]}; '
          f'JP with NHK {sum(r["jp_approval_nhk"] != "" for r in rows)}')
    for m in ('2015-06', '2016-11', '2017-07', '2018-10', '2019-07', '2021-01', '2023-12', '2024-11', '2025-12', '2026-08'):
        r = next((r for r in rows if r['month'] == m), None)
        if r:
            print(f"  {m}: KR {r['kr_approval']} (n={r['kr_n']})  JP {r['jp_approval']} (n={r['jp_n']}, NHK {r['jp_approval_nhk']})")


if __name__ == '__main__':
    main()
