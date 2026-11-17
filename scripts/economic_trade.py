"""Import immutable official snapshots and regenerate trade research CSVs."""
import csv
import hashlib
import io
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dri.paths import DATA, write_generated
from dri.storage import Store

RAW = DATA / 'raw/trade'
HS_CONCORDANCE_URL = 'https://unstats.un.org/unsd/classifications/Econ/tables/HS-SITC-BEC%20Correlations_2022.xlsx'
PAIR = {'JPN': 'KOR', 'KOR': 'JPN'}
UN = {0: 'WLD', 392: 'JPN', 410: 'KOR'}
SECTORS = {
    'C26': 'Электроника, оптика и компьютеры',
    'C20': 'Химическая продукция',
    'C28': 'Машины и оборудование',
    'C29': 'Автомобили и комплектующие',
    'C27': 'Электрооборудование, включая аккумуляторы',
    'C24FER': 'Чёрная металлургия',
    'C24': 'Основные металлы',
    'C301': 'Суда и лодки',
    'B06': 'Сырая нефть и природный газ',
    'C19': 'Кокс и нефтепродукты',
}
PRODUCTS = {
    '854231': 'Процессоры и контроллеры',
    '854232': 'Интегральные схемы памяти',
    '850760': 'Литий-ионные аккумуляторы',
    '280920': 'Фосфорная и полифосфорные кислоты',
    '870899': 'Прочие части и принадлежности автомобилей',
    '720839': 'Горячекатаный рулонный прокат толщиной менее 3 мм',
    '890120': 'Танкеры',
    '271111': 'Сжиженный природный газ',
    '848620': 'Оборудование для производства полупроводников и интегральных схем',
}
MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
SOURCES = {
    'imf_imts': 'https://data.imf.org/Datasets/IMTS',
    'oecd_btige': 'https://www.oecd.org/en/data/datasets/bilateral-trade-in-goods-by-industry-and-end-use-category.html',
    'un_comtrade': 'https://comtradeplus.un.org/en/api-docs',
    'japan_mof': 'https://www.customs.go.jp/toukei/info/tsdl.htm',
    'korea_customs': 'https://www.tradedata.go.kr/cts/index_eng.do',
}


def snapshots():
    seen = set()
    for manifest in sorted(RAW.glob('downloads*.jsonl')):
        for line in manifest.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip():
                continue
            meta = json.loads(line)
            key = meta['file'], meta['retrieved_at']
            if key in seen:
                continue
            seen.add(key)
            path = RAW / Path(meta['archive']).name
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != meta['sha256']:
                raise ValueError(f'Snapshot checksum mismatch: {path}')
            yield meta, path, body if meta['file'].endswith('.pdf') else body.decode('utf-8-sig')


def csv_records(body):
    return csv.DictReader(io.StringIO(body))


def observation(frequency, period, reporter, partner, flow, classification, code,
                value, multiplier=0, *, flags=None, revision='latest_snapshot', publication=None):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError(f'Invalid value for {period}/{reporter}/{code}')
    return (frequency, period, reporter, partner, flow, classification, code,
            str(value), 'USD', multiplier, float(amount * (10 ** multiplier)),
            publication, revision, json.dumps(flags or {}, ensure_ascii=False, sort_keys=True))


