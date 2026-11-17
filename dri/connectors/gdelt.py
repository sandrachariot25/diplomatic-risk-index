"""Documented discovery API only. It does not provide article full text or event truth."""
import json
from urllib.parse import urlencode
from ..identity import normalize_url

class GDELTDiscovery:
    endpoint='https://api.gdeltproject.org/api/v2/doc/doc'

    def request_url(self, query, timespan='1d', limit=25):
        if not 1<=limit<=250:raise ValueError('GDELT maxrecords must be 1..250')
        if timespan not in {'1d','1week','1month','3months'}:
            raise ValueError('Historical 2015–2026 retrieval is not supported by DOC')
        return self.endpoint+'?'+urlencode(dict(query=query,mode='artlist',format='json',timespan=timespan,maxrecords=limit))

    def parse(self, body, content_type):
        if 'json' not in content_type.lower():
            raise ValueError('GDELT returned non-JSON; may be throttling/error, not zero results')
        obj=json.loads(body)
        if not isinstance(obj,dict) or not isinstance(obj.get('articles'),list):
            raise ValueError('Missing GDELT article list')
        result=[]
        for item in obj['articles']:
            result.append({'url':normalize_url(item['url']),'title':item.get('title'),
                           'seen_at':item.get('seendate'),'publication_date':None,
                           'language':item.get('language'),'discovery_source':'gdelt'})
        return result
