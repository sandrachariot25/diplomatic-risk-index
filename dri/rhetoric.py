"""Auditable seed-lexicon matching with conservative contextual abstention.

These rules do not perform semantic sentiment or threat classification.
"""
import re
from .tokenization import prepare,sentence_spans

COUNTERPART={
    ('en','JPN'):r'\b(?:japan|japanese)\b',
    ('en','ROK'):r'\b(?:south korea|republic of korea|rok)\b',
    ('ko','JPN'):r'일본|한[·ㆍ․-]?일',
    ('ko','ROK'):r'대한민국|한국|한[·ㆍ․-]?일',
    ('ja','ROK'):r'大韓民国|韓国|日韓|日米韓',
    ('ja','JPN'):r'日本|日韓|日米韓',
}
THIRD={
    'en':r'\b(?:north korea|dprk|china|russia|united states|united nations)\b|\bU\.S\.',
    'ko':r'북한|북조선|중국|러시아|미국|유엔',
    'ja':r'北朝鮮|中国|ロシア|米国|アメリカ|国連',
}
REPORTED={
    'en':r'\b(?:said|stated|reported|according to|argued|claimed)\b',
    'ko':r'말했|말하|주장했|주장하|보도|에 따르면',
    'ja':r'述べ|主張|報道|によると|とのこと',
}
HYPOTHETICAL={
    'en':r'\b(?:if|would|could|might|may)\b',
    'ko':r'만약|경우|가정|수 있다',
    'ja':r'場合|仮に|ならば|かもしれ',
}

def quoted_spans(text):
    pairs={'“':'”','‘':'’','「':'」','『':'』','"':'"'};stack=[];spans=[]
    for i,c in enumerate(text):
        if stack and c==stack[-1][1]:
            start,_=stack.pop();spans.append((start,i+1))
        elif c in pairs:stack.append((i,pairs[c]))
    return spans

