"""One primary database; SQLite backup precedes any controlled schema upgrade."""
import sqlite3
from datetime import datetime, timezone
from .paths import inside

VERSION = 9

# Internal research store for complete Kokkai speeches (author decision 2026-11-10). Kept apart from
# documents/statements so the frozen v1 corpus and its hashes are untouched. Never exported:
# NDL api.html section 4 permits use without permission for political speeches and computational
# analysis; republication of full texts is not assumed.
KOKKAI_FULL_SCHEMA = """
CREATE TABLE kokkai_speeches_full (
 speech_id TEXT PRIMARY KEY, issue_id TEXT, spoken_date TEXT NOT NULL, name_of_house TEXT,
 name_of_meeting TEXT, issue TEXT, speech_order INTEGER, speaker TEXT, speaker_yomi TEXT,
 speaker_group TEXT, speaker_position TEXT, speaker_role TEXT, speech TEXT NOT NULL,
 speech_sha256 TEXT NOT NULL, speech_url TEXT NOT NULL, meeting_url TEXT, query TEXT NOT NULL,
 fetched_at TEXT NOT NULL, response_sha256 TEXT NOT NULL,
 content_policy TEXT NOT NULL DEFAULT 'restricted_research_full_text'
  CHECK(content_policy='restricted_research_full_text'),
 rights TEXT NOT NULL DEFAULT 'NDL api.html s.4: political speech / computational analysis use; internal only, not for publication');
CREATE INDEX kokkai_speeches_full_date ON kokkai_speeches_full(spoken_date);
CREATE TABLE kokkai_full_pages (
 query TEXT NOT NULL, year INTEGER NOT NULL, start_record INTEGER NOT NULL, fetched_at TEXT NOT NULL,
 number_of_records INTEGER NOT NULL, returned INTEGER NOT NULL, next_record INTEGER,
 response_sha256 TEXT NOT NULL, PRIMARY KEY(query, year, start_record));
"""

ECONOMY_NATIVE_SCHEMA = """
CREATE TABLE economic_trade_native (
  download_id INTEGER NOT NULL REFERENCES economic_downloads(id),
  period TEXT NOT NULL, reporter TEXT NOT NULL, partner TEXT NOT NULL,
  flow TEXT NOT NULL CHECK(flow IN ('M','X')),
  value_native INTEGER NOT NULL CHECK(value_native >= 0),
  currency TEXT NOT NULL, multiplier INTEGER NOT NULL,
  publication_date TEXT, revision_status TEXT NOT NULL,
  PRIMARY KEY(download_id,period,reporter,partner,flow)
) WITHOUT ROWID;
CREATE VIEW economic_trade_native_current AS
SELECT t.*, d.source, d.url, d.retrieved_at, d.sha256
FROM economic_trade_native t JOIN economic_downloads d ON d.id=t.download_id
WHERE NOT EXISTS (
 SELECT 1 FROM economic_downloads n WHERE n.logical_file=d.logical_file
 AND (n.retrieved_at,n.id)>(d.retrieved_at,d.id)
);
"""

