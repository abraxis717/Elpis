#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    selector = json.loads(
        (ROOT / "manifests/ACTIVE_COMPONENT_ASSEMBLY.json").read_text(
            encoding="utf-8"
        )
    )
    canonical = json.loads(
        (ROOT / selector["canonical_manifest"]).read_text(encoding="utf-8")
    )
    registry = json.loads(
        (ROOT / selector["component_registry"]).read_text(encoding="utf-8")
    )

    print(
        f"Assembly: {selector['active_assembly']}  "
        f"Canonical: {canonical['component_count']}  "
        f"Public: {selector['public_component_count']}"
    )
    for item in registry["components"]:
        deps = ", ".join(item.get("dependencies", [])) or "none"
        print(
            f"  {item['promotion_order']}. {item['component_id']} "
            f"({item.get('active_path_status')}) deps=[{deps}]"
        )


if __name__ == "__main__":
    main()
