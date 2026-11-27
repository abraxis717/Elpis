#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
OUT=${1:?absolute new build directory required}
[[ $# = 1 && $OUT = /* && $OUT != */ ]]
# Canonical paths only; output must be new, outside the source export.
[[ $OUT = "$(realpath -m -- "$OUT")" && ! -e $OUT && ! -L $OUT ]]
[[ $OUT != "$ROOT" && $OUT != "$ROOT/"* && -d $(dirname -- "$OUT") ]]
# Never build into the operator's transient handoff mailbox.
case "$OUT" in /mnt/primesauce/Downloads|/mnt/primesauce/Downloads/*) exit 2;; esac
# No relaxation of the predecessor's resource admission.
CG="/sys/fs/cgroup$(awk -F: '$1=="0"{print $3}' /proc/self/cgroup)"
[[ $(cat "$CG/memory.max") =~ ^[0-9]+$ ]]
(( $(cat "$CG/memory.max") <= 4294967296 ))
test "$(cat "$CG/memory.swap.max")" = 0
test "$(cat "$CG/memory.swap.current")" = 0
test "$(wc -l < /proc/swaps)" = 1
python3 -I -B "$ROOT/policy.py" "$ROOT"
mkdir -- "$OUT"
mkdir -- "$OUT/cargo_home"
export CARGO_HOME="$OUT/cargo_home" CARGO_NET_OFFLINE=true CARGO_BUILD_JOBS=1 CUDA_VISIBLE_DEVICES='' LC_ALL=C
unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS RUSTC_WRAPPER RUSTC_WORKSPACE_WRAPPER CARGO_TARGET_DIR LD_PRELOAD LD_LIBRARY_PATH
ulimit -c 0
timeout -k 5 1200 bash "$ROOT/build_standalone.sh" "$ROOT/source" "$OUT"
python3 -I -B "$ROOT/policy.py" "$ROOT"
