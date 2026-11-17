"""Verified korea.kr speech/briefing HTML. No news-to-quote conversion."""
import re
from urllib.parse import urlsplit, parse_qs
from ..html import Tree, clean, one
from ..models import Document
from ..statements import Statement, Quote


def parse(html, url, record, *, restricted_research=False):
    p = urlsplit(url)
    if p.netloc != 'www.korea.kr' or p.path not in {
        '/briefing/speechView.do', '/briefing/presidentView.do'
    }:
        raise ValueError('Unverified government document route')
    tree = Tree(html)
    title = clean(one(tree.root.find('div', cls='view_title'), 'title').text())
    body_node = one(tree.root.find('div', cls='view_cont'), 'body')
    body = clean(body_node.text())
    if len(body) < 100 or any(body_node.find(tag) for tag in ('img', 'iframe', 'video')):
        raise ValueError('Insufficient text or mixed media requires manual review')
    licence = clean(one(tree.root.find('div', cls='kogl'), 'item licence').text())
    m = re.search(r'제\s*([1-4])\s*유형', licence)
    if not m or m[1] not in {'1', '4'}:
        raise ValueError('Item licence not approved for retention')
    restricted = m[1] == '4'
    if restricted and not restricted_research:
        raise ValueError('KOGL4 requires explicit restricted research authorization')
    infos = [clean(n.text()) for n in tree.root.find('div', cls='info')]
    speech = p.path.endswith('speechView.do')
    label = r'연설일\s*:\s*' if speech else r'^'
    dates = [re.search(label + r'(\d{4})\.(\d{2})\.(\d{2})', s) for s in infos]
    dates = [x for x in dates if x]
    if len(dates) != 1:
        raise ValueError('Ambiguous or missing labelled date')
    date = '-'.join(dates[0].groups())
    if not '2015-01-01' <= date <= '2026-10-31':
        raise ValueError('Outside corpus period')
    if not any(w in body for w in ('일본', '한일', '한·일')):
        raise ValueError('No verified Japan relevance')
    # Reviewed attribution must be literally supported by this page, never office history.
    evidence = title + '\n' + '\n'.join(infos) + '\n' + body
    for field in ('name', 'role'):
        if record.get(field) and record[field] not in evidence:
            raise ValueError('Attribution not present in source: ' + field)
    identifier = parse_qs(p.query)['newsId'][0]
    kind = 'official_speech' if speech else 'official_written_briefing'
    rights = ('KOGL Type ' + m[1] + '; attribution: 대한민국 정책브리핑, ' + title + ', ' + url
              + ('; NONCOMMERCIAL RESEARCH ONLY; no alterations or commercial reuse; media excluded'
                 if restricted else '; media excluded'))
    doc = Document(
        source='korea_government_kr', url=url, title=title,
        published_date=None if speech else date, event_date=date if speech else None,
        text=body, language='ko', publisher='대한민국 정책브리핑',
        author=record.get('name'), author_role=record['role'], rights=rights,
        content_policy='restricted_research_full_text' if restricted else 'full_text',
        official_identifier='korea.kr:' + identifier, related_countries=('ROK', 'JPN'),
        country_scope='ROK', observation_type=kind, text_completeness='complete_published_body',
        analysis_status='restricted_noncommercial_research_only' if restricted else 'text_frequency_candidate',
        verification_status='source_verified', institution=record['institution'],
        observation_addressee=record['addressee'], theme=record['theme'], rights_evidence=licence)
    # Each signed written briefing is its spokesperson's text, not a president's oral quote.
    st = Statement(
        event_key='official:korea.kr:' + identifier, country='ROK', target_country='JPN',
        institution=record['institution'], context=title, published_date=doc.published_date,
        spoken_date=date if speech else None, speaker_name=doc.author, speaker_office=record['role'],
        addressee=record['addressee'], theme=record['theme'], original_language='ko',
        verification_status='source_verified', attribution_confidence='high' if doc.author else 'medium',
        attribution_evidence='Page title / labelled speaker and date; written briefing is attributed to its spokesperson. '+record['evidence'],
        institution_type='head_of_state_administration', speaker_role=record['role'],
        statement_context='speech' if speech else 'written_briefing',
        position_scope='institutional_position',
        quotes=(Quote(body.split('\n')[0], 'ko', 'ko', locator='first paragraph; written text, not inferred oral quotation'),))
    return doc, (st,)