def parse(name, body, country_codes):
    if name == 'imf_monthly.csv':
        for r in csv_records(body):
            reporter = r['COUNTRY']
            partner = 'WLD' if r['COUNTERPART_COUNTRY'] == 'G001' else r['COUNTERPART_COUNTRY']
            if partner not in ('WLD', PAIR[reporter]) or not r['OBS_VALUE']:
                continue
            yield observation('M', r['TIME_PERIOD'].replace('-M', '-'), reporter, partner,
                              r['INDICATOR'][0], 'TOTAL', 'TOTAL', r['OBS_VALUE'],
                              flags={k: r[k] for k in ('INDICATOR', 'SCALE', 'DERIVATION_TYPE', 'STATUS')})
    elif name in ('oecd_industry.csv', 'oecd_suppliers.csv'):
        for r in csv_records(body):
            reporter, partner = r['REF_AREA'], r['COUNTERPART_AREA']
            partner = 'WLD' if partner == 'W' else partner
            if name == 'oecd_suppliers.csv' and (partner in ('WLD', PAIR[reporter]) or partner not in country_codes.values()):
                continue
            if not r['OBS_VALUE']:
                continue
            if (r['UNIT_MEASURE'], r['END_USE'], r['FREQ']) != ('USD', 'TOTAL', 'A'):
                raise ValueError('Unexpected OECD unit, end use or frequency')
            yield observation('A', r['TIME_PERIOD'], reporter, partner, r['TRADE_FLOW'],
                              'CPA2.1', r['PRODUCT'], r['OBS_VALUE'], int(r['UNIT_MULT']),
                              flags={'END_USE': r['END_USE']})
    elif name.startswith('comtrade_'):
        annual = re.fullmatch(r'comtrade_suppliers_(\d{4})_(\d{6})\.json', name)
        monthly = re.fullmatch(r'comtrade_(\d{6})\.json', name)
        if not (annual or monthly):
            raise ValueError(f'Unknown Comtrade file: {name}')
        expected_period = (annual or monthly)[1]
        payload = json.loads(body)
        if payload.get('error') or payload['count'] != len(payload['data']) or payload['count'] >= 500:
            raise ValueError(f'Incomplete response: {name}')
        for r in payload['data']:
            reporter = UN[r['reporterCode']]
            partner = UN.get(r['partnerCode'])
            if annual:
                partner = partner or country_codes.get(r['partnerCode'])
            elif partner not in ('WLD', PAIR[reporter]):
                continue
            if partner is None or r['primaryValue'] is None:
                continue
            if (str(r['period']) != expected_period or r['cmdCode'] not in PRODUCTS
                    or (annual and (r['cmdCode'] != annual[2] or r['flowCode'] != 'M'))
                    or (r['partner2Code'], r['customsCode'], r['motCode']) != (0, 'C00', 0)):
                raise ValueError(f'Unexpected trade dimensions: {name}')
            period = str(r['period'])
            yield observation('A' if annual else 'M', period if annual else period[:4]+'-'+period[4:],
                              reporter, partner, r['flowCode'],
                              r['classificationCode'], r['cmdCode'], r['primaryValue'],
                              flags={k: r[k] for k in ('isOriginalClassification','isReported','isAggregate',
                                                        'cifvalue','fobvalue','qty','qtyUnitCode','netWgt')})


def japan_rows(name, body, publication):
    _, year, flow = name.removesuffix('.csv').split('_')
    records = list(csv_records(body))
    country = {r['Country']: r for r in records}
    if len(country) != len(records) or any(
        r['Year'] != year or r['Exp or Imp'] != {'X':'1','M':'2'}[flow]
        or not re.fullmatch(r'[1-7]\d\d', r['Country']) for r in records
    ):
        raise ValueError(f'Unexpected Japanese national table: {name}')
    for month, label in enumerate(MONTHS, 1):
        key = 'Value-' + label
        if label == 'Apr' and key not in records[0]:
            key = 'Value-Apl'
        world = sum(int(r[key] or 0) for r in records)
        if not world:
            continue
        for partner, value in [('KOR', country['103'][key]), ('WLD_SUM', world)]:
            if value == '':
                continue
            yield (f'{year}-{month:02d}', 'JPN', partner, flow, int(value), 'JPY', 3,
                   publication or None, 'published_table_snapshot')


def korea_rows(name, body, publication):
    from pypdf import PdfReader

    period = name[4:8]+'-'+name[8:10]
    pdf = PdfReader(io.BytesIO(body))
    for page, flow, label in ((12,'X','수출'), (14,'M','수입')):
        body_text = pdf.pages[page-1].extract_text(extraction_mode='layout')
        if not re.search(r'국가\(지역\)별', body_text) or not re.search(r'백만\s+달러', body_text):
            raise ValueError(f'Unexpected KCS table: {name}, page {page}')
        for partner, row_label in [('JPN',r'일\s+본'), ('WLD',r'전\s*체\s*'+label)]:
            matches = re.findall(r'^\s*'+row_label+r'\s+[\d,]+\s+([\d,]+)\s+', body_text, re.M)
            if len(matches) != 1:
                raise ValueError(f'Unverified KCS table row: {name}/{page}/{partner}')
            yield observation('M',period,'KOR',partner,flow,'TOTAL','TOTAL',matches[0].replace(',',''),6,
                              publication=publication,revision='monthly_confirmed_subject_to_annual_revision',
                              flags={'pdf_page':page,'source_unit':'USD million'})


