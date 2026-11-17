"""Current continuation only; no historical content audit or old-batch replay."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dri.storage import Store
from dri.models import Document
from dri.statements import Statement,Quote
from dri.repository import ingest
from dri.expansion_outputs import replace_section
from dri.paths import write_generated

def main():
 s=Store();d=s.db
 try:
  b=json.loads(d.execute("SELECT config_json FROM collection_runs WHERE run_key='continuation-2026-11-01-baseline'").fetchone()[0])
  tables=('documents','statements','quotes','statement_sources','quote_sources','duplicate_candidates')
  count=lambda:{t:d.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in tables}
  before=count();columns=('event_key','country','target_country','institution','context','published_date','spoken_date','speaker_name','speaker_office','addressee','theme','original_language','verification_status','attribution_confidence','attribution_evidence','third_country_context')
  docs=d.execute('SELECT id,metadata_json FROM documents WHERE id>?',(b['last_document_id'],)).fetchall()
  for did,meta in docs:
   sts=[]
   for row in d.execute('SELECT s.id,'+','.join('s.'+c for c in columns)+' FROM statements s JOIN statement_sources ss ON ss.statement_id=s.id WHERE ss.document_id=?',(did,)).fetchall():
    qs=d.execute('SELECT q.text,q.published_language,q.original_language,q.version_kind,qs.evidence_locator FROM quotes q JOIN quote_sources qs ON qs.quote_id=q.id WHERE q.statement_id=? AND qs.document_id=?',(row[0],did)).fetchall()
    sts.append(Statement(**dict(zip(columns,row[1:])),quotes=tuple(Quote(*q) for q in qs)))
   outcome=ingest(s,Document(**json.loads(meta)),statements=sts)
   assert outcome['documents_added']==outcome['statements_added']==outcome['quotes_added']==0
  after=count();assert before==after
  assert d.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
  assert not d.execute('PRAGMA foreign_key_check').fetchall()
  full=sum(json.loads(m).get('text_completeness')=='complete_published_body' for _,m in docs)
  dates=sum(bool(json.loads(m).get('event_date') or json.loads(m).get('published_date')) for _,m in docs)
  authors=sum(bool(json.loads(m).get('author')) for _,m in docs)
  years=d.execute("SELECT substr(coalesce(published_date,json_extract(metadata_json,'$.event_date')),1,4),source,count(*),sum(content_policy='full_text_permitted') FROM documents WHERE id>? GROUP BY 1,2",(b['last_document_id'],)).fetchall()
  remaining=d.execute('SELECT source_id,status,count(*) FROM discovery_results GROUP BY 1,2').fetchall()
  result=dict(before={k:b[k] for k in ('documents','statements','quotes')},after=after,new_documents=len(docs),full_texts=full,fragments=len(docs)-full,known_dates=dates,known_personal_authors=authors,years=years,remaining=remaining,repeat_passed=True,network_requests_in_verification=0)
  from dri.quality import report
  report(s)
  lines=['## Продолжение 1 ноября 2026: срез по 31.10.2026','',f'До: {b["documents"]} документов / {b["statements"]} реплик / {b["quotes"]} цитат. После: {after["documents"]} / {after["statements"]} / {after["quotes"]}.',f'Добавлено документов: {len(docs)}; полных текстов: {full}; коротких фрагментов: {len(docs)-full}. Новых реплик: {after["statements"]-b["statements"]}; новых цитат: {after["quotes"]-b["quotes"]}.',f'Известная дата события или публикации: {dates}/{len(docs)}; персональный автор: {authors}/{len(docs)}. Институциональный издатель не выдаётся за личного автора.', 'GDELT не расширялся: 22 Events / 28 Mentions / 60 GKG; эти типы не складываются с текстами.', 'Повторный импорт только текущего продолжения: прирост 0; SQLite integrity=ok, FK ошибок нет.', '', '| Год | Источник / страна | Документы | Полные | Фрагменты |','|---|---|---:|---:|---:|']
  for year in range(2015,2027):
   for src,country in [('mofa_kr','ROK'),('kokkai_jp','JPN')]:
    row=next((r for r in years if r[0]==str(year) and r[1]==src),None);n=row[2] if row else 0;f=row[3] if row else 0
    lines.append(f'| {year} | {src} / {country}, primary | {n} | {f} | {n-f} |')
  lines+=['','Состояния очереди: `'+json.dumps(remaining,ensure_ascii=False)+'`.','Полные тексты допускают частоты внутри этого документального подкорпуса. Короткие выбранные цитаты не заменяют полные речи; политическая интерпретация, адресат и нерешённые совпадения требуют проверки. Тональность, веса и индекс не рассчитывались.']
  text='\n'.join(lines)
  for file in ('QUALITY_REPORT.md','CHANGES.md'):
   p=ROOT/'docs'/file;old=p.read_text(encoding='utf-8');marker='<!-- CONTINUATION_20261101 -->'
   if marker in old:old=old.split(marker)[0]
   write_generated(p,old.rstrip()+'\n\n'+marker+'\n'+text+'\n')
  p=ROOT/'README.md';old=p.read_text(encoding='utf-8');marker='<!-- CONTINUATION_20261101 -->'
  if marker in old:old=old.split(marker)[0]
  write_generated(p,old.rstrip()+'\n\n'+marker+'\n'+text.split('| Год')[0]+'\nКоманды продолжения прежние; используется существующая схема 4. Текущий отчёт: docs/QUALITY_REPORT.md. Изменены коннектор Kokkai, граничная дата expansion.py и добавлен scripts/report_continuation.py; обновлены существующие отчёты и единственная выгрузка.\n')
  p=ROOT/'data/verification.json';v=json.loads(p.read_text(encoding='utf-8'));v['continuation_20261101']=result;write_generated(p,json.dumps(v,ensure_ascii=False,indent=2)+'\n');s.export();print(json.dumps(result))
 finally:d.close()
if __name__=='__main__':main()
