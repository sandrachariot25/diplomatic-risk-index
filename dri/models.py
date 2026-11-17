from dataclasses import dataclass
from datetime import date
import hashlib
import unicodedata

@dataclass(frozen=True)
class Document:
    source: str
    url: str
    title: str
    published_date: str | None
    text: str
    language: str
    publisher: str
    author: str | None = None
    author_role: str | None = None
    translation_note: str | None = None
    rights: str = 'Review source-specific terms before redistribution'
    source_type: str = 'primary'
    content_policy: str = 'legacy_unreviewed'
    official_identifier: str | None = None
    content_sha256: str | None = None
    related_countries: tuple[str, ...] = ()
    event_date: str | None = None
    country_scope: str | None = None
    fingerprint_kind: str = 'normalized_text'
    legacy_content_fingerprint: str | None = None
    observation_type: str | None = None
    text_completeness: str | None = None
    analysis_status: str | None = None
    verification_status: str | None = None
    institution: str | None = None
    observation_addressee: str | None = None
    theme: str | None = None
    rights_evidence: str | None = None
    research_metadata: dict | None = None

    def validate(self):
        if self.published_date:
            date.fromisoformat(self.published_date)
        if self.event_date:
            date.fromisoformat(self.event_date)
        if not self.published_date and not self.event_date:
            raise ValueError('At least a documented event or publication date is required')
        if not self.title.strip() or (self.content_policy not in {'metadata_only', 'excerpt_only'} and len(self.text.strip()) < 100):
            raise ValueError('Missing title or insufficient document body')
        if self.source_type not in {'primary', 'secondary'}:
            raise ValueError('Invalid document source type')

    @property
    def text_sha256(self):
        if self.content_sha256:
            return self.content_sha256
        normalized = ' '.join(unicodedata.normalize('NFC', self.text).split())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
