"""DRI v2 stage 1: offline relevance pre-filter for Korean Assembly candidate turns.

Lexical rules only (no model, no network). Calibrated against the expert-checked pilot labels
(core/peripheral = relevant; mention/irrelevant = not relevant). Its job is to drop passing
mentions of Japan before semantic annotation, while keeping recall of relevant turns high.

    python scripts/relevance_v2.py calibrate   # recall/precision on pilot labels per threshold
    python scripts/relevance_v2.py queue       # scores all candidates, writes the annotation queue
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.pilot_v2 import DATA, kr_level, stratum, excerpt, KR_QUOTA  # noqa: E402

QUEUE = DATA / 'dri_v2_queue_kr.jsonl'
SEED = 'dri-v2-queue-2026-11-10'
THRESHOLD = 3          # chosen in `calibrate`; see docs/CODEBOOK_v2.md
# Month-stratified random sample: the same cap for every month, independent of known crises,
# so that the later early-warning test is not biased by selecting on the outcome.
MONTH_CAP = 25

JAPAN = re.compile(r'일본|日本|일측|일 측|대일|아베|스가|기시다|이시바|다카이치|고노|모테기|하야시|가미카와|이와야|도쿄전력|일왕|천황|자위대')
# Bilateral topics: a hit means the turn is about the relationship, not Japan as an example.
TOPICS = re.compile(r'한일|한·일|한-일|한ㆍ일|한미일|한·미·일|한ㆍ미ㆍ일|독도|다케시마|위안부|소녀상|강제징용|강제동원|징용|'
                    r'사도광산|사도 광산|군함도|하시마|메이지 산업|오염수|처리수|후쿠시마|수출규제|수출 규제|화이트리스트|'
                    r'지소미아|GSOMIA|정보보호협정|욱일기|전범기|야스쿠니|교과서 왜곡|역사 왜곡|식민지배|식민 지배|일제|'
                    r'청구권|1965|화해치유재단|화해·치유재단|과거사|셔틀외교|셔틀 외교|초계기|레이더|대륙붕|7광구|공동개발구역|'
                    r'통화스와프|통화 스와프|역사 문제|역사문제|사죄|반성|'
                    # Added after calibration misses (pilot v2.1): heritage, discharge, seafood, materials, diplomacy framing.
                    r'세계유산|유네스코|방류|수산물 수입|수입 규제|수입규제|소재·부품|소재ㆍ부품|소부장|'
                    r'굴종|저자세|빈손외교|대일외교|대일 외교|대일정책|대일 정책')
# Typical passing-mention frames: Japan as a benchmark or statistic.
COMPARISON = re.compile(r'일본(?:처럼|같이|과 같이|의 경우|의 사례|사례|에서는|도 |은 [0-9]|이 [0-9]|의 [0-9])|'
                        r'(?:미국|독일|영국|프랑스|중국|대만|호주|싱가포르)[,·ㆍ ]+(?:일본|日本)|'
                        r'(?:일본|日本)[,·ㆍ ]+(?:미국|독일|영국|프랑스|중국|대만|호주|싱가포르)')


def features(text):
    japan = len(JAPAN.findall(text))
    topics = len(TOPICS.findall(text))
    comparison = len(COMPARISON.findall(text))
    return japan, topics, comparison


def score(text):
    japan, topics, comparison = features(text)
    # Topic terms are the strongest evidence; Japan mentions add weight; benchmark frames subtract.
    return 2 * min(topics, 5) + min(japan, 6) - 2 * min(comparison, 3)


def load_candidates():
    for term in ('t19', 't20', 't21', 't22', 't22_live'):  # t22_live: scripts/collect_assembly_records.py
        path = DATA / f'kr_hearings_candidates_{term}.jsonl'
        if not path.exists():
            continue
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if row['role_group'] == 'excluded' or not row['speech_date'] or len(row['text']) < 80:
                    continue
                yield row


def cmd_calibrate(_):
    units = {u['unit_id']: u for u in map(json.loads, (DATA / 'dri_v2_pilot_units.jsonl').read_text(encoding='utf-8').splitlines())}
    ann = [json.loads(l) for l in (DATA / 'dri_v2_pilot_annotations.jsonl').read_text(encoding='utf-8').splitlines()]
    wanted = {u for u in units if u.startswith('kr:')}
    full = {}
    for row in load_candidates():
        key = f'kr:{row["conf_num"]}:{row["turn_seq"]}'
        if key in wanted:
            full[key] = row['text']
    labelled = [(score(full[r['unit_id']]), r['relevance'] in {'core', 'peripheral'}, r['unit_id'])
                for r in ann if r['unit_id'] in full]
    positives = sum(y for _, y, _ in labelled)
    print(f'pilot KR turns {len(labelled)}: relevant {positives}, not relevant {len(labelled) - positives}')
    print('threshold  kept  recall  precision  dropped_not_relevant')
    for t in range(-2, 13):
        kept = [(s, y) for s, y, _ in labelled if s >= t]
        tp = sum(y for _, y in kept)
        dropped_neg = sum(1 for s, y, _ in labelled if s < t and not y)
        print(f'{t:9} {len(kept):5} {tp/positives:7.2f} {tp/len(kept) if kept else 0:10.2f} {dropped_neg:8}')
    missed = [(s, u) for s, y, u in labelled if y and s < THRESHOLD]
    print(f'relevant turns lost at threshold {THRESHOLD}:', missed)


def cmd_queue(_):
    rng = random.Random(SEED)
    rows, dist = [], Counter()
    for row in load_candidates():
        s = score(row['text'])
        day = date.fromisoformat(str(row['speech_date'])[:10])
        layer = stratum(day)
        dist[(layer, s >= THRESHOLD)] += 1
        if s < THRESHOLD:
            continue
        rows.append((layer, s, day, row))
    pilot = {json.loads(l)['unit_id'] for l in (DATA / 'dri_v2_pilot_units.jsonl').read_text(encoding='utf-8').splitlines()}
    by_month = {}
    for item in rows:
        row = item[3]
        if f'kr:{row["conf_num"]}:{row["turn_seq"]}' not in pilot:
            by_month.setdefault(item[2].strftime('%Y-%m'), []).append(item)
    queue = []
    for month in sorted(by_month):
        pool = sorted(by_month[month], key=lambda item: (item[3]['conf_num'], item[3]['turn_seq']))
        picked = rng.sample(pool, min(MONTH_CAP, len(pool)))
        # Inverse-probability weight lets monthly shares be estimated for all relevant turns of the month.
        weight = len(pool) / len(picked)
        queue.extend((item, weight, len(pool)) for item in picked)
    out = []
    for (layer, s, day, row), weight, month_pool in queue:
        level, status = kr_level(row, day)
        text, cut = excerpt(row['text'], 1200)
        out.append(dict(
            unit_id=f'kr:{row["conf_num"]}:{row["turn_seq"]}', source='assembly_kr', country='ROK', language='ko',
            date=day.isoformat(), stratum=layer, relevance_score=s, sampling_weight=round(weight, 4),
            month_relevant_pool=month_pool, speaker=row['speaker_name'],
            speaker_pos=row['speaker_pos'], party=row['party'], gov_status=status, speaker_level=level,
            text=text, excerpted=cut, text_sha256=hashlib.sha256(row['text'].encode()).hexdigest(),
            source_url=f'https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id={row["conf_num"]}&type=view'))
    queue = sorted(out, key=lambda q: (q['date'], q['unit_id']))
    QUEUE.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in queue), encoding='utf-8')
    print('candidates by stratum (kept / dropped):')
    for layer in KR_QUOTA:
        print(f'  {layer:14} kept {dist[(layer, True)]:6}  dropped {dist[(layer, False)]:6}')
    months = Counter(q['date'][:7] for q in queue)
    print(f'queue {len(queue)} (up to {MONTH_CAP} random relevant turns per month; pilot units excluded)')
    print(f'months covered {len(months)}; months below cap {sum(n < MONTH_CAP for n in months.values())}; '
          f'empty months {[m for m in (f"{y}-{mm:02}" for y in range(2015, 2027) for mm in range(1, 13)) if m <= "2026-10" and m not in months]}')
    print('queue by stratum:', dict(Counter(q['stratum'] for q in queue)))
    print('queue by year:', dict(sorted(Counter(q['date'][:4] for q in queue).items())))
    print('queue by level:', dict(Counter(q['speaker_level'] for q in queue)))
    print('characters to read:', sum(len(q['text']) for q in queue))


# ---------------------------------------------------------------- Japanese Diet (kokkai_speeches_full)
QUEUE_JP = DATA / 'dri_v2_queue_jp.jsonl'
MONTH_CAP_JP = 15
KOREA_JP = re.compile(r'韓国|ソウル|朴槿恵|文在寅|尹錫悦|李在明|韓国政府|韓国側|日韓')
TOPICS_JP = re.compile(r'日韓|竹島|独島|慰安婦|少女像|徴用|旧朝鮮半島出身労働者|佐渡|軍艦島|明治日本の産業革命遺産|'
                       r'輸出管理|輸出規制|ホワイト国|グループA|フッ化水素|レジスト|ポリイミド|GSOMIA|軍事情報包括保護協定|'
                       r'レーダー照射|火器管制レーダー|旭日旗|処理水|汚染水|水産物|輸入規制|日韓合意|請求権|1965|'
                       r'歴史認識|歴史問題|教科書|靖国|大法院|差し押さえ|現金化|日米韓|シャトル外交|大陸棚|共同開発区域|'
                       r'漁業協定|排他的経済水域|対韓|反日|嫌韓|通貨スワップ|関係改善|戦後最悪|'
                       # Added after a 30-speech check of dropped records: diplomatic-contact markers.
                       r'申入れ|申し入れ|抗議|遺憾|大統領|新政権|政権交代|駐韓|在韓|大使館|総領事|首脳会談|外相会談')
COMPARISON_JP = re.compile(r'(?:米国|アメリカ|中国|台湾|ドイツ|英国|イギリス|フランス|豪州)[、・](?:韓国)|'
                           r'韓国[、・](?:米国|アメリカ|中国|台湾|ドイツ|英国|イギリス|フランス|豪州)|'
                           r'韓国(?:など|のように|の例|の事例|と比べ|に比べ)')
JP_RULING_UNTIL_2025_10 = ('自由民主党', '公明党')


def score_jp(text):
    korea = len(KOREA_JP.findall(text))
    topics = len(TOPICS_JP.findall(text))
    comparison = len(COMPARISON_JP.findall(text))
    return 2 * min(topics, 5) + min(korea, 6) - 2 * min(comparison, 3)


def jp_status(group, day):
    if not group:
        return None
    if day < date(2025, 10, 21):
        return 'ruling' if any(p in group for p in JP_RULING_UNTIL_2025_10) else 'opposition'
    if '自由民主党' in group:
        return 'ruling'
    return 'confidence_partner' if '日本維新の会' in group else 'opposition'


def jp_level_full(position, role):
    position, role = position or '', role or ''
    if role in ('参考人', '公述人', '証人'):
        return 'L1'
    if '内閣総理大臣' in position:
        return 'L5'
    if ('大臣' in position and '副大臣' not in position and '政務官' not in position) or '官房長官' in position:
        return 'L4'
    if any(k in position for k in ('副大臣', '政務官', '局長', '審議官', '長官', '次長', '室長', '参事官', '課長',
                                   '政府参考人', '内閣官房', '省', '庁')) or role == '政府参考人':
        return 'L3'
    return 'L2'


def excerpt_jp(text, limit=1200):
    text = re.sub(r'\s+', ' ', re.sub(r'^[○◯][^\s　]+[\s　]+', '', text)).strip()
    if len(text) <= limit:
        return text, False
    sentences = re.split(r'(?<=[。！？])', text)
    hits = [i for i, s in enumerate(sentences) if KOREA_JP.search(s) or TOPICS_JP.search(s)]
    keep = sorted({j for i in hits for j in (i - 1, i, i + 1) if 0 <= j < len(sentences)})
    out, last, size = [], None, 0
    for j in keep:
        if size + len(sentences[j]) > limit:
            break
        if last is not None and j != last + 1:
            out.append('…')
        out.append(sentences[j])
        size += len(sentences[j])
        last = j
    return ''.join(out) or text[:limit], True


def cmd_queue_jp(_):
    import sqlite3
    rng = random.Random(SEED + '-jp')
    with sqlite3.connect((DATA / 'dri.sqlite3').resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('''SELECT speech_id, spoken_date, speaker, speaker_group, speaker_position, speaker_role,
                             speech, speech_url, name_of_house, name_of_meeting FROM kokkai_speeches_full''').fetchall()
    kept, dropped, by_month = Counter(), Counter(), {}
    for sid, spoken, speaker, group, position, role, speech, url, house, meeting in rows:
        day = date.fromisoformat(spoken)
        layer = stratum(day)
        s = score_jp(speech)
        if s < THRESHOLD:
            dropped[layer] += 1
            continue
        kept[layer] += 1
        by_month.setdefault(spoken[:7], []).append((s, day, layer, sid, speaker, group, position, role, speech, url, house, meeting))
    queue = []
    for month in sorted(by_month):
        pool = sorted(by_month[month], key=lambda item: item[3])
        picked = rng.sample(pool, min(MONTH_CAP_JP, len(pool)))
        weight = len(pool) / len(picked)
        for s, day, layer, sid, speaker, group, position, role, speech, url, house, meeting in picked:
            text, cut = excerpt_jp(speech)
            queue.append(dict(
                unit_id=f'jp:{sid}', source='kokkai_jp_full', country='JPN', language='ja', date=day.isoformat(),
                stratum=layer, relevance_score=s, sampling_weight=round(weight, 4), month_relevant_pool=len(pool),
                speaker=speaker, speaker_pos=position, party=group, gov_status=jp_status(group, day),
                speaker_level=jp_level_full(position, role), venue=f'{house} {meeting}', text=text, excerpted=cut,
                text_sha256=hashlib.sha256(speech.encode()).hexdigest(), source_url=url))
    queue.sort(key=lambda q: (q['date'], q['unit_id']))
    QUEUE_JP.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in queue), encoding='utf-8')
    print('speeches by stratum (kept / dropped):')
    for layer in KR_QUOTA:
        print(f'  {layer:14} kept {kept[layer]:6}  dropped {dropped[layer]:6}')
    months = Counter(q['date'][:7] for q in queue)
    print(f'queue {len(queue)} (up to {MONTH_CAP_JP}/month); months covered {len(months)}')
    print('queue by year:', dict(sorted(Counter(q['date'][:4] for q in queue).items())))
    print('queue by level:', dict(Counter(q['speaker_level'] for q in queue)))
    print('queue by status:', dict(Counter(q['gov_status'] for q in queue)))
    print('characters to read:', sum(len(q['text']) for q in queue))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('cmd', choices=['calibrate', 'queue', 'queue_jp'])
    args = parser.parse_args()
    globals()['cmd_' + args.cmd](args)
