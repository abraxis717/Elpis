from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "native/hacf_bridge/fms_inference_bridge.h"
SOURCE = ROOT / "native/hacf_bridge/fms_inference_bridge.c"


def test_bridge_stats_arrays_use_fms_symbolic_cardinalities():
    text = HEADER.read_text(encoding="utf-8")
    assert '#include "elpis/fms.h"' in text
    assert "uint64_t tier_bytes[FMS_NTIERS];" in text
    assert "uint64_t domain_bytes[FMS_NDOMAINS];" in text
    assert "tier_bytes[3]" not in text
    assert "domain_bytes[3]" not in text


def test_bridge_copy_loops_use_distinct_symbolic_cardinalities():
    text = SOURCE.read_text(encoding="utf-8")
    assert "for (int i = 0; i < FMS_NTIERS; ++i)" in text
    assert "for (int i = 0; i < FMS_NDOMAINS; ++i)" in text
    assert not re.search(r"for\s*\([^;]+;[^;]*<\s*3\s*;", text)


def test_three_slot_external_abi_is_an_explicit_compile_time_invariant():
    text = SOURCE.read_text(encoding="utf-8")
    assert '_Static_assert(FMS_NTIERS == 3' in text
    assert '_Static_assert(FMS_NDOMAINS == 3' in text
    assert "Python ctypes ABI" in text
