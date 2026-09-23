# Full release v1

`tools/full_release.py` is the normal operator entry point once development
changes are committed and the working tree is clean.

```sh
python tools/full_release.py
python tools/full_release.py --execute
```

The first command is a zero-effect plan. `--execute` owns the complete lifecycle:

1. create and commit the write-once v3 seal;
2. run the fixed local qualification categories and materialize the exact report;
3. invoke the crash-safe lower-level release orchestrator for main/tag/Release/PyPI;
4. commit only the append-only publication assertion;
5. separately commit `RELEASE_RATIFICATIONS/Elpis<version>.json`;
6. rerun publication verification, release verification, and full root;
7. fast-forward public main from the immutable seal to the ratification commit;
8. require every release-required main workflow green on that exact closeout SHA;
9. write a Git-private terminal `CLOSED.json`.

State, logs, intent, qualification report, and terminal receipt live under the
common Git directory in `elpis-full-release-v1/<version>/`. Re-running the same
command resumes the same release state. A failed required hosted workflow is not
permission to construct a new intent or rerun until green.

`release_orchestrator.py` remains available for recovery/forensics. Ordinary
releases should use only `full_release.py --execute`.
