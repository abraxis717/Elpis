from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[3]
import os, sys, shutil, tempfile
sys.path.insert(0, str(_ROOT / "ECS/runtime"))
from elpis_ecs.kernel import Kernel

d = tempfile.mkdtemp()
k = Kernel(d).open()
a = k.found_entity("a"); b = k.found_entity("b")
k.activate(a); k.activate(b)
p = k.entity_port(a)
for i in range(5):
    p.propose(b, b"msg%d" % i)
k.run_until_quiescent()
cp = k.checkpoint()
root_full = k.state_root_digest()
n_full = len(k.events())
k.close()

log = os.path.join(d, "events.log")
size_full = os.path.getsize(log)
# Truncate to the last complete frame boundary before the final event.
import struct
off = 0; bounds=[]
with open(log,"rb") as fh: data = fh.read()
while off < len(data):
    ln = struct.unpack_from(">Q", data, off)[0]
    off += 8 + ln
    bounds.append(off)
rollback_to = bounds[-3]   # drop the last two committed events
with open(log,"r+b") as fh: fh.truncate(rollback_to)

k2 = Kernel(d).open()
print("REOPEN AFTER SILENT TRUNCATION: OK")
print("  events before:", n_full, " after:", len(k2.events()))
print("  root before  :", root_full[:16])
print("  root after   :", k2.state_root_digest()[:16])
print("  checkpoint on disk claimed event_index:", cp.event_index, "clock:", cp.logical_clock)
print("  checkpoint ignored by replay:", cp.state_root_digest[:16], "!=", k2.state_root_digest()[:16])
k2.close()
shutil.rmtree(d)
