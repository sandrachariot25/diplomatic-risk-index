from .korea import KoreaMOFA
from .japan import JapanMOFA

CONNECTORS = {c.source: c() for c in (KoreaMOFA, JapanMOFA)}
