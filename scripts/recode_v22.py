"""DRI v2.2 recode after the blind check (docs/CODEBOOK_v2.md, rules agreed with the expert on 12.11.2026).

    python scripts/recode_v22.py

Rules: (A) core = speaker states a position on the other country / bilateral issue; (B) "all options",
"resolute response" without a named measure = R4, R5 only for a concrete measure threatened by the state;
resolutions and MPs' calls are coded by content (demand = R3); (C) urgency words do not raise the rung:
R3 + urgency flag; (D) a call on one's own government = R3 only if a concrete act is named, otherwise R1.
Previous values are kept in `rung_v21` / `relevance_v21`. Idempotent.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.annotate_v2 import OUT, load_done, load_units  # noqa: E402

VERSION = 'DRI-v2.2'
URGENCY = re.compile(r'即時|即刻|直ちに|ただちに|一日も早く|一刻も早く|早急に|至急|今すぐ|즉시|즉각|조속히|하루빨리|당장')

# unit_id -> new rung (rule in comment). Rows reviewed: all R4-R6 and R3 with criticism of own government/both.
RUNG = {
    # (C) urgency-only R4 -> R3
    'kr:43611:4': 3, 'kr:43722:89': 3, 'kr:45982:27': 3, 'jp:119715254X00320181031_021': 3,
    'jp:119703968X00420181128_005': 3, 'jp:120003968X00120191018_010': 3, 'jp:120014080X00620191203_028': 3,
    'jp:120315261X00120201105_351': 3, 'jp:120405254X00120210118_011': 3, 'jp:120415254X00120210118_009': 3,
    'jp:121303968X01420240612_012': 3,
    # resolutions coded by content (demand = R3, warning+condemnation = R2)
    'kr:39455:23': 2, 'kr:45982:28': 3, 'kr:46392:11': 3, 'kr:46392:12': 3, 'kr:46479:8': 3, 'kr:46479:9': 3,
    'kr:47153:3': 3, 'kr:47309:280': 3, 'kr:52084:1': 3, 'kr:52084:39': 3, 'kr:52084:41': 3, 'kr:52084:44': 3,
    # (D) MPs naming a measure for their own government = R3, not R5/R4
    'kr:39627:370': 3, 'kr:39703:1211': 3, 'kr:39992:553': 3, 'kr:44049:401': 3, 'kr:44565:660': 3,
    'kr:45857:658': 3, 'kr:47450:993': 3, 'kr:52384:453': 3, 'jp:119315261X00120170130_522': 3,
    'jp:119805268X00120190227_224': 3,
    # (B) "will respond / all options / countermeasures" without a named measure = R4
    'kr:44301:50': 4, 'jp:119805268X00120190227_221': 4, 'jp:119805268X00120190227_256': 4,
    'jp:119815261X00720190308_184': 4, 'jp:120113950X00120200709_198': 4, 'jp:120113950X00120200709_200': 4,
    'jp:120415261X00120210127_411': 4, 'jp:120403968X00620210407_114': 4,
    # WTO process only asked about, no own stance
    'kr:45174:222': 1,
    # (D) general calls for firmness, no concrete act = R1
    'kr:40258:814': 1, 'kr:52560:488': 1, 'kr:42830:779': 1, 'kr:43886:945': 1,
    'jp:119803968X00720190412_008': 1, 'jp:119813950X01820190618_013': 1,
}
RELEVANCE = {'kr:45174:222': 'peripheral'}


def main():
    units, done = load_units(), load_done()
    assert set(RUNG) <= set(done), set(RUNG) - set(done)
    changed = urgent = 0
    for uid, r in done.items():
        r.setdefault('rung_v21', r['rung'])
        r.setdefault('relevance_v21', r['relevance'])
        new_rung = RUNG.get(uid, r['rung_v21'])
        new_rel = RELEVANCE.get(uid, r['relevance_v21'])
        changed += (new_rung, new_rel) != (r['rung_v21'], r['relevance_v21'])
        r['rung'], r['relevance'] = new_rung, new_rel
        relevant = new_rel in {'core', 'peripheral'}
        r['urgency'] = bool(relevant and new_rung >= 2 and URGENCY.search(units[uid]['text']))
        urgent += r['urgency']
        r['annotation_version'] = VERSION
    order = {uid: i for i, uid in enumerate(units)}
    rows = sorted(done.values(), key=lambda r: order[r['unit_id']])
    OUT.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print(f'{VERSION}: {changed} rows recoded, urgency flag on {urgent}; total {len(rows)}')


if __name__ == '__main__':
    main()
