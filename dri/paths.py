"""All persistent and temporary outputs belong to the existing project."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

def inside(path):
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(ROOT):
        raise ValueError(f'Path outside existing project: {candidate}')
    return candidate

def write_generated(path, text):
    """Atomic replacement only for explicitly named derived exports, never raw inputs."""
    target=inside(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    encoded=text.encode('utf-8')
    if target.exists() and target.read_bytes()==encoded:
        return
    temp=target.with_name(target.name+'.tmp')
    with temp.open('wb') as stream:
        stream.write(encoded);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,target)
