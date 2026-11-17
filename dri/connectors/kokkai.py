"""Official documented NDL speech API. No invented publication dates or translations."""
import json
import hashlib
import re
from datetime import date
from urllib.parse import urlencode, urlsplit
from ..models import Document
from ..statements import Statement,Quote
from ..identity import fingerprint, normalized

class Kokkai:
    source='kokkai_jp'
    host='kokkai.ndl.go.jp'
    endpoint='https://kokkai.ndl.go.jp/api/speech'

    def request_url(self,year,limit=20,query='韓国',speaker_position=None):
        if not 2015<=year<=2026 or not 1<=limit<=100:raise ValueError('Outside bounded pilot')
        parameters={'any':query,'from':f'{year}-01-01',
          'until':f'{year}-12-31' if year<2026 else '2026-10-31','maximumRecords':limit,'recordPacking':'json'}
        if speaker_position:parameters['speakerPosition']=speaker_position
        return self.endpoint+'?'+urlencode(parameters)

    def parse(self,body,focus_theme=None,*,start='2015-01-01',end='2026-10-31'):
        obj=json.loads(body)
        if not isinstance(obj.get('speechRecord'),list):
            if obj.get('numberOfRecords')==0:return []
            raise ValueError('Missing official speechRecord list')
        results=[]
        for item in obj['speechRecord']:
            speech=item.get('speech','')
            if not re.search(r'日韓|日中韓|韓国との|韓国政府|韓国側|対韓|竹島|慰安婦|徴用|韓国に|韓国が|韓国の',speech):continue
            spoken=item.get('date');date.fromisoformat(spoken)
            if not start<=spoken<=end:continue
            sid=item['speechID'];url=item['speechURL']
            if urlsplit(url).hostname!=self.host:raise ValueError('Unexpected speech URL host')
            name=item.get('speaker');office=item.get('speakerPosition')
            if not name:continue
            # A short contiguous original-language excerpt containing the target reference.
            match=re.search(r'日韓|韓国',speech)
            if focus_theme=='normalization_deescalation':
                match=re.search(r'(?:日韓|韓国).{0,35}(?:改善|正常化)|(?:改善|正常化).{0,35}(?:日韓|韓国)',speech,re.S)
                if not match:continue
            elif focus_theme=='regional_cooperation':
                match=re.search(r'日中韓',speech)
                if not match:continue
            if match is None:continue
            offset=max(0,match.start()-25)
            excerpt=speech[offset:offset+90]
            context=f"{item.get('nameOfHouse','')} {item.get('nameOfMeeting','')} {item.get('issueID','')} speech {sid}"
            doc=Document(self.source,url,context,None,excerpt,'ja','National Diet Library, Japan',author=name,
               author_role=office,rights='NDL API terms; individual speaker rights retained; short research excerpt only',
               content_policy='excerpt_only',official_identifier=sid,content_sha256=hashlib.sha256(normalized(speech).encode('utf-8')).hexdigest(),
               legacy_content_fingerprint=fingerprint(speech),
               related_countries=('JPN','ROK'),event_date=spoken)
            theme='security' if any(t in speech for t in ('北朝鮮','ミサイル','安全保障')) else 'diplomatic_contacts'
            for category,terms in [('territorial_disputes',('竹島','領土')),('historical_disputes',('慰安婦','徴用','歴史')),('trade_economy',('輸出','貿易','経済')),
                                   ('normalization_deescalation',('関係改善','国交正常化')),('regional_cooperation',('日中韓',))]:
                if any(t in excerpt for t in terms):theme=category;break
            if focus_theme:theme=focus_theme
            statement=Statement('kokkai:'+sid,'JPN','ROK',item.get('nameOfHouse','National Diet of Japan'),context,None,
                spoken_date=spoken,speaker_name=name,speaker_office=office,addressee='Republic of Korea (topic, not necessarily direct recipient)',
                theme=theme,original_language='ja',verification_status='needs_review',attribution_confidence='high',
                attribution_evidence='Official NDL speechID, dated meeting and speaker; role retained if supplied by API, otherwise unknown; relevance and interpretation require human review.',
                political_affiliation=item.get('speakerGroup') or None,
                metadata_evidence=('NDL speakerGroup as reported (parliamentary group, not inferred party or ruling status): '+url) if item.get('speakerGroup') else None,
                statement_context='parliamentary_debate',
                third_country_context=any(t in excerpt for t in ('北朝鮮','中国','米国')),
                quotes=(Quote(excerpt,'ja','ja','original_excerpt','speechID='+sid+f'; character_offset={offset}'),))
            doc.validate();statement.validate()
            results.append((doc,statement))
        return results
