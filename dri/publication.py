"""Internal research retention does not authorize publication of text or raw files."""
INTERNAL_POLICIES={'internal_research_only','restricted_research_full_text'}

def internal_document(metadata):
    return metadata.get('content_policy') in INTERNAL_POLICIES

def internal_statement(db,sid):
    return bool(db.execute('''SELECT 1 FROM statement_sources ss JOIN documents d ON d.id=ss.document_id
        WHERE ss.statement_id=? AND d.content_policy IN ('internal_research_only','restricted_research_full_text') LIMIT 1''',(sid,)).fetchone())

WITHHELD='[Text withheld: internal research only; publication rights not established]'
