"""Download raw wikitext of public approval-rating tables (Wikipedia) into data/approval/ for parsing.

    python scripts/fetch_approval.py

Korea: ko.wikipedia "대한민국의 대통령 지지율" (Gallup Korea series). Japan: en.wikipedia "Opinion polling for the
2017/2021/2024/2026 Japanese general election" (cabinet approval tables by pollster, incl. NHK).
Wikipedia is a secondary compilation: values must be spot-checked against the pollsters' own releases.
Sequential requests with a 3 s pause; files are stored with retrieval time and SHA-256 in a manifest.
"""
from hashlib import sha256
import json
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'approval'
PAGES = {
    'kr_president.wiki': ('ko', '대한민국의 대통령 지지율'),
    'jp_naikaku_ja.wiki': ('ja', '内閣支持率'),
    'jp_2021.wiki': ('en', 'Opinion polling for the 2021 Japanese general election'),
    'jp_2024.wiki': ('en', 'Opinion polling for the 2024 Japanese general election'),
    'jp_2026.wiki': ('en', 'Opinion polling for the 2026 Japanese general election'),
    'jp_next.wiki': ('en', 'Opinion polling for the next Japanese general election'),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, (lang, title) in PAGES.items():
        url = f'https://{lang}.wikipedia.org/w/index.php?title={quote(title)}&action=raw'
        req = Request(url, headers={'User-Agent': 'DiplomaticRiskIndex/1.0 research (approval series)'})
        try:
            with urlopen(req, timeout=60) as r:
                body = r.read()
            (OUT / name).write_bytes(body)
            manifest[name] = dict(url=url, bytes=len(body), sha256=sha256(body).hexdigest(),
                                  retrieved_at=time.strftime('%Y-%m-%dT%H:%M:%S'))
            print(name, len(body))
        except Exception as exc:  # noqa: BLE001
            manifest[name] = dict(url=url, error=f'{type(exc).__name__}: {exc}')
            print(name, 'ERROR', exc)
        time.sleep(3)
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
