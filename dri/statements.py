"""Explicit statement records, not article-to-signal conversion."""
from dataclasses import dataclass, field
from datetime import date
from .identity import normalized, fingerprint

@dataclass(frozen=True)
class Quote:
    text: str
    language: str
    original_language: str | None = None
    version_kind: str = 'published_version'
    locator: str = 'document body'

@dataclass(frozen=True)
class Statement:
    # event_key is an explicit official document/event identifier or a reviewed event id.
    # Never derive cross-publication event identity from title similarity alone.
    event_key: str
    country: str
    target_country: str
    institution: str
    context: str
    published_date: str | None
    spoken_date: str | None = None
    speaker_name: str | None = None
    speaker_office: str | None = None
    addressee: str | None = None
    theme: str = 'unclassified'
    original_language: str | None = None
    verification_status: str = 'needs_review'
    attribution_confidence: str = 'unknown'
    attribution_evidence: str = ''
    third_country_context: bool = False
    quotes: tuple[Quote, ...] = field(default_factory=tuple)
    institution_type: str | None = None
    speaker_role: str | None = None
    political_affiliation: str | None = None
    government_opposition_status: str | None = None
    political_status_date: str | None = None
    statement_context: str | None = None
    position_scope: str | None = None
    metadata_evidence: str | None = None

    def validate(self):
        if not self.event_key or not self.institution or not self.context:
            raise ValueError('Event identity, institution and context required')
        if self.country not in {'ROK','JPN'} or self.target_country not in {'ROK','JPN'} or self.country == self.target_country:
            raise ValueError('Expected a directed ROK/JPN statement')
        if self.published_date:
            date.fromisoformat(self.published_date)
        if self.spoken_date:
            date.fromisoformat(self.spoken_date)
        if not self.published_date and not self.spoken_date:
            raise ValueError('A documented date is required; do not impute publication from event date')
        if self.attribution_confidence not in {'high','medium','low','unknown'}:
            raise ValueError('Confidence is a categorical attribution assessment, not a probability')
        if not self.attribution_evidence:
            raise ValueError('Attribution evidence required, including explanation of unknowns')
        if self.institution_type and self.institution_type not in {'parliament','foreign_ministry','government','head_of_state_administration','political_party','other','unknown'}:
            raise ValueError('Unknown institution type; no implicit significance hierarchy')
        if self.political_affiliation or self.government_opposition_status:
            if not self.metadata_evidence:raise ValueError('Political affiliation/status requires explicit source evidence')
        if self.government_opposition_status:
            if self.government_opposition_status not in {'ruling','opposition','coalition','independent','other'} or not self.political_status_date:
                raise ValueError('Government/opposition status requires a documented as-of date')
            date.fromisoformat(self.political_status_date)
            if self.spoken_date and self.political_status_date!=self.spoken_date:
                raise ValueError('Political status must refer to the statement date')
        for quote in self.quotes:
            if not normalized(quote.text) or not quote.language:
                raise ValueError('Quote text and language required')

    @property
    def key(self):
        # Publication date may differ across reports; speech date and verified event are identity.
        return fingerprint(self.event_key, self.country, self.target_country,
                           normalized(self.speaker_name), normalized(self.speaker_office),
                           self.spoken_date, normalized(self.institution))

def theme_for(text):
    s = text.casefold()
    groups = [
      ('territorial_disputes', ('dokdo','takeshima','territorial')),
      ('historical_disputes', ('yasukuni','comfort women','sexual slavery','forced labor','history','historical','sado')),
      ('trade_economy', ('export','trade','economic','wto')),
      ('normalization_deescalation', ('normalization','reconciliation','de-escalation')),
      ('security', ('nuclear','missile','security','defense','defence')),
      ('regional_cooperation', ('trilateral','regional cooperation')),
      ('diplomatic_contacts', ('meeting','telephone','summit','visit'))]
    return next((name for name, terms in groups if any(t in s for t in terms)), 'unclassified')

def extract_korean_institutional(doc):
    """Only explicitly labelled institutional commentary/statements, never meeting summaries.

    No name is guessed from who held an office; no speech date is imputed from publication.
    Only the retained short excerpt is used as quote evidence.
    """
    title = doc.title.casefold()
    if doc.source != 'mofa_kr' or not any(t in title for t in ('spokesperson', 'spokesman', 'spokeswoman')):
        return []
    relevant=any(t in (title+' '+doc.text.casefold()) for t in ('japan','japanese','dokdo','takeshima')) or 'JPN' in doc.related_countries
    if not any(t in title for t in ('commentary','statement')) or not relevant:
        return []
    return [Statement(
        event_key='official:' + doc.url, country='ROK', target_country='JPN',
        institution='Ministry of Foreign Affairs, Republic of Korea', context=doc.title,
        published_date=doc.published_date, speaker_office='MOFA Spokesperson',
        addressee='Japan (topic; named recipient not established)', theme=theme_for(doc.title),
        verification_status='needs_review', attribution_confidence='medium',
        attribution_evidence='Official page explicitly labels an institutional spokesperson statement/commentary; no personal name or speech date established.',
        third_country_context=any(t in doc.title.casefold() for t in ('north korea','china','russia')),
        quotes=(Quote(doc.text, doc.language, version_kind='unofficial_translation' if doc.translation_note else 'published_version'),) if doc.text else (),
    )]
