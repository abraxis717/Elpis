# Runtime R4 — guarded Darwinian evolution-path attempt

R4 is an additive, qualified-inactive integration seam. It composes the
qualified `EvolutionPathGate` immediately before the existing
`DarwinianMatrix.controller.episode.advance_episode` transaction.

It does not modify DarwinianMatrix, the R2/R3 runtimes, FPRM, token inference,
ECS mutation, active assembly, public registry, or runtime-admission state.
A rejected path assertion executes zero Darwinian attempts. An admitted path
assertion executes exactly one existing Darwinian episode attempt and returns
the existing `GateExecuted`/`PathTransitionReceipt` lineage.

R4 performs no candidate generation, evaluation, selection, heredity, child
workspace materialization, model loading, semantic interpretation, or
background execution. Those remain separate authorities and later gates.

`runtime_admission = false`.
