#!/usr/bin/env bash
set -Eeuo pipefail
SRC=$1; OUT=$2; REL=native/runtime/model_protocol
mkdir -p "$OUT/lib" "$OUT/native"
CC=gcc bash "$SRC/native/runtime/build_production.sh" "$SRC" "$OUT/native"
for pair in protocol:model_protocol ipc:model_ipc ipc_guard:ipc_guard;do
 name=${pair%%:*}; unit=${pair#*:}
 gcc -std=c11 -O2 -Wall -Wextra -Wpedantic -Werror -I "$SRC/$REL/include/elpis" -fvisibility=hidden -c "$SRC/$REL/src/$unit.c" -o "$OUT/lib/$unit.o"
 ar rcs "$OUT/lib/libcr6_$name.a" "$OUT/lib/$unit.o"
done
CARGO_TARGET_DIR="$OUT/cargo-host" RUSTFLAGS="-Lnative=$OUT/native -Lnative=$OUT/lib" cargo build --offline --locked --release --bin elpis_cognitive_host --manifest-path "$SRC/$REL/Cargo.toml"
cp "$OUT/cargo-host/release/elpis_cognitive_host" "$OUT/elpis_cognitive_host"
