from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[3]
import sys, tempfile, shutil, time
sys.path.insert(0, str(_ROOT / "ECS/runtime"))
from elpis_ecs.kernel import Kernel
from elpis_ecs.entity import founding_record, entity_id_from_founding
from elpis_ecs.persistence import genesis_descriptor_digest

# --- identity grinding for scheduler priority ---
g = genesis_descriptor_digest("ecs-m1a-genesis")
best = min(((entity_id_from_founding(founding_record(0, f"L{i}", g)), f"L{i}") for i in range(20000)))
print("grind 20k labels at founding_index=0 -> min entity_id prefix:", best[0][:8], "label:", best[1])
plain = entity_id_from_founding(founding_record(0, "agent", g))
print("ungrounded 'agent' prefix:", plain[:8], "-> grinder outranks:", best[0] < plain)

# --- throughput / scaling ---
for n in (200, 400, 800):
    d = tempfile.mkdtemp()
    k = Kernel(d, mailbox_capacity=1024).open()
    a = k.found_entity("a"); b = k.found_entity("b")
    k.activate(a); k.activate(b); p = k.entity_port(a)
    t0 = time.perf_counter()
    for i in range(n): p.propose(b, b"x")
    k.run_until_quiescent()
    t1 = time.perf_counter()
    ev = len(k.events())
    t2 = time.perf_counter(); k.topology_analysis(); t3 = time.perf_counter()
    print(f"events={ev:5d} commit_total={t1-t0:7.3f}s  per_event={(t1-t0)/ev*1e3:6.2f}ms  topology_analysis={t3-t2:6.3f}s")
    k.close(); shutil.rmtree(d)
