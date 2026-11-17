import re
from datetime import datetime
from urllib.parse import urlsplit, urljoin
from ..html import Tree, clean, one
from ..models import Document

class JapanMOFA:
    """Parser awaiting live HTML validation: current host rejects direct access (403)."""
    source = 'mofa_jp'
    host = 'www.mofa.go.jp'
    index_url = 'https://www.mofa.go.jp/region/asia-paci/korea/archives.html'

    def canonical(self, url):
        p = urlsplit(url)
        if p.scheme != 'https' or p.netloc != self.host or not p.path.endswith('.html'):
            raise ValueError('Not an approved Japanese MOFA document URL')
        return 'https://' + self.host + p.path

    def discover(self, html, base_url=None):
        result = []
        for a in Tree(html).root.find('a'):
            if not re.search(r'Japan.?ROK|Japan.{0,4}Republic of Korea', a.text(), re.I):
                continue
            try:
                url = self.canonical(urljoin(base_url or self.index_url, a.attrs.get('href', '')))
            except ValueError:
                continue
            if url != self.index_url and url not in result:
                result.append(url)
        return result

    def parse(self, html, url):
        root = Tree(html).root
        main = one(root.find(id='main'), 'main (unverified live selector)')
        title = clean(one(main.find('h2'), 'document h2').text())
        contents = one(main.find(cls='contents'), 'contents (unverified live selector)')
        body = clean(contents.text())
        dates = re.findall(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\b', main.text())
        if not dates:
            raise ValueError('Publication date missing')
        date = datetime.strptime(dates[0], '%B %d, %Y').date().isoformat()
        doc = Document(self.source, self.canonical(url), title, date, body, 'en',
                       'Ministry of Foreign Affairs of Japan', rights='PDL 1.0, subject to page-specific and third-party exceptions; cite URL and access date')
        doc.validate()
        return doc
