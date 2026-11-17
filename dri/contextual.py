"""DRI v0.2: bounded predicate/argument evidence, categorical abstention, no LLM."""
import re
from bisect import bisect_left
from .tokenization import prepare, sentence_spans
from .rhetoric import COUNTERPART, THIRD, REPORTED, quoted_spans

GUARDS={
 'en':dict(negation=r"\b(?:not|never|no|don't|doesn't|didn't|cannot|won't|without)\b",
           hypothetical=r'\b(?:if|could|might|would|whether)\b',
           historical=r'\b(?:in (?:18|19)\d\d|during the war|at that time|in those days)\b',
           procedural=r'\b(?:order of business|time has expired|yield the floor)\b',
           foreign_subject=r'^\s*(?:\d+[.]?\s*)?(?:Japan|the Japanese government|South Korea|the ROK government)\s+(?:strongly )?(?:protests?|condemns?|demands?|urges?)\b',
           anaphora=r'^\s*(?:these|those|such) (?:actions|measures|restrictions)',
           disaster=r'earthquake|tsunami|natural disaster'),
 'ko':dict(negation=r'않(?:다|는|습|았|겠)|아니(?:다|라|라고|며)|못(?:하|합|했)|할수없|하지말',
           hypothetical=r'만약|라면|경우에는|것인지|어떻게생각|어떤생각',
           historical=r'(?:18|19)\d{2}년|식민지시대|당시에는',
           procedural=r'발언시간.*(?:종료|초과)|질의를마치|의사진행|산회를선포',
           foreign_subject=r'^(?:일본|한국|대한민국)(?:정부)?(?:은|는|이|가).{0,8}(?:항의|규탄|요구|촉구)',
           anaphora=r'^(?:이|그|이러한|그러한|이미취해진)(?:조치|정책|규제)',
           disaster=r'지진|쓰나미|자연재해'),
 'ja':dict(negation=r'抗議しない|非難しない|要求しない|強化しない|必要はない|ではない|とは思わない|とは考えない|べきではない|ませんでした',
           hypothetical=r'仮に|ならば|かもしれ|でしょうか|ですか|ますか',
           historical=r'(?:18|19)\d{2}年|当時は|戦時中',
           procedural=r'質問を終わ|時間が参|議事進行|散会',
           foreign_subject=r'^(?:韓国|日本)(?:政府)?(?:は|が)(?:強く|厳重に)?(?:抗議|非難|要求)',
           anaphora=r'^(?:こうした|これらの|その)(?:措置|政策|行動)',
           disaster=r'地震|津波|自然災害')}

def compact_view(text, language):
    """Remove CJK PDF hard-wrap spaces for rules, retaining an exact offset map."""
    positions=[i for i,c in enumerate(text) if language=='en' or not c.isspace()]
    return ''.join(text[i] for i in positions),positions

def spans_overlap(a,b,c,d):return a<d and c<b

def uncertain_quote_spans(text):
    """Only the affected interval of a truncated quote, not every prior sentence."""
    pairs={'“':'”','「':'」','『':'』','"':'"','‘':'’'};stack=[];uncertain=[]
    for i,c in enumerate(text):
        if stack and c==stack[-1][1]:stack.pop()
        elif c in pairs:stack.append((i,pairs[c]))
        elif c in {'”','」','』'}:uncertain.append((0,i+1))
    uncertain.extend((start,len(text)) for start,_ in stack)
    return uncertain

