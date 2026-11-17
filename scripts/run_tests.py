"""One canonical test report, written only inside this project."""
import io
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report=stream.getvalue()
    (ROOT/'docs/TEST_RESULTS.txt').write_text(report,encoding='utf-8')
    print(report)
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
