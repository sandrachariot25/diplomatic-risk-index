"""Conservative deterministic identities; fuzzy matches never imply a merge."""
import hashlib
import json
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def normalized(text):
    return ' '.join(unicodedata.normalize('NFC', text or '').split())

def fingerprint(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def normalize_url(url):
    p = urlsplit(url)
    if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
        raise ValueError('Expected public HTTP(S) URL without credentials')
    host = p.hostname.lower()
    port = p.port
    if port and not (p.scheme == 'https' and port == 443 or p.scheme == 'http' and port == 80):
        host += f':{port}'
    pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
    if host == 'www.mofa.go.kr' and p.path.endswith('/view.do'):
        pairs = [(k, v) for k, v in pairs if k == 'seq']
    return urlunsplit((p.scheme.lower(), host, p.path or '/', urlencode(sorted(pairs)), ''))

def official_id(url):
    p = urlsplit(url)
    if p.hostname == 'www.mofa.go.kr':
        return dict(parse_qsl(p.query)).get('seq')
    if p.hostname in {'www.mofa.go.jp', 'japan.kantei.go.jp'}:
        return p.path
    return None

def token_similarity(a, b):
    def grams(text):
        s = normalized(text).casefold()
        words = re.findall(r'\w+', s)
        # Character trigrams also work for Korean/Japanese without spaces.
        return set(zip(words, words[1:])) if len(words) > 4 else {s[i:i+3] for i in range(max(1, len(s)-2))}
    aa, bb = grams(a), grams(b)
    return len(aa & bb) / len(aa | bb) if aa | bb else 0.0
