"""Bibliographic media records only. No inference of speeches from news prose."""
from datetime import date
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from ..models import Document
from ..identity import fingerprint, normalize_url

def metadata_document(row, source):
    if source['source_type']!='secondary':
        raise ValueError('Media connector accepts secondary publishers only')
    if row.get('text') or row.get('quotes') or row.get('statements'):
        raise ValueError('Media metadata channel cannot import prose, quotes or statements')
    url=normalize_url(row['url'])
    allowed=set(source.get('article_hosts', [urlsplit(source['base_url']).hostname]))
    if urlsplit(url).scheme!='https' or urlsplit(url).hostname not in allowed:
        raise ValueError('Article URL is outside audited publisher hosts')
    published=row['published_date']
    date.fromisoformat(published)
    if not '2015-01-01'<=published<='2026-10-30':
        raise ValueError('Publication outside the research interval')
    if not row.get('evidence_url') or not row.get('date_evidence'):
        raise ValueError('Observed URL and publication date evidence required')
    title=row['title'].strip()
    return Document(source['id'],url,title,published,'',row.get('language','und'),source['name'],
        author=row.get('author'),source_type='secondary',content_policy='metadata_only',
        content_sha256=fingerprint(source['id'],url,title,published),fingerprint_kind='metadata_identity',
        country_scope=source['country'],rights='Bibliographic reference only; article/quote reuse not licensed',
        translation_note='Publication language is not evidence of the original language of a speech')

def parse_rss(xml, source, evidence_url):
    """Ignore descriptions/content and channel author (not an article byline)."""
    if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise ValueError('XML declarations with entities are prohibited')
    root=ET.fromstring(xml)
    if root.tag!='rss':raise ValueError('Expected RSS, not an HTML error page')
    rows=[]
    for item in root.findall('./channel/item'):
        title=item.findtext('title','').strip();url=item.findtext('link','').strip()
        stamp=item.findtext('pubDate','').strip()
        if not title or not url or not stamp:continue
        # Publisher-local calendar day; do not convert into a speech date.
        published=parsedate_to_datetime(stamp).date().isoformat()
        row=dict(url=url,title=title,published_date=published,language='en',author=None,
                 evidence_url=evidence_url,date_evidence='RSS pubDate: '+stamp,channel='official_rss')
        metadata_document(row,source)
        rows.append(row)
    return rows
