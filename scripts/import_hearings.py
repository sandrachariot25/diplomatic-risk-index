"""Import only session-model reviewed turns, preserving the frozen prediction corpus."""
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dri.paths import ROOT
from dri.storage import Store
from dri.repository import ingest, start_run, queue_item, finish_run
from dri.models import Document
from dri.statements import Statement, Quote
from scripts.annotate_llm_pilot import data

REASONS = {
 'neutral':'Обсуждение двустороннего вопроса без собственного конфронтационного требования; внутренняя критика и пересказ не перенесены на Японию.',
 'cooperative':'Текст содержит поддержку сотрудничества, диалога или конструктивного решения двустороннего вопроса; атрибуция позиции указана отдельно.',
 'confrontational':'В тексте есть собственная критика японских действий либо требование противодействия; интенсивность оценена по смыслу, а не наличию слов.',
 'mixed':'Одновременно выражены конфронтационная позиция и готовность к сотрудничеству.'}

def main():
    before_units,before_labels=data()
    candidates={r['review_id']:r for r in map(json.loads,(ROOT/'data/kr_hearings_review.jsonl').read_text(encoding='utf-8').splitlines())}
    with (ROOT/'config/kr_hearings_semantic_review.tsv').open(encoding='utf-8') as f:
        reviews=list(csv.DictReader(f,delimiter='\t'))
    output=ROOT/'data/kr_hearings_annotations.jsonl'
    old=[json.loads(l) for l in output.read_text(encoding='utf-8').splitlines()] if output.exists() else []
    annotated={r['unit_id']:r for r in old}
    store=Store()
    run=start_run(store,'kr-hearings-v10.3-reviewed-1',{'release':'v10.3','review_file':'config/kr_hearings_semantic_review.tsv'},resume=True)
    counts=Counter()
    for review in reviews:
        if review['direction']=='uncertain':continue
        r=candidates[int(review['review_id'])]
        key=f"kr-hearings:v10.3:{r['conf_num']}:{r['turn_seq']}"
        url=f"https://record.assembly.go.kr/assembly/viewer/minutes/xml.do?id={r['conf_num']}&type=view"
        meeting=r['meeting']
        evidence={'release':'v10.3','repository':'https://github.com/kyusik-yang/kr-hearings-data',
                  'conf_num':r['conf_num'],'conf_id':meeting['conf_id'],'turn_seq':r['turn_seq'],
                  'original_source':r['source'],'raw_minutes_sha1':meeting['raw_sha1'],
                  'date_basis':'speech_date_proxy','publication_date_confirmed':False,
                  'full_meeting':False,'complete_dataset_turn':True,'review_id':r['review_id'],
                  'party_uncertain':r['party_uncertain'],'role_group':r['role_group'],
                  'committee':meeting['committee_raw'],'hearing_type':meeting['hearing_type'],
                  'annotation_file':'data/kr_hearings_annotations.jsonl','expansion_only':True}
        institution='National Assembly, Republic of Korea' if r['role_group']=='legislator' else (r['speaker_pos'] or 'Parliamentary hearing participant, Republic of Korea')
        st=Statement(event_key=key,country='ROK',target_country='JPN',institution=institution,
                     context=meeting['title'],published_date=None,spoken_date=r['speech_date'],
                     speaker_name=r['speaker_name'],speaker_office=r['speaker_pos'],
                     addressee='Parliamentary participants; Japan is the substantive topic',
                     original_language='ko',verification_status='dataset_text_semantically_reviewed',
                     attribution_confidence='medium',attribution_evidence='Printed speaker metadata from kr-hearings v10.3; semantic review by Codex, not independent expert verification or new official transcript comparison.',
                     quotes=(Quote(r['text'],'ko','ko','published_version',key),),
                     institution_type=('parliament' if r['role_group']=='legislator' else
                                       'other' if r['role_group']=='excluded' else
                                       'unknown' if r['speaker_pos']=='증인' else 'government'),
                     speaker_role=r['speaker_pos'],political_affiliation=r['party'] if not r['party_uncertain'] else None,
                     statement_context='parliamentary_debate',position_scope='individual_position',
                     metadata_evidence=json.dumps(evidence,ensure_ascii=False))
        doc=Document(source='assembly_kr',url=url,title=meeting['title']+f" — turn {r['turn_seq']}",
                     published_date=None,event_date=r['speech_date'],text=r['text'],language='ko',
                     publisher='National Assembly Secretariat; research transcription by Kyusik Yang',
                     author=r['speaker_name'],author_role=r['speaker_pos'],
                     rights='Yang, Kyusik (2026), kr-hearings-data v10.3, CC BY 4.0. Internal DRI research corpus.',
                     content_policy='internal_research_only',official_identifier=key,
                     related_countries=('ROK','JPN'),country_scope='ROK',
                     observation_type='parliamentary_turn',text_completeness='complete_dataset_speaker_turn',
                     analysis_status='expansion_excluded_from_frozen_prediction',
                     verification_status='research_transcription_semantically_reviewed',
                     institution=institution,research_metadata=evidence)
        item=queue_item(store,run,'assembly_kr',url+'#'+str(r['turn_seq']))
        outcome=ingest(store,doc,statements=[st],run_id=run,item_key=item)
        counts.update({k:outcome[k] for k in ('documents_added','statements_added','quotes_added')})
        sid=store.db.execute('SELECT id FROM statements WHERE identity_key=?',(st.key,)).fetchone()[0]
        label=dict(unit_id=key,statement_ids=[sid],document_ids=[outcome['document_id']],
                   date=r['speech_date'],country='ROK',institution=institution,institution_type=st.institution_type,
                   speaker=r['speaker_name'],meeting_id=r['conf_num'],turn_seq=r['turn_seq'],
                   input_text_sha256=hashlib.sha256(r['text'].encode()).hexdigest(),
                   direction=review['direction'],confrontation_intensity=int(review['intensity']),
                   cooperation_present=review['direction'] in {'cooperative','mixed'},
                   target_country='JPN',position_ownership=review['ownership'],confidence='medium',
                   summary_ru=review['summary_ru'],reason_ru=REASONS[review['direction']],
                   annotation_method='codex_contextual_model',annotation_version='DRI-LLM-pilot-1',
                   model_id='gpt-6-astra',source_url=url,availability_basis='speech_date_proxy',
                   published_date=None,review_id=r['review_id'],
                   analysis_eligible=r['role_group']!='excluded')
        if key in annotated:
            previous=annotated[key]
            for field in ('direction','confrontation_intensity','summary_ru','input_text_sha256'):
                if previous[field]!=label[field]:raise ValueError('Conflicting semantic annotation')
        with store.db:
            store.db.execute('UPDATE statement_metadata SET institution_type=? WHERE statement_id=?', (st.institution_type,sid))
        annotated[key]=label
        tmp=output.with_suffix('.tmp')
        tmp.write_text(''.join(json.dumps(v,ensure_ascii=False,sort_keys=True)+'\n' for v in annotated.values()),encoding='utf-8')
        tmp.replace(output)
        replay=ingest(store,doc,statements=[st])
        assert not any(replay[k] for k in ('documents_added','statements_added','quotes_added'))
    finish_run(store,run)
    store.db.close()
    assert data()==(before_units,before_labels),'Frozen analytical units changed'
    print(json.dumps({'added':counts,'annotated':len(annotated),'years':Counter(r['date'][:4] for r in annotated.values()),'categories':Counter(r['direction'] for r in annotated.values())},ensure_ascii=False))

if __name__=='__main__':main()
