from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[3]
import sys, tempfile, shutil, time
sys.path.insert(0, str(_ROOT / "ECS/runtime"))
from elpis_ecs.kernel import Kernel

d = tempfile.mkdtemp()
k = Kernel(d, mailbox_capacity=4).open()
ids = [k.found_entity(f"e{i}") for i in range(4)]
for e in ids: k.activate(e)
lo, hi = min(ids), max(ids)
ports = {e: k.entity_port(e) for e in ids}
# saturate the lexicographically-lowest mailbox and one high mailbox
ports[hi].propose(lo, b"to-low-1")
ports[lo].propose(hi, b"to-high-1")
print("ready head kind/entity:", [(i.rank, i.entity_id[:6]) for i in k.ready_items()])
# Each step drains lowest-ID mailbox first; a producer that refills it starves `hi`.
served = []
for step in range(12):
    items = k.ready_items()
    if not items: break
    head = items[0]
    served.append(head.entity_id[:6])
    k.step()
    # adversarial producer keeps the low mailbox non-empty
    if len(k.events()) < 40:
        try: ports[hi].propose(lo, b"refill-%d" % step)
        except Exception as ex: print("  refill blocked:", type(ex).__name__)
print("served order:", served)
print("hi mailbox still queued:", k.mailbox_size(hi))
print("lo=", lo[:6], "hi=", hi[:6])
k.close(); shutil.rmtree(d)