ECONOMY_SCHEMA = """
CREATE TABLE economic_downloads (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL, logical_file TEXT NOT NULL, raw_path TEXT NOT NULL,
  url TEXT NOT NULL, retrieved_at TEXT NOT NULL, sha256 TEXT NOT NULL,
  UNIQUE(logical_file, retrieved_at)
);
CREATE TABLE economic_trade (
  download_id INTEGER NOT NULL REFERENCES economic_downloads(id),
  frequency TEXT NOT NULL CHECK(frequency IN ('M','A')),
  period TEXT NOT NULL, reporter TEXT NOT NULL, partner TEXT NOT NULL,
  flow TEXT NOT NULL CHECK(flow IN ('M','X')),
  classification TEXT NOT NULL, commodity TEXT NOT NULL,
  value_native TEXT NOT NULL, currency TEXT NOT NULL, multiplier INTEGER NOT NULL,
  value_usd REAL NOT NULL CHECK(value_usd >= 0),
  publication_date TEXT, revision_status TEXT NOT NULL, source_flags TEXT NOT NULL,
  PRIMARY KEY(download_id, period, reporter, partner, flow, classification, commodity)
) WITHOUT ROWID;
CREATE VIEW economic_trade_current AS
SELECT t.*, d.source, d.url, d.retrieved_at, d.sha256
FROM economic_trade t JOIN economic_downloads d ON d.id=t.download_id
WHERE NOT EXISTS (
 SELECT 1 FROM economic_downloads n WHERE n.logical_file=d.logical_file
 AND (n.retrieved_at,n.id)>(d.retrieved_at,d.id)
);
"""
SCHEMA = '''
CREATE TABLE sources (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT,
 source_type TEXT NOT NULL CHECK(source_type IN ('primary','secondary','discovery')),
 base_url TEXT NOT NULL, terms_url TEXT, access_status TEXT NOT NULL DEFAULT 'not_checked',
 content_policy TEXT NOT NULL DEFAULT 'metadata_only', audit_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE documents__migration (
 id INTEGER PRIMARY KEY, source TEXT NOT NULL REFERENCES sources(id), url TEXT NOT NULL,
 text_sha256 TEXT NOT NULL, metadata_json TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL,
 canonical_url TEXT NOT NULL, official_id TEXT, published_date TEXT, language TEXT,
 source_type TEXT NOT NULL DEFAULT 'primary', content_policy TEXT NOT NULL DEFAULT 'legacy_unreviewed',
 UNIQUE(source,canonical_url,text_sha256,published_date));
INSERT INTO sources(id,name,country,source_type,base_url)
 VALUES ('mofa_kr','Ministry of Foreign Affairs, Republic of Korea','ROK','primary','https://www.mofa.go.kr'),
 ('mofa_jp','Ministry of Foreign Affairs of Japan','JPN','primary','https://www.mofa.go.jp');
INSERT INTO documents__migration(id,source,url,text_sha256,metadata_json,text,created_at,canonical_url,published_date,language)
 SELECT id,source,url,text_sha256,metadata_json,text,created_at,url,
 json_extract(metadata_json,'$.published_date'),json_extract(metadata_json,'$.language') FROM documents;
DROP TABLE documents;
ALTER TABLE documents__migration RENAME TO documents;
CREATE INDEX documents_text_date ON documents(source,text_sha256,published_date);
CREATE INDEX documents_official_id ON documents(source,official_id,published_date);
CREATE TABLE document_aliases (
 source TEXT NOT NULL REFERENCES sources(id), normalized_url TEXT NOT NULL,
 document_id INTEGER NOT NULL REFERENCES documents(id), PRIMARY KEY(source,normalized_url,document_id));
INSERT INTO document_aliases SELECT source,canonical_url,id FROM documents;
CREATE TABLE speakers (
 id INTEGER PRIMARY KEY, country TEXT NOT NULL, name TEXT NOT NULL, office TEXT NOT NULL,
 valid_from TEXT, valid_to TEXT, identity_key TEXT UNIQUE NOT NULL);
CREATE TABLE statements (
 id INTEGER PRIMARY KEY, identity_key TEXT UNIQUE NOT NULL, event_key TEXT NOT NULL,
 speaker_id INTEGER REFERENCES speakers(id), speaker_name TEXT, speaker_office TEXT,
 country TEXT NOT NULL CHECK(country IN ('ROK','JPN')), institution TEXT NOT NULL,
 target_country TEXT NOT NULL CHECK(target_country IN ('ROK','JPN')), addressee TEXT,
 spoken_date TEXT, published_date TEXT NOT NULL, context TEXT NOT NULL,
 theme TEXT NOT NULL, original_language TEXT, verification_status TEXT NOT NULL,
 attribution_confidence TEXT NOT NULL CHECK(attribution_confidence IN ('high','medium','low','unknown')),
 attribution_evidence TEXT NOT NULL, third_country_context INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, CHECK(country != target_country));
CREATE TABLE statement_sources (
 statement_id INTEGER NOT NULL REFERENCES statements(id), document_id INTEGER NOT NULL REFERENCES documents(id),
 evidence_type TEXT NOT NULL, verification_status TEXT NOT NULL,
 PRIMARY KEY(statement_id,document_id));
CREATE TABLE quotes (
 id INTEGER PRIMARY KEY, statement_id INTEGER NOT NULL REFERENCES statements(id),
 text TEXT NOT NULL, text_sha256 TEXT NOT NULL, published_language TEXT NOT NULL,
 original_language TEXT, version_kind TEXT NOT NULL, verification_status TEXT NOT NULL,
 UNIQUE(statement_id,published_language,text_sha256));
CREATE TABLE quote_sources (
 quote_id INTEGER NOT NULL REFERENCES quotes(id), document_id INTEGER NOT NULL REFERENCES documents(id),
 evidence_locator TEXT NOT NULL, PRIMARY KEY(quote_id,document_id));
CREATE TABLE language_links (
 id INTEGER PRIMARY KEY, statement_id INTEGER NOT NULL REFERENCES statements(id),
 quote_a INTEGER NOT NULL REFERENCES quotes(id), quote_b INTEGER NOT NULL REFERENCES quotes(id),
 relation TEXT NOT NULL, evidence_url TEXT NOT NULL, verified_by TEXT NOT NULL,
 UNIQUE(quote_a,quote_b,relation), CHECK(quote_a < quote_b));
CREATE TABLE duplicate_candidates (
 id INTEGER PRIMARY KEY, entity_type TEXT NOT NULL CHECK(entity_type IN ('statement','quote')),
 left_id INTEGER NOT NULL, right_id INTEGER NOT NULL, reason TEXT NOT NULL,
 similarity REAL, status TEXT NOT NULL DEFAULT 'possible_duplicate',
 UNIQUE(entity_type,left_id,right_id,reason), CHECK(left_id < right_id));
CREATE TABLE collection_runs (
 id INTEGER PRIMARY KEY, run_key TEXT UNIQUE NOT NULL, started_at TEXT NOT NULL,
 finished_at TEXT, status TEXT NOT NULL, config_json TEXT NOT NULL,
 counters_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE collection_items (
 run_id INTEGER NOT NULL REFERENCES collection_runs(id), item_key TEXT NOT NULL,
 url TEXT NOT NULL, source TEXT NOT NULL REFERENCES sources(id), status TEXT NOT NULL,
 document_id INTEGER REFERENCES documents(id), documents_added INTEGER NOT NULL DEFAULT 0,
 statements_added INTEGER NOT NULL DEFAULT 0, quotes_added INTEGER NOT NULL DEFAULT 0,
 duplicates_rejected INTEGER NOT NULL DEFAULT 0, possible_matches INTEGER NOT NULL DEFAULT 0,
 error TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(run_id,item_key));
CREATE TABLE source_checks (
 id INTEGER PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), url TEXT NOT NULL,
 checked_at TEXT NOT NULL, status INTEGER, result TEXT NOT NULL, response_sha256 TEXT,
 UNIQUE(source_id,url,checked_at));
CREATE TABLE discovery_results (
 id INTEGER PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
 normalized_url TEXT NOT NULL UNIQUE, title TEXT, published_date TEXT, discovered_via TEXT NOT NULL,
 discovered_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'unreviewed');
CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
'''

