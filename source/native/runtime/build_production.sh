#!/usr/bin/env bash
set -Eeuo pipefail
trap 'rc=$?; echo "HOLD_PROD_BUILD_LINE=$LINENO RC=$rc COMMAND=$BASH_COMMAND" >&2' ERR
SRC=$1; OUT=$2; N=$SRC/native; R=$N/runtime; G=$N/geodome; C=$N/cgc; E=$N/ECS_C/enrollment; S=$N/ECS_C/session; H=$N/substrate; K=$N/ECS_G; B=$R/cognitive_binding; D=$R/cognitive_transaction
mkdir -p "$OUT"
incs=("$G/scheduler/include" "$G/include" "$G/state/include" "$H/include" "$C/include" "$E/include" "$S/include" "$K/include" "$B/include" "$D/include" "$G/state/src" "$G/scheduler/src" "$C/src" "$E/src" "$D/src" "$R")
flags=(-std=c11 -O2 -Wall -Wextra -Wpedantic -Werror -fPIC -fvisibility=hidden -ffp-contract=off -fno-fast-math -fno-builtin-malloc -fno-builtin-calloc)
for i in "${incs[@]}"; do flags+=("-I$i");done
for f in check_evidence create destroy entity_at entity_find next_entity_id read_coordinate transition; do flags+=("-Delpis_ecs_c_session_${f}=cr5_session_${f}");done
units=("$G/src/geodome_geometry.c" "$G/src/geodome_index.c" "$G/src/geodome_address.c" "$C/src/cgc_r97w.c" "$K/src/ecsg_math.c" "$H/src/sha256.c" "$B/src/cognitive_binding.c" "$D/src/evidence_image.c" "$D/src/state_image.c" "$D/src/pool_image.c" "$R/cr5_borrowed_coordinator.c" "$R/reusable_scheduler.c" "$R/production_capabilities.c")
objects=(); for u in "${units[@]}"; do o="$OUT/$(basename "${u%.c}").o"; "${CC:-gcc}" "${flags[@]}" -c "$u" -o "$o"; objects+=("$o");done
rm -f "$OUT/libcr5_production.a"; ar rcs "$OUT/libcr5_production.a" "${objects[@]}"
python3 -I -B - "$OUT/libcr5_production.a" <<'PY'
import subprocess,sys,collections
p=sys.argv[1]; text=subprocess.check_output(['nm','-g',p],text=True)
rows=[l.split() for l in text.splitlines() if l.strip() and not l.endswith(':')]
assert not any('elpis_ecs_c_session_' in l for l in text.splitlines()),'unmapped session reference'
refs={r[-1] for r in rows if r[-2]=='U' and r[-1].startswith('cr5_session_')}
expected={'cr5_session_'+n for n in ('check_evidence','entity_at','entity_find','next_entity_id','read_coordinate','create','destroy','transition')}
assert refs==expected,refs
owners=collections.Counter(r[-1] for r in rows if r[-2] in ('T','D','B','R'))
assert all(owners[n]==1 for n in expected|{'ct_create_borrowed','ct_commit','eve_commit','gds_create','cgp_create','gsc_create','gsc_workspace_reserve','ct_budget_start','ct_budget_end','ct_budget_open','ct_budget_usage'})
assert not any('probe' in n or n.startswith('cr5_retained_') for n in owners)
assert len(subprocess.check_output(['ar','t',p],text=True).splitlines())==13
print('PROD_NATIVE_TRANSLATION_UNITS=13\nPROD_CAPABILITY_SYMBOL_OWNERSHIP=PASS\nPROD_TEST_PROBE_SYMBOLS=0\nPROD_STRICT_ARCHIVE=PASS')
PY
