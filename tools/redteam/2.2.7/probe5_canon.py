from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[3]
import sys, json, hashlib
sys.path.insert(0,str(_ROOT / "ECS/runtime")); sys.path.insert(0,str(_ROOT / "src"))
from elpis_ecs import canonical as ecs_canon
from elpis.contracts.closure.identity import content_checksum, canonical_json_bytes as closure_bytes

payload = {"label": "café", "note": "naïve"}
print("ECS canonical_bytes      :", ecs_canon.canonical_bytes(payload))
print("closure canonical_bytes  :", closure_bytes(payload))
print("identical bytes          :", ecs_canon.canonical_bytes(payload) == closure_bytes(payload))
print()
d = "x.v1"
ecs = ecs_canon.domain_digest(d, payload)
clo = content_checksum(d, payload)
print("ECS domain_digest        :", ecs[:32])
print("closure content_checksum :", clo[:32])
print("same domain+payload ->   :", "SAME" if ecs==clo else "TWO DIFFERENT IDENTITIES")
print()
# same-domain collision surface of bare concatenation vs structured
print("ASCII-only payload also diverges:", ecs_canon.domain_digest(d,{"a":1}) != content_checksum(d,{"a":1}))