AUDIT_SCHEMA = '''
CREATE TABLE statement_metadata (
 statement_id INTEGER PRIMARY KEY REFERENCES statements(id),
 institution_type TEXT NOT NULL DEFAULT 'unknown' CHECK(institution_type IN
 ('parliament','foreign_ministry','government','head_of_state_administration','political_party','other','unknown')),
 venue_institution_type TEXT, speaker_role TEXT, speaker_category TEXT NOT NULL DEFAULT 'unknown', political_affiliation TEXT,
 government_opposition_status TEXT CHECK(government_opposition_status IS NULL OR government_opposition_status IN
 ('ruling','opposition','coalition','independent','other')),
 political_status_date TEXT,
 statement_context TEXT NOT NULL DEFAULT 'unknown',
 position_scope TEXT NOT NULL DEFAULT 'unclear' CHECK(position_scope IN
 ('official_state_position','institutional_position','individual_position','faction_position','unclear')),
 evidence_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL);
CREATE TABLE statement_assessments (
 statement_id INTEGER PRIMARY KEY REFERENCES statements(id),
 relevance_category TEXT NOT NULL CHECK(relevance_category IN
 ('direct_address','official_bilateral','domestic_bilateral','regional_security','regional_cooperation','third_country_only','incidental_reference','indeterminate')),
 reason TEXT NOT NULL, evidence_sha256 TEXT NOT NULL, ruleset_version TEXT NOT NULL,
 assessment_status TEXT NOT NULL DEFAULT 'excerpt_assessed_needs_review',
 excerpt_quality TEXT NOT NULL DEFAULT 'needs_context', theme_suggestion TEXT,
 sentiment TEXT CHECK(sentiment IS NULL OR sentiment IN ('positive','negative','neutral')),
 sentiment_verified INTEGER NOT NULL DEFAULT 0 CHECK(sentiment_verified IN (0,1)),
 sentiment_evidence TEXT, assessed_by TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(sentiment_verified=0 OR (sentiment IS NOT NULL AND sentiment_evidence IS NOT NULL)));
CREATE TABLE audit_samples (
 sample_key TEXT NOT NULL, statement_id INTEGER NOT NULL REFERENCES statements(id),
 sampling_rank INTEGER NOT NULL, stratum_json TEXT NOT NULL,
 PRIMARY KEY(sample_key,statement_id), UNIQUE(sample_key,sampling_rank));
CREATE TABLE duplicate_reviews (
 candidate_id INTEGER PRIMARY KEY REFERENCES duplicate_candidates(id),
 classification TEXT NOT NULL, disposition TEXT NOT NULL DEFAULT 'possible_duplicate',
 evidence_json TEXT NOT NULL, reviewed_by TEXT NOT NULL, ruleset_version TEXT NOT NULL,
 updated_at TEXT NOT NULL);
CREATE VIEW signal_timeline AS
 SELECT s.id AS statement_id,s.event_key,s.spoken_date AS statement_date,s.published_date,
 s.country,s.target_country,s.speaker_name,m.speaker_role,m.institution_type,
 m.venue_institution_type,m.speaker_category,m.political_affiliation,m.government_opposition_status,
 m.political_status_date,m.statement_context,m.position_scope,s.context,s.theme,
 s.verification_status,s.attribution_confidence,a.relevance_category,
 a.assessment_status,a.sentiment,a.sentiment_verified,
 CASE WHEN s.spoken_date IS NULL THEN 'unknown' ELSE 'day' END AS statement_date_precision,
 (SELECT min(o.fetched_at) FROM statement_sources ss JOIN observations o ON o.document_id=ss.document_id
 WHERE ss.statement_id=s.id) AS first_observed_by_collector_at
 FROM statements s LEFT JOIN statement_metadata m ON m.statement_id=s.id
 LEFT JOIN statement_assessments a ON a.statement_id=s.id;
CREATE INDEX statement_metadata_institution ON statement_metadata(institution_type,statement_context);
CREATE INDEX statement_assessments_relevance ON statement_assessments(relevance_category);
'''

