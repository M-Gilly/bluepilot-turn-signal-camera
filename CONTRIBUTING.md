# Contributing

Start with the compatibility table and validation record in the README. Reproduce issues with the unmodified stationary release before proposing changes. Use the test-report issue template and keep identifying data out of public logs.

Run the three host suites listed in README.md. Explain additional tests appropriate to the change. Installer changes should preserve backups, refusal of incompatible inputs, restoration and repeat-install handling. Device-state stubs and reported module status are not proof of receiver or vehicle behavior.

For compatibility ports, identify the exact source revisions, baseline files, fingerprint, device/harness and observed camera behavior. For message changes, document captured evidence, direction/bus, payload fields, timing, cleanup and how the receiving modules were observed. Keep behavior changes separate from checksum or formatting updates.

Use `python3 tools/build_release.py` to validate payload hashes and produce the versioned ZIP. This command rejects payloads that differ from the release manifest; it does not update behavioral assertions or validate arbitrary edits. Review checksum changes together with the source changes they describe.

Respect upstream licenses and retain copyright notices. No broad license grant is inferred from this mixed-source repository.