def ingest(db):
    items = list(snapshots())
    reference = max((x for x in items if x[0]['file'] == 'comtrade_countries.json'),
                    key=lambda x: x[0]['retrieved_at'])
    countries = {r['PartnerCode']:r['PartnerCodeIsoAlpha3'] for r in json.loads(reference[2])['results']
                 if not r['isGroup'] and r.get('PartnerCodeIsoAlpha2') and r.get('PartnerCodeIsoAlpha3')}
    with db:
        for meta, path, body in items:
            name = meta['file']
            if name in ('comtrade_countries.json', 'kcs_202610.pdf'):
                continue
            source = ('imf_imts' if name.startswith('imf_') else
                      'oecd_btige' if name.startswith('oecd_') else
                      'japan_mof' if name.startswith('japan_') else
                      'korea_customs' if name.startswith('kcs_') else 'un_comtrade')
            inserted = db.execute(
                'INSERT INTO economic_downloads(source,logical_file,raw_path,url,retrieved_at,sha256) '
                'VALUES (?,?,?,?,?,?) ON CONFLICT(logical_file,retrieved_at) DO NOTHING',
                (source, name, path.relative_to(DATA).as_posix(), meta['url'], meta['retrieved_at'], meta['sha256']))
            if inserted.rowcount and source == 'japan_mof':
                db.executemany('INSERT INTO economic_trade_native VALUES (?,?,?,?,?,?,?,?,?,?)',
                               ((inserted.lastrowid, *row)
                                for row in japan_rows(name, body, meta.get('publication_date'))))
            elif inserted.rowcount:
                rows = (korea_rows(name,body,meta['publication_date']) if source == 'korea_customs'
                        else parse(name,body,countries))
                db.executemany('INSERT INTO economic_trade VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                               ((inserted.lastrowid, *row) for row in rows))


def month_shift(period, offset):
    year, month = map(int, period.split('-'))
    y, m = divmod(year*12+month-1+offset, 12)
    return f'{y:04d}-{m+1:02d}'


def ratio(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator else None


def monthly_rows(rows):
    by_key = {(r['period'], r['reporter'], r['partner'], r['flow']): r for r in rows}
    values = {key:r['value_usd'] for key,r in by_key.items()}
    periods = sorted({key[0] for key in values})

    def turnover(period, reporter):
        flows = [values.get((period, reporter, PAIR[reporter], flow)) for flow in ('X','M')]
        return sum(flows) if None not in flows else None

    for period in periods:
        for reporter, partner in PAIR.items():
            exports, imports = (values.get((period, reporter, partner, f)) for f in ('X','M'))
            world_exports, world_imports = (values.get((period, reporter, 'WLD', f)) for f in ('X','M'))
            total = turnover(period, reporter)
            last_year = turnover(month_shift(period, -12), reporter)
            yoy = ratio(total, last_year)
            previous = month_shift(period, -12)
            export_yoy = ratio(exports, values.get((previous,reporter,partner,'X')))
            import_yoy = ratio(imports, values.get((previous,reporter,partner,'M')))
            mirror = values.get((period, partner, reporter, 'M'))
            result = dict(period=period, reporter=reporter, partner=partner, exports_usd=exports,
                          imports_usd=imports, world_exports_usd=world_exports, world_imports_usd=world_imports,
                          turnover_usd=total, balance_usd=exports-imports if total is not None else None,
                          turnover_yoy=yoy-1 if yoy is not None else None,
                          exports_yoy=export_yoy-1 if export_yoy is not None else None,
                          imports_yoy=import_yoy-1 if import_yoy is not None else None,
                          import_share=ratio(imports, world_imports), export_share=ratio(exports, world_exports),
                          partner_reported_import_usd=mirror,
                          export_minus_mirror_usd=exports-mirror if exports is not None and mirror is not None else None,
                          mirror_gap_relative_to_export=ratio(mirror-exports, exports)
                          if mirror is not None and exports is not None else None)
            origin = by_key.get((period,reporter,partner,'X')) or by_key.get((period,reporter,partner,'M'))
            for field in ('source','url','retrieved_at','publication_date','revision_status'):
                result['source_url' if field == 'url' else field] = origin[field] if origin else None
            for width in (3, 12):
                window = [turnover(month_shift(period, -i), reporter) for i in range(width)]
                result[f'turnover_ma{width}_usd'] = sum(window)/width if None not in window else None
            yield result


def hs_alignment():
    from openpyxl import load_workbook

    path = RAW/'unsd_hs_correlations_2022.xlsx'
    workbook = load_workbook(path, read_only=True)
    versions = defaultdict(set)
    try:
        rows = workbook['HS SITC BEC'].iter_rows(min_col=5,max_col=7,values_only=True)
        if next(rows) != ('HS12','HS17','HS22'):
            raise ValueError('Unexpected UNSD concordance columns')
        for codes in rows:
            for code in set(codes).intersection(PRODUCTS):
                versions[code].add(codes)
    finally:
        workbook.close()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return [dict(commodity=code, one_to_one_same_code=int(versions[code] == {(code,code,code)}),
                 linked_triples=len(versions[code]), source_url=HS_CONCORDANCE_URL, source_sha256=sha)
            for code in PRODUCTS]


def dependency_rows(rows, comparable_codes=()):
    groups = defaultdict(dict)
    totals = {}
    for r in rows:
        key = (r['source'],r['frequency'],r['period'],r['reporter'],r['classification'],r['commodity'],r['flow'])
        if r['partner'] in groups[key]:
            raise ValueError(f'Duplicate active trade key: {key}/{r["partner"]}')
        groups[key][r['partner']] = r
        if r['commodity'] == '_T' and r['classification'] == 'CPA2.1':
            totals[(r['period'],r['reporter'],r['flow'],r['partner'])] = r['value_usd']
    shares = {}
    comparable_shares = {}
    for key, values in groups.items():
        partner = PAIR[key[3]]
        shares[key] = ratio(values.get(partner, {}).get('value_usd'), values.get('WLD', {}).get('value_usd'))
        source, frequency, period, reporter, classification, code, flow = key
        if code in comparable_codes and classification in ('H4','H5','H6'):
            lookup = (source,frequency,period,reporter,code,flow)
            if lookup in comparable_shares:
                raise ValueError(f'Multiple HS versions for the same period: {lookup}')
            comparable_shares[lookup] = shares[key]
    for key, values in sorted(groups.items()):
        source, frequency, period, reporter, classification, code, flow = key
        partner = PAIR[reporter]
        if partner not in values and 'WLD' not in values:
            continue
        world = values.get('WLD', {}).get('value_usd')
        bilateral = values.get(partner, {}).get('value_usd')
        suppliers = {k: v['value_usd'] for k,v in values.items() if k != 'WLD' and v['value_usd'] > 0}
        observed = sum(suppliers.values())
        coverage = ratio(observed, world)
        supplier_panel = flow == 'M' and frequency == 'A' and any(k != partner for k in suppliers)
        hhi_low = hhi_high = None
        if supplier_panel and coverage is not None and 0 < coverage <= 1.000001:
            hhi_low = sum((v/world)**2 for v in suppliers.values())
            hhi_high = min(1.0, hhi_low + max(0, 1-coverage)**2)
        previous = month_shift(period, -12) if frequency == 'M' else str(int(period)-1)
        prior_share = shares.get((source, frequency, previous, reporter, classification, code, flow))
        aligned = code in comparable_codes and classification in ('H4','H5','H6')
        if aligned:
            prior_share = comparable_shares.get((source,frequency,previous,reporter,code,flow))
        share = shares[key]
        yield dict(source=source, frequency=frequency, period=period, reporter=reporter, partner=partner,
                   classification=classification, commodity=code, flow=flow,
                   comparison_classification='HS2012–2022 (UNSD 1:1)' if aligned else classification,
                   label=PRODUCTS.get(code, SECTORS.get(code.removeprefix('CPA_2_1_'), code)),
                   bilateral_usd=bilateral, world_usd=world, partner_share=share,
                   partner_share_change_pp_yoy=100*(share-prior_share)
                   if share is not None and prior_share is not None else None,
                   bilateral_structure_share=ratio(bilateral,totals.get((period,reporter,flow,partner)))
                   if source == 'oecd_btige' else None,
                   named_suppliers=len(suppliers) if supplier_panel else None,
                   supplier_coverage=coverage if supplier_panel else None,
                   hhi_lower=hhi_low, hhi_upper=hhi_high,
                   largest_supplier=max(suppliers,key=suppliers.get) if hhi_low is not None else None,
                   largest_supplier_share=ratio(max(suppliers.values()),world) if hhi_low is not None else None,
                   available_by=max(r['retrieved_at'] for r in values.values()),
                   source_url=next(iter(values.values()))['url'])


def japan_comparison(db, monthly):
    native = [dict(r) for r in db.execute(
        'SELECT * FROM economic_trade_native_current ORDER BY period,flow,partner')]
    by_key = {(r['period'],r['flow'],r['partner']):r for r in native}
    imf = {(r['period'],r['flow'],r['partner']):r['value_usd'] for r in monthly if r['reporter']=='JPN'}
    for r in native:
        if r['partner'] != 'KOR':
            continue
        period, flow = r['period'], r['flow']
        world = by_key[period,flow,'WLD_SUM']
        national_share = ratio(r['value_native'],world['value_native'])
        imf_share = ratio(imf.get((period,flow,'KOR')),imf.get((period,flow,'WLD')))
        yield dict(period=period,flow=flow,korea_value_thousand_jpy=r['value_native'],
                   world_sum_thousand_jpy=world['value_native'],japan_mof_share=national_share,
                   imf_share=imf_share,share_gap=(national_share-imf_share) if imf_share is not None else None,
                   publication_date=r['publication_date'],retrieved_at=r['retrieved_at'],source_url=r['url'])


def export(name, rows):
    rows = list(rows)
    if not rows:
        raise ValueError(f'No observations for {name}')
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    write_generated(DATA / name, output.getvalue())
    return len(rows)


def recalculate(db):
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute('SELECT * FROM economic_trade_current ORDER BY source,period,reporter,partner,flow,classification,commodity')]
    imf = [r for r in rows if r['source'] == 'imf_imts']
    imf_months = defaultdict(set)
    for r in imf:
        imf_months[(r['period'],r['reporter'])].add((r['partner'],r['flow']))
    local = [r for r in rows if r['source']=='korea_customs'
             and len(imf_months[(r['period'],r['reporter'])]) < 4]
    local_months = {(r['period'],r['reporter']) for r in local}
    monthly = [r for r in imf if (r['period'],r['reporter']) not in local_months] + local
    detail = [r for r in rows if r['classification'] != 'TOTAL']
    alignment_path = DATA/'trade_hs_alignment.csv'
    comparable = set()
    if alignment_path.exists():
        workbook_path = RAW/'unsd_hs_correlations_2022.xlsx'
        checksum = hashlib.sha256(workbook_path.read_bytes()).hexdigest()
        for row in csv_records(alignment_path.read_text(encoding='utf-8')):
            if row['source_sha256'] != checksum:
                raise ValueError('Regenerate the HS alignment after changing the source workbook')
            if row['one_to_one_same_code'] == '1':
                comparable.add(row['commodity'])
    dependencies = list(dependency_rows(detail, comparable))
    result = {
        'monthly_raw': len(monthly), 'commodity_raw': len(detail),
        'trade_monthly': export('trade_monthly.csv', monthly_rows(monthly)),
        'trade_structure': export('trade_structure.csv', (r for r in dependencies if r['classification'] == 'CPA2.1')),
        'trade_dependency': export('trade_dependency.csv', (r for r in dependencies if r['flow'] == 'M')),
        'trade_hs6': export('trade_hs6.csv', (r for r in dependencies if r['source'] == 'un_comtrade')),
    }
    national = list(japan_comparison(db, imf))
    if national:
        result['japan_check'] = export('trade_japan_check.csv', national)
    return result


if __name__ == '__main__':
    if sys.argv[1:] == ['--audit-hs']:
        export('trade_hs_alignment.csv', hs_alignment())
    elif sys.argv[1:]:
        raise SystemExit('Usage: economic_trade.py [--audit-hs]')
    store = Store()
    try:
        ingest(store.db)
        print(json.dumps(recalculate(store.db), ensure_ascii=False))
    finally:
        store.db.close()