GDELT_SCHEMA = '''
CREATE TABLE gdelt_events (
 event_id TEXT PRIMARY KEY,event_date TEXT NOT NULL,observed_at TEXT NOT NULL,
 published_date TEXT,actor1_name TEXT,actor1_country TEXT NOT NULL,actor1_role TEXT,
 actor2_name TEXT,actor2_country TEXT NOT NULL,actor2_role TEXT,event_code TEXT NOT NULL,
 source_url TEXT NOT NULL,archive_url TEXT NOT NULL,raw_sha256 TEXT NOT NULL,
 record_sha256 TEXT NOT NULL,raw_json TEXT NOT NULL,
 verification_status TEXT NOT NULL DEFAULT 'machine_extracted_needs_review',
 observation_type TEXT NOT NULL DEFAULT 'gdelt_event',
 rights TEXT NOT NULL DEFAULT 'GDELT open data; no licence to source article text inferred');
CREATE TABLE gdelt_mentions (
 identity_key TEXT PRIMARY KEY,event_id TEXT NOT NULL REFERENCES gdelt_events(event_id),
 event_observed_at TEXT NOT NULL,mention_observed_at TEXT NOT NULL,source_name TEXT,
 document_identifier TEXT NOT NULL,source_type TEXT,source_language TEXT,
 archive_url TEXT NOT NULL,raw_sha256 TEXT NOT NULL,raw_json TEXT NOT NULL,
 verification_status TEXT NOT NULL DEFAULT 'machine_extracted_needs_review',
 observation_type TEXT NOT NULL DEFAULT 'gdelt_mention');
CREATE TABLE gdelt_gkg (
 record_id TEXT PRIMARY KEY,observed_at TEXT NOT NULL,document_identifier TEXT NOT NULL,
 source_name TEXT,archive_url TEXT NOT NULL,raw_sha256 TEXT NOT NULL,raw_json TEXT NOT NULL,
 relationship_scope TEXT NOT NULL DEFAULT 'country_cooccurrence_not_dyadic_event',
 verification_status TEXT NOT NULL DEFAULT 'machine_extracted_needs_review',
 observation_type TEXT NOT NULL DEFAULT 'gdelt_gkg');
CREATE INDEX gdelt_events_direction_date ON gdelt_events(actor1_country,actor2_country,event_date);
'''

