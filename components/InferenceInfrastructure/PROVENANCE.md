# Inference infrastructure R0 donor authority

Experimental, in-process components. Neither public-registry nor general runtime
admission is granted. Existing P0 expert proposals remain proposal-only.

All paths below are relative to the local `ElpisDonors` intake. The complete
local source inventory and checksum verification are in the workspace evidence
directory `astra.tmp/inference_r0`. No donor is a production dependency.

| Mechanism | Local reference | Identity | Role | License |
|---|---|---|---|---|
| DSV41_ENGRAM | DeepSeek4.1/00_V41_REFERENCE/inference/engram.py | UPSTREAM_REVISION_UNPINNED; SHA256 11f35ecbead8150c35aa002b3d180ef290b05a25afe883a11884f94d476d3897 | PRIMARY_ARCHITECTURE | MIT |
| Local/global context, sparse MoE | DeepSeek4.1/00_V41_REFERENCE/inference/model.py | UPSTREAM_REVISION_UNPINNED; local inventory | PRIMARY_ARCHITECTURE | MIT |
| V4.1 embedded DSpark | Same model.py | Same local identity | COMPARATIVE_ONLY | MIT |
| DS_ENGRAM_DEMO | DeepSeek4.1/02_Engram/engram_demo_v1.py | fb7f84a21f91223715394a33a1dc24bbfb7f788e | COMPARATIVE_ONLY; different hash space | Apache-2.0 |
| QWEN38_PLE | Qwen3.8/vllm_runtime/ngram_embedding.py; tests/test_ple.py | 82daf9f5756e1868be0aa751afaec4726beca12a | IMPLEMENTATION_REFERENCE / INDEPENDENT_ORACLE | Apache-2.0 |
| PLE comparison | Qwen3.8/nemo_reference/engram.py | 44cf34834b679ff0cf0df4ff56cc37ddf5273a02 | COMPARATIVE_ONLY | Apache-2.0 |
| QSA | Qwen3.8/nemo_reference/qsa.py; vllm_runtime/indexer_qsa.py | corresponding intake revisions above | COMPARATIVE_ONLY | Apache-2.0 |
| V4-style hash and row engine | Qwen3.8/ds4_nvme/ds4_engram.c; ds4_engram.h | 0aaea5a238fb41a35106a551e73c8409dfb751ac | IMPLEMENTATION_REFERENCE / INDEPENDENT_ORACLE; not Qwen PLE | MIT |
| Markov drafter and verifier | DeepSeek4.1/01_DeepSpec/deepspec/modeling/dspark/markov_head.py; eval/dspark/draft_ops.py; eval/dspark/evaluator.py | 005e03b81cec38b7da6399833d609ee89a2587f2 | PRIMARY_ARCHITECTURE | MIT |
| Lifetime, compaction, forks | ZCode/context/context-types.ts; compaction/compact-contract.ts; state/session-fork.ts | 872ad960de7ec172591f7e1952f7849229f94521 | IMPLEMENTATION_REFERENCE | Apache-2.0 |

Donor reports and evaluation data are NON_EXECUTABLE_REFERENCE. Training,
download, deployment, host-control and product infrastructure scripts are
OUT_OF_SCOPE. No donor evaluation material is training data.

The tiny address artifacts are synthetic maps and frozen constants. Qwen golden
rows were evaluated using the isolated local vLLM reference test function with
already installed Torch. DeepSeek golden rows were independently evaluated by
the compiled, unmodified DS4 hash implementation, including masked tokens and
all feed splits. Runtime scheme validation uses pinned artifacts, never runtime
constant regeneration. These facts do not establish compatibility with either
production trained table. The production V4.1 tokenizer/map is unavailable.

License texts are retained in this directory's `licenses/`. No NOTICE file was
present in the intaken Apache source subsets; `NOTICE` records attribution and
the adaptation scope, without inventing upstream notices.
