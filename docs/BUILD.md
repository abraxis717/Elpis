# Offline native development build

This candidate contains the C/Rust native runtime, not a neural model. The build is not a deployment or runtime launch authorization.

## Requirements

Linux with cgroup v2, Bash, GNU coreutils and binutils, GCC, Python 3.11+ (tomllib), and Rust/Cargo 1.89 or newer. The dependency closure uses local crates and the checked-in Cargo lock. No network downloads are performed by the build. Toolchains must already be installed. The qualified host is Linux-specific; a successful compile is not proof of kernel containment compatibility.

Use a clean source export: the positive inventory validator deliberately rejects extra files, including `.git`, untracked files and in-tree builds. From a Git checkout at the intended commit, export into a new directory:

```bash
mkdir -p "$WORK/source-export"
git archive HEAD | tar -xf - -C "$WORK/source-export"
```

Set `WORK` to an existing absolute, canonical, operator-selected development directory outside the checkout. The export directory must initially be empty. Choose a new output directory outside the export. For a Linux machine with a delegated systemd user cgroup and no active host swap:

```bash
systemd-run --user --scope --quiet -p MemoryMax=4G -p MemorySwapMax=0 \
  bash "$WORK/source-export/build.sh" "$WORK/build"
```

The build checks its actual cgroup memory and swap limits and refuses active host swap. It does not change host configuration. The output path must not already exist. On Ouroboros, use the established persistent DEV artifacts root, not Downloads or /home/joe. The output contains four native archives and `elpis_cognitive_host`; neither is installed or run by this build.

Archive byte parity is toolchain-specific; different compilers or linkers can produce different bytes. Fresh behavioral qualification and containment are separate gates. The host starts empty and expects supervisor-assigned pipe capabilities. No public enrollment, dynamic reconnection, generic FMS allocator, or cognitive utility is established by this build.

## CI

The workflow validates a clean Git export and performs an offline native build in a bounded cgroup on a disposable GitHub-hosted Linux runner. Only that ephemeral runner may have swap disabled for the build; the local wrapper never alters swap configuration. No runtime is launched and no artifacts are published. Successful hosted CI for the exact candidate commit is required before main promotion.