EVENT_TRUTH_SCHEMA = '''
CREATE TABLE diplomatic_actions (
 event_id TEXT PRIMARY KEY, action_key TEXT NOT NULL UNIQUE,
 event_date TEXT NOT NULL, direction TEXT NOT NULL
 CHECK(direction IN ('escalation','cooperation','neutral')),
 evidence_json TEXT NOT NULL);
CREATE TABLE diplomatic_event_candidates (
 candidate_id TEXT PRIMARY KEY, evidence_json TEXT NOT NULL);
CREATE TABLE diplomatic_action_candidate_links (
 event_id TEXT NOT NULL REFERENCES diplomatic_actions(event_id),
 candidate_id TEXT NOT NULL REFERENCES diplomatic_event_candidates(candidate_id),
 PRIMARY KEY(event_id,candidate_id));
'''


LIVE_SCHEMA = '''
CREATE TABLE live_review_queue (
 id TEXT PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
 statement_id INTEGER NOT NULL REFERENCES statements(id),
 available_at TEXT NOT NULL, evidence_json TEXT NOT NULL);
CREATE TABLE live_annotations (
 id TEXT PRIMARY KEY REFERENCES live_review_queue(id),
 reviewed_at TEXT NOT NULL, annotation_json TEXT NOT NULL);
CREATE TABLE live_forecasts (
 sequence INTEGER PRIMARY KEY, assessment_date TEXT NOT NULL, method TEXT NOT NULL,
 issued_at TEXT NOT NULL, horizon_end TEXT NOT NULL, previous_hash TEXT NOT NULL,
 record_hash TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, UNIQUE(assessment_date,method));
CREATE TRIGGER live_forecasts_no_update BEFORE UPDATE ON live_forecasts
 BEGIN SELECT RAISE(ABORT,'live forecasts are append-only'); END;
CREATE TRIGGER live_forecasts_no_delete BEFORE DELETE ON live_forecasts
 BEGIN SELECT RAISE(ABORT,'live forecasts are append-only'); END;
'''

