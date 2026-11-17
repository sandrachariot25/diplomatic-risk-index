import re
from urllib.parse import urljoin, urlsplit, parse_qs, urlencode
from ..html import Tree, clean, one
from ..models import Document

class KoreaMOFA:
    source = 'mofa_kr'
    host = 'www.mofa.go.kr'
    index_url = 'https://www.mofa.go.kr/eng/brd/m_5676/list.do'

    def canonical(self, url):
        parts = urlsplit(url)
        seq = parse_qs(parts.query).get('seq', [''])[0]
        if (parts.scheme != 'https' or parts.netloc != self.host
                or parts.path not in {'/eng/brd/m_5676/view.do', '/www/brd/4080/view.do', '/www/brd/m_4080/view.do'}
                or not seq.isdigit()):
            raise ValueError('Not an approved Korean MOFA document URL')
        return 'https://' + self.host + parts.path + '?' + urlencode({'seq': seq})

    def discover(self, html, base_url=None):
        result = []
        for a in Tree(html).root.find('a'):
            href = urljoin(base_url or self.index_url, a.attrs.get('href', ''))
            try:
                url = self.canonical(href)
            except ValueError:
                continue
            if re.search(r'Japan|Japanese', a.text(), re.I) and url not in result:
                result.append(url)
        return result

    def parse(self, html, url):
        root = Tree(html).root
        detail = one(root.find(cls='board_detail'), 'board_detail')
        head = one(detail.find(cls='bo_head'), 'bo_head')
        title = clean(one(head.find('h2'), 'document title').text())
        date = re.search(r'\b\d{4}-\d{2}-\d{2}\b', head.text())
        if not date:
            raise ValueError('Publication date missing')
        body = clean(one(detail.find(cls='bo_con'), 'bo_con').text())
        language = 'ko' if urlsplit(url).path.startswith('/www/') else 'en'
        doc = Document(self.source, self.canonical(url), title, date[0], body,
                       language, 'Ministry of Foreign Affairs, Republic of Korea',
                       author_role='MOFA Spokesperson' if 'Spokesperson' in title else None,
                       translation_note='unofficial translation' if 'unofficial translation' in body.lower() else None)
        doc.validate()
        return doc