class Matcher:
    def __init__(self,lexicon,segmenter):
        self.segmenter=segmenter;self.patterns={k:[] for k in ('en','ko','ja')}
        for entry in lexicon['entries']:
            pattern=tuple(t.lemma for t in segmenter.tokenize(entry['expression'],entry['language'])
                          if t.content or (entry['language']=='ja' and t.lemma in {'ない','ぬ','ず'}))
            if not pattern:raise ValueError('Empty lexicon expression: '+entry['id'])
            self.patterns[entry['language']].append((pattern,entry))

    def match(self,text,language,target):
        text=prepare(text);tokens=self.segmenter.tokenize(text,language)
        content=[(i,t) for i,t in enumerate(tokens) if t.content or (language=='ja' and t.lemma in {'ない','ぬ','ず'})]
        candidates=[];spans=sentence_spans(text);quoted=quoted_spans(text)
        for pattern,entry in self.patterns[language]:
            for start in range(len(content)-len(pattern)+1):
                window=content[start:start+len(pattern)]
                if tuple(t.lemma for _,t in window)!=pattern:continue
                if window[0][1].sentence!=window[-1][1].sentence:continue
                i,a=window[0];j,b=window[-1];sentence=spans[a.sentence]
                reason=self.context(text,tokens,i,j,entry,language,target,sentence,quoted)
                candidates.append({'expression_id':entry['id'],'category':entry['category'],
                    'char_start':a.start,'char_end':b.end,'token_start':i,'token_end':j+1,
                    'sentence_start':sentence[0],'sentence_end':sentence[1],
                    'decision':'counted' if reason is None else 'suppressed','reason':reason,
                    'pattern_tokens':len(pattern)})
        # A phrase and its contained short form are one lexical occurrence.
        selected=[]
        for candidate in sorted(candidates,key=lambda m:(-(m['char_end']-m['char_start']),m['expression_id'],m['char_start'])):
            if any(candidate['char_start']<s['char_end'] and s['char_start']<candidate['char_end'] for s in selected):continue
            selected.append(candidate)
        return tokens,sorted(selected,key=lambda m:(m['char_start'],m['expression_id']))

    def context(self,text,tokens,i,j,entry,language,target,sentence,quoted):
        a=tokens[i].start;b=tokens[j].end;clause=text[sentence[0]:sentence[1]]
        if any(x<=a and b<=y for x,y in quoted):return 'quoted_position_or_scare_quote'
        anchors=list(re.finditer(COUNTERPART[(language,target)],clause,re.I))
        if not anchors:return 'counterpart_not_explicit_in_sentence'
        benign={'en':r'earthquake|tsunami|natural disaster',
                'ko':r'지진|쓰나미|자연재해','ja':r'地震|津波|自然災害'}
        if entry['category']=='negative_bilateral_actions' and re.search(benign[language],clause,re.I):
            return 'humanitarian_or_natural_disaster_context'
        # Avoid attributing sanctions/condemnation of DPRK or a third state to the dyad.
        if re.search(THIRD[language],clause,re.I):return 'competing_third_country_context'
        if re.search(REPORTED[language],clause,re.I):return 'reported_position_uncertain_ownership'
        if re.search(HYPOTHETICAL[language],clause,re.I) or re.search(r'[?？]',clause):return 'hypothetical_or_question'
        if entry['category']=='economic_restrictions' and entry['expression'] in {'export restrictions','수출 규제','輸出規制'}:
            evaluations={'en':r'unjust|unacceptable|regret|condemn|protest|retaliat|critic',
                         'ko':r'부당|유감|규탄|항의|비판|보복|불합리|우려',
                         'ja':r'不当|遺憾|非難|抗議|批判|報復|懸念'}
            if not re.search(evaluations[language],clause,re.I):return 'measure_description_without_explicit_negative_evaluation'
        # Outside-expression negation only: intrinsically negative lexical phrases
        # (e.g. 容認できない) retain their own negation as part of the expression.
        near=[t for n,t in enumerate(tokens) if max(0,i-5)<=n<=j+6 and not i<=n<=j and t.sentence==tokens[i].sentence]
        negatives={'en':{'not','never','no','without',"don't","doesn't","cannot","won't"},
                   'ko':{'않','못','아니','없','말'},'ja':{'ない','ぬ','ず','ません','無い','否定'}}
        if any(t.lemma in negatives[language] for t in near):return 'nearby_negation_scope_uncertain'
        if j+1<len(tokens):
            nxt=tokens[j+1]
            if nxt.start==b and nxt.lemma in {'법','안','론','집','문','자','法','案','論','者','集','書'}:
                return 'compound_extension_or_legal_title'
        prefix=text[sentence[0]:a]
        # Grammatical foreign subject is a warning of ownership inversion. Predicate
        # assessments such as 'Japan’s actions are unacceptable' are not this case.
        action=entry['category'] in {'diplomatic_condemnation','accusations_protests','termination_cooperation','threats_warnings'}
        if action:
            foreign_en=r'(?:Japan|The Japanese government)' if target=='JPN' else r'(?:South Korea|The ROK government|The government of the Republic of Korea)'
            if language=='en' and re.search(r'^\s*'+foreign_en+r'\s+(?:strongly\s+)?$',prefix,re.I):
                return 'counterpart_as_speaking_actor'
            foreign_ko=r'일본' if target=='JPN' else r'(?:한국|대한민국)'
            if language=='ko' and re.search(foreign_ko+r'(?:\s*정부)?(?:이|가|은|는)\s*$',prefix):
                return 'counterpart_as_speaking_actor'
            foreign_ja='韓国' if target=='ROK' else '日本'
            if language=='ja' and re.search(foreign_ja+r'(?:政府)?(?:は|が)\s*(?:強く|厳重に)?$',prefix):
                return 'counterpart_as_speaking_actor'
        return None