class ContextClassifier:
    def __init__(self, rules):
        self.rules={lang:[] for lang in GUARDS}
        for r in rules['rules']:
            if r['direction'] not in {'confrontational','neutral','cooperative'}:raise ValueError('Unknown direction')
            if r['intensity'] not in range(4) or (r['direction']!='confrontational' and r['intensity']!=0):raise ValueError('Invalid intensity')
            pattern=re.compile(r['pattern'],re.I)
            if 'act' not in pattern.groupindex:raise ValueError('Rule must identify a predicate')
            self.rules[r['language']].append((r,pattern))

    def classify(self, unit):
        lang=unit['language'];guards=GUARDS.get(lang)
        evidence=[];flags=set();roles=set();unresolved=[]
        if not guards:return self.finish(unit,[],[],['unsupported_language'],[])
        for fi,f in enumerate(unit['fragments']):
            text=prepare(f['text']);view,index=compact_view(text,lang);quoted=quoted_spans(text)
            uncertain_quotes=uncertain_quote_spans(text)
            if uncertain_quotes:flags.update(('unbalanced_quotation_context','quotation_present'))
            previous=None
            # Preserve source sentence boundaries BEFORE deleting CJK whitespace.
            # Otherwise Korean '. ' becomes '.다음' and poisons unrelated clauses.
            for source_a,source_b in sentence_spans(text):
                a,b=bisect_left(index,source_a),bisect_left(index,source_b)
                if a==b:continue
                clause=view[a:b]
                context={k:bool(re.search(guards[k],clause,re.I)) for k in ('negation','historical','procedural','hypothetical')}
                flags.update(k for k,v in context.items() if v)
                if quoted:flags.add('quotation_present')
                if context['historical']:roles.add('historical_context')
                if context['procedural']:roles.add('procedural')
                extra_reports={'en':r'\b(?:he|she|they) (?:emphasized|announced|welcomed)\b',
                    'ko':r'의견을같이했|공감했|설명했|언급했|당부했|말했습니다',
                    'ja':r'と発言|と説明|と指摘'}
                reported=bool(re.search(REPORTED[lang]+'|'+extra_reports[lang],clause,re.I))
                # Official recounting is evidence about the speaker's reported position,
                # not a new utterance of that politician. Institutional briefings can
                # still contain their own explicitly attributable evaluations.
                if reported:
                    flags.add('reported_position_present');roles.add('reported_position')
                    if unit.get('source_type')=='primary':roles.add('official_recount')
                    elif unit.get('source_type')=='secondary':roles.add('journalistic_recount')
                for rule,pattern in self.rules[lang]:
                    for match in pattern.finditer(clause):
                        x,y=match.span('act');start,end=a+x,a+y
                        source_start=index[a+match.start()];source_end=index[a+match.end()-1]+1
                        act_start=index[start];act_end=index[end-1]+1
                        reason=None;inherited=False
                        anchors=list(re.finditer(COUNTERPART[(lang,unit['target_country'])],clause,re.I))
                        if not anchors:
                            # Anaphora is restricted to one adjacent sentence in the
                            # same attributed fragment; never cross speakers/turns.
                            inherited=bool(rule.get('inherit_target') and previous
                                and re.search(guards['anaphora'],clause,re.I)
                                and re.search(COUNTERPART[(lang,unit['target_country'])],previous,re.I)
                                and not re.search(THIRD[lang],previous,re.I)
                                and not re.search(REPORTED[lang],previous,re.I))
                            if not inherited:reason='unresolved_counterpart'
                        if any(spans_overlap(act_start,act_end,q1,q2) for q1,q2 in quoted):
                            reason='quoted_position';roles.add('quoted_other_or_ambiguous_position')
                        if any(spans_overlap(source_start,source_end,q1,q2) for q1,q2 in uncertain_quotes):
                            reason='incomplete_quotation_scope';roles.add('quoted_other_or_ambiguous_position')
                        # Local predicate scope: negation elsewhere in a long sentence
                        # is not a global veto. Unhandled scope conservatively abstains.
                        near=clause[max(0,x-(45 if lang=='en' else 14)):min(len(clause),y+(45 if lang=='en' else 14))]
                        if re.search(guards['negation'],near,re.I):reason='negation_scope_needs_review'
                        if context['hypothetical'] or re.search(r'[?？]',clause):reason='hypothetical_or_question'
                        if context['procedural']:reason='procedural_turn'
                        if context['historical']:reason='historical_ownership_needs_review'
                        if reported:reason='reported_ownership_needs_review'
                        if lang=='en' and rule['id'] in {'en_protest','en_demand','en_concern'}:
                            owner=clause[:x]
                            if not re.search(r'\b(?:we|I|our government|(?:the )?ROK government|(?:the )?Japanese government|(?:the )?government of (?:the )?Republic of Korea)\b.{0,85}$',owner,re.I):
                                reason='no_explicit_owned_subject_for_performative'
                        foreign=re.search(guards['foreign_subject'],clause,re.I)
                        if foreign:
                            actor=foreign[0]
                            target_actor=bool(re.search(COUNTERPART[(lang,unit['target_country'])],actor,re.I))
                            if target_actor:reason='counterpart_as_speaking_actor'
                        thirds=list(re.finditer(THIRD[lang],clause,re.I))
                        if thirds:
                            flags.add('third_country_present')
                            # Bilateral cooperation on third-country security is not
                            # hostility to that country; retain an explicit dyad frame.
                            if rule['direction']=='confrontational':
                                def distance(m):return max(m.start()-y,x-m.end(),0)
                                if not anchors or min(map(distance,thirds))<=min(map(distance,anchors)):
                                    reason='competing_target_near_predicate'
                        if rule['id'].endswith('concern') or rule['id'] in {'ko_criticism','ja_unacceptable'}:
                            if re.search(guards['disaster'],clause,re.I):reason='humanitarian_context'
                        record={'rule_id':rule['id'],'direction':rule['direction'],'intensity':rule['intensity'],
                            'fragment_index':fi,'source_ref':f['ref'],'char_start':source_start,'char_end':source_end,
                            'predicate_start':act_start,'predicate_end':act_end,'inherited_target':inherited,
                            'decision':'abstained' if reason else 'supported','reason':reason}
                        evidence.append(record)
                        if reason:unresolved.append(reason)
                        else:roles.add('owned_explicit_position')
                previous=clause
        return self.finish(unit,evidence,sorted(flags),unresolved,sorted(roles))

    def finish(self,unit,evidence,flags,unresolved,roles):
        supported=[e for e in evidence if e['decision']=='supported']
        directions={e['direction'] for e in supported}
        conflict='confrontational' in directions;cooperative='cooperative' in directions
        if unit.get('exclusion_reason'):
            direction='undetermined';intensity=None;status='excluded';reason=unit['exclusion_reason']
        elif conflict and cooperative:
            direction='undetermined';intensity=None;status='needs_review';reason='mixed_owned_positions'
        elif supported:
            # Different quotation blocks remain ONE unit, regardless of hit count.
            direction='confrontational' if conflict else 'cooperative' if cooperative else 'neutral'
            intensity=max(e['intensity'] for e in supported);status='rule_supported';reason='explicit_predicate_and_target_frame'
            # A suppressed competing stance could change the whole-unit assessment.
            if any(e['decision']=='abstained' and e['direction']!=direction for e in evidence):
                direction='undetermined';intensity=None;status='needs_review';reason='unresolved_competing_position'
        else:
            direction='undetermined';intensity=None;status='needs_review';reason=sorted(set(unresolved))[0] if unresolved else 'no_sufficient_owned_context_frame'
        return {'direction':direction,'intensity':intensity,'classification_status':status,
            'confidence':'bounded_rule_support_not_calibrated' if status=='rule_supported' else 'insufficient_or_ambiguous',
            'classification_reason':reason,'context_flags':flags,'discourse_roles':roles,
            'negation_present':'negation' in flags,'quotation_present':'quotation_present' in flags,
            'historical_context_present':'historical' in flags,
            'evidence':evidence,'expert_validation':False}
