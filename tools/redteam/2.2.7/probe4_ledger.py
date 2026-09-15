from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[3]
import sys, time, tempfile, os, hashlib
sys.path.insert(0,str(_ROOT / "components/Grid81DeterministicCapabilityApplicationExecutor/src"))
from elpis_grid81_application_executor.durable_ledger_v2 import DurableApplicationLedgerV2
d=tempfile.mkdtemp(); L=DurableApplicationLedgerV2(os.path.join(d,"l.db"))
h=lambda s: hashlib.sha256(s.encode()).hexdigest()
marks={}
t0=time.perf_counter()
for i in range(1,1201):
    L.append(L.head, h(f"r{i}"), h(f"a{i}"))
    if i in (100,200,400,800,1200): marks[i]=time.perf_counter()-t0
prev=0
for n,t in marks.items():
    print(f"n={n:5d} cumulative={t:7.3f}s  marginal_per_append={(t-prev)/ (n- (list(marks).index(n) and list(marks)[list(marks).index(n)-1] or 0) ) *1e3:7.2f}ms")
    prev=t
