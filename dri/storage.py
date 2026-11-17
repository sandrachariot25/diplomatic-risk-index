import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from .paths import DATA, inside, write_generated
from .migrations import upgrade
from .identity import normalize_url, official_id

def now():
    return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, directory=None, *, memory=False):
        self.root = inside(directory or DATA)
        self.root.mkdir(parents=True, exist_ok=True)
        if not memory and self.root != DATA:
            raise ValueError('Only the existing data/dri.sqlite3 may be used; tests must use memory=True')
        self.db = sqlite3.connect(':memory:' if memory else self.root / 'dri.sqlite3')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
          id INTEGER PRIMARY KEY, source TEXT NOT NULL, url TEXT NOT NULL,
          text_sha256 TEXT NOT NULL, metadata_json TEXT NOT NULL,
          text TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(source, text_sha256));
        CREATE TABLE IF NOT EXISTS observations (
          id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
          url TEXT NOT NULL, raw_path TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
          fetched_at TEXT NOT NULL, UNIQUE(document_id,url,raw_sha256));
        CREATE TABLE IF NOT EXISTS fetches (
          id INTEGER PRIMARY KEY, url TEXT NOT NULL, fetched_at TEXT NOT NULL,
          status INTEGER, headers_json TEXT, raw_path TEXT, sha256 TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS errors (
          id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, source TEXT,
          url TEXT, stage TEXT NOT NULL, message TEXT NOT NULL);
        ''')
        upgrade(self.db, self.root)

    def record_fetch(self, url, status, headers, body, error=None, *, retain_body=True):
        digest = hashlib.sha256(body).hexdigest()
        path = Path('raw') / digest[:2] / (digest + '.bin')
        target = self.root / path
        if retain_body:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError('Existing raw file hash mismatch; refusing overwrite')
            if not target.exists():
                target.write_bytes(body)
        else:
            path = None
        stamp = now()
        with self.db:
            self.db.execute('INSERT INTO fetches(url,fetched_at,status,headers_json,raw_path,sha256,error) VALUES(?,?,?,?,?,?,?)',
                            (url, stamp, status, json.dumps(headers, ensure_ascii=False), path.as_posix() if path else None, digest, error))
        return path.as_posix() if path else '', digest, stamp

    def save(self, doc, raw_ref):
        doc.validate()
        with self.db:
            doc_id, inserted = self._save(doc, raw_ref)
        return inserted

    def _save(self, doc, raw_ref):
        doc.validate()
        url = normalize_url(doc.url)
        oid = doc.official_identifier or official_id(url)
        if not self.db.execute('SELECT 1 FROM sources WHERE id=?', (doc.source,)).fetchone():
            raise ValueError('Register source and its policy before ingestion')
        existing = self.db.execute('''SELECT id FROM documents WHERE source=? AND
          coalesce(published_date,json_extract(metadata_json,'$.event_date')) IS ? AND text_sha256=?
          AND (? != 'kokkai_jp' OR official_id IS ?)
          ORDER BY canonical_url=? DESC LIMIT 1''', (doc.source, doc.published_date or doc.event_date, doc.text_sha256, doc.source, oid, url)).fetchone()
        # Same URL or official id + date + content identifies a revision; different content is retained.
        inserted = existing is None
        if inserted:
            cur = self.db.execute('''INSERT INTO documents(source,url,text_sha256,metadata_json,text,created_at,
                canonical_url,official_id,published_date,language,source_type,content_policy) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (doc.source, url, doc.text_sha256, json.dumps(asdict(doc), ensure_ascii=False), doc.text, now(),
                 url, oid, doc.published_date, doc.language, doc.source_type, doc.content_policy))
            doc_id = cur.lastrowid
        else:
            doc_id = existing[0]
        self.db.execute('INSERT OR IGNORE INTO document_aliases VALUES(?,?,?)', (doc.source, url, doc_id))
        if raw_ref:
            self.db.execute('INSERT OR IGNORE INTO observations(document_id,url,raw_path,raw_sha256,fetched_at) VALUES(?,?,?,?,?)',
                            (doc_id, url, *raw_ref))
        return doc_id, inserted

    def error(self, source, url, stage, error):
        message = f'{type(error).__name__}: {error}'
        with self.db:
            self.db.execute('INSERT INTO errors(created_at,source,url,stage,message) VALUES(?,?,?,?,?)', (now(), source, url, stage, message))
        with (self.root / 'errors.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(at=now(), source=source, url=url, stage=stage, message=message), ensure_ascii=False) + '\n')

    def export(self):
        rows = self.db.execute('SELECT id, metadata_json FROM documents ORDER BY id').fetchall()
        lines=[]
        for doc_id, metadata in rows:
            obj = json.loads(metadata)
            from .publication import internal_document
            private=internal_document(obj)
            if private:
                obj['text']=''
                obj['export_text_status']='withheld_internal_research_only'
                if obj.get('research_metadata'):
                    allowed={'parser','pdf_sha256','conf_id','confer_num','pages','complete_reviewed_turns','floor_speaker_records','ocr_used'}
                    obj['research_metadata']={k:v for k,v in obj['research_metadata'].items() if k in allowed}
            obj['id'] = doc_id
            obj['observations'] = [dict(url=r[0], raw_path=r[1], raw_sha256=r[2], fetched_at=r[3]) for r in self.db.execute('SELECT url,raw_path,raw_sha256,fetched_at FROM observations WHERE document_id=?', (doc_id,))]
            if private:
                for observation in obj['observations']:observation['raw_path']=None
            lines.append(json.dumps(obj, ensure_ascii=False))
        write_generated(self.root / 'corpus.jsonl','\n'.join(lines)+('\n' if lines else ''))
