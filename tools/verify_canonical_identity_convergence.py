# Verify the known F7 divergence and the v1 convergence target.
from __future__ import annotations

import json

from elpis.canonical_identity import canonical_json_bytes, content_digest
from elpis.contracts.closure.identity import (
    canonical_json_bytes as closure_bytes,
    content_checksum as closure_checksum,
)
from elpis_ecs import canonical as ecs_canonical


def main() -> int:
    payload = {"label": "café", "note": "naïve"}
    domain = "x.v1"

    ecs_bytes = ecs_canonical.canonical_bytes(payload)
    closure = closure_bytes(payload)
    ecs_digest = ecs_canonical.domain_digest(domain, payload)
    closure_digest = closure_checksum(domain, payload)

    if ecs_bytes == closure:
        raise RuntimeError("F7_DIVERGENCE_NOT_REPRODUCED:bytes")
    if ecs_digest == closure_digest:
        raise RuntimeError("F7_DIVERGENCE_NOT_REPRODUCED:digest")

    result = {
        "legacy_ecs_bytes_hex": ecs_bytes.hex(),
        "legacy_closure_bytes_hex": closure.hex(),
        "legacy_ecs_digest": ecs_digest,
        "legacy_closure_digest": closure_digest,
        "canonical_v1_bytes_hex": canonical_json_bytes(payload).hex(),
        "canonical_v1_digest": content_digest(domain, payload),
        "legacy_bytes_diverge": True,
        "legacy_digests_diverge": True,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
