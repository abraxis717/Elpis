# Elpis2.2.34

## Version: v2.2.34

Corrective successor to the sealed, signed, tagged, hosted-CI-failed Elpis2.2.33 release attempt.

This release preserves the qualified 2.2.33 product/runtime payload and corrects repository-identity mode separation: development and candidate verification no longer acquire release-tag authority from an incidental local tag ref, while strict tagged verification continues to require the real annotated tag object at HEAD.
