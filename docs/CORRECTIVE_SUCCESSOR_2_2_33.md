# Elpis2.2.33 corrective successor authority

Elpis2.2.32 is immutable locally sealed qualification failure evidence.

- development commit: `e2371d6fdfda0ac0a364dc759a32ddb551ac5be8`
- sealed commit: `830673bff4c35bafd93ab17c7fd9f0b3f71c10d6`
- manifest SHA-256: `a8969284b46fafce1cca369cd47b32ef4ad1949c15b91c5736ddfdfdef14bd53`
- signed tag: absent
- remote tag: absent
- push/publication: not reached
- failure class: `STALE_PRESEAL_ONLY_HOSTED_MECHANICS_TEST_REJECTED_SEALED_MANIFEST`

The exact sealed-candidate failure was the 2.2.32-specific hosted-mechanics regression asserting that `manifests/Elpis2.2.32.RELEASE_MANIFEST.json` must not exist. That assertion was valid only before sealing and became false by design after the canonical write-once seal commit.

Elpis2.2.33 preserves the failed manifest unchanged and converts that regression into historical-evidence semantics. Current-version manifest behavior remains governed by the generic current-release hygiene and immutable-evidence contracts.
