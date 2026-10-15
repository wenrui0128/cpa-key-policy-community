# Publication privacy review — 2026-10-14

This directory is a clean public source export, not a copy of a private Git repository. No Git history is included. Preserve the upstream MIT copyright and attribution when creating your own public repository.

The review covers source, dependency lockfiles, documentation, built embedded HTML, synthetic screenshots, and the separately distributed Linux shared library. The public package excludes:

- Account authorization files, management/viewer credentials, downstream keys and private-key files.
- Production endpoints, domains, public/private IP addresses and personal home-directory paths.
- Real key names, costs, quota caches, account IDs, reset-credit IDs, ledgers, logs and backups.
- Host bootstrap/deployment scripts, captured terminal output and screenshots of real services.
- node_modules, Python bytecode, build caches, source-control history and OS metadata.

Example addresses use loopback or reserved example domains. Example users and dollar values are fabricated. Test credentials are generated at runtime, used only in temporary files and removed afterward. Screenshots were visually reviewed and PNG chunks checked for absence of textual/EXIF metadata. The plugin screenshot shows only a loopback test address and synthetic key previews.

`python3 scripts/check-public-source.py` rejects credential patterns, personal paths, unexpected IPs/URL hosts, runtime files, symlinks, OS metadata and unreviewed binary assets. Gitleaks with the included CPA-key rule also passed. The shared library was built with `-trimpath -buildvcs=false` and stripped debug symbols, then checked for credential patterns and known private identifiers. SHA-256 manifests accompany the source and release artifacts.

Review results apply to these dated files; scanners cannot guarantee detection of every possible secret. Keep new data/secrets directories outside Git, retain the ignore rules, and rerun both scanners after any future edits. An authenticated dashboard still intentionally displays key names and spending to authorized viewers; do not assume that granting someone viewer access hides those statistics.

## Final publication check — 2026-10-15

An empty test-generated ledger (zero keys, no usage) was removed before publication. The scanner now rejects both historical runtime-ledger filename variants, regression tests cover those files and monitor runtime directories, and plugin tests isolate default state writes in a temporary directory. The new repository uses a GitHub noreply author address, with no inherited Git history.