LIVE_INSERT_GUARD = '''
CREATE TRIGGER IF NOT EXISTS live_forecasts_no_replace BEFORE INSERT ON live_forecasts
 WHEN EXISTS(SELECT 1 FROM live_forecasts WHERE sequence=NEW.sequence OR record_hash=NEW.record_hash
             OR (assessment_date=NEW.assessment_date AND method=NEW.method))
 BEGIN SELECT RAISE(ABORT,'live forecasts are append-only'); END
'''

def upgrade(db, root):
    current = db.execute('PRAGMA user_version').fetchone()[0]
    if current == VERSION:
        db.execute(LIVE_INSERT_GUARD)
        return
    if current not in (0,1,2,3,4,5,6,7,8):
        raise RuntimeError(f'Unsupported schema version {current}; expected 0..{VERSION}')
    next_version=current+1
    # This is the existing schema, already created by Store. Back up only a file DB.
    db_path = db.execute('PRAGMA database_list').fetchone()[2]
    if db_path:
        folder = inside(root / 'backups')
        folder.mkdir(parents=True, exist_ok=True)
        backup_path = folder / f'pre-schema-{next_version:03d}.sqlite3'
        if backup_path.exists():
            raise RuntimeError('Pre-migration backup already exists; inspect before retrying migration')
        target = sqlite3.connect(backup_path)
        try:
            db.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed')
        finally:
            target.close()
    stamp = datetime.now(timezone.utc).isoformat()
    db.execute('PRAGMA foreign_keys=OFF')
    try:
        if current==0:
            db.executescript('BEGIN IMMEDIATE;\n' + SCHEMA)
        elif current==1:
            # Preserve all IDs and dependent FKs while permitting unknown publication dates.
            sql=db.execute("SELECT sql FROM sqlite_master WHERE name='statements'").fetchone()[0]
            sql=sql.replace('CREATE TABLE statements','CREATE TABLE statements__migration',1).replace('published_date TEXT NOT NULL','published_date TEXT')
            db.execute('BEGIN IMMEDIATE')
            db.execute(sql)
            db.execute('INSERT INTO statements__migration SELECT * FROM statements')
            db.execute('DROP TABLE statements')
            db.execute('ALTER TABLE statements__migration RENAME TO statements')
            db.execute("CREATE UNIQUE INDEX documents_identity_date ON documents(source,canonical_url,text_sha256,coalesce(published_date,json_extract(metadata_json,'$.event_date'),''))")
        elif current==2:
            db.executescript('BEGIN IMMEDIATE;\n'+AUDIT_SCHEMA)
        elif current==3:
            db.executescript('BEGIN IMMEDIATE;\n'+GDELT_SCHEMA)
        elif current==4:
            db.executescript('BEGIN IMMEDIATE;\n'+EVENT_TRUTH_SCHEMA)
        elif current==5:
            db.executescript('BEGIN IMMEDIATE;\n'+LIVE_SCHEMA)
            db.execute(LIVE_INSERT_GUARD)
        elif current==6:
            db.executescript('BEGIN IMMEDIATE;\n'+ECONOMY_SCHEMA)
        elif current==7:
            db.executescript('BEGIN IMMEDIATE;\n'+ECONOMY_NATIVE_SCHEMA)
        else:
            db.executescript('BEGIN IMMEDIATE;\n'+KOKKAI_FULL_SCHEMA)
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Migration would break foreign keys')
        db.execute('INSERT INTO schema_migrations VALUES(?,?)', (next_version, stamp))
        db.execute(f'PRAGMA user_version={next_version}')
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.execute('PRAGMA foreign_keys=ON')
    if next_version<VERSION:
        upgrade(db,root)
