# Validation record — v0.1, 2026-10-23

## What this release contains

The seven camera/controller/settings source files are byte-for-byte identical to the unmodified stationary beta installed and previously verified on the development comma. The native header includes the expired-trailer-lease recovery correction. No edited moving-operation variants from the later source discussion or Downloads folder are included.

The stock-oriented installer is new. It uses the isolated Panda archive/build/signature approach previously exercised successfully on the development device. Default OFF, stock compatibility checks, snapshot/restore and repeat-install handling are new wrapper behavior. This wrapper has **not yet had an end-to-end installation on a second physical stock device**. No comma/device was changed while preparing this archive.

## Host checks completed

- **21 complete native-hook tests passed**, compiling the packaged Ford and camera safety headers against the pinned host safety fixture. Includes exact payload/bus restrictions, freshness, motion/control rejection, forwarding, hard budgets, unrelated TX/FWD comparison, and two missing-cleanup recovery regressions.
- **9 runtime/settings/UI tests passed** against packaged source. Includes OFF behavior, eligibility loss, setting persistence/failure handling and UI refresh through stubs. UI stub tests do not establish actual screen fit on every device.
- **11 installer tests passed** in temporary host filesystems. Includes install/restore with modes and absent files, default OFF, import-failure rollback, interrupted deployment recovery, corrupt backup refusal, changed artifact/source refusal, offroad rejection, symlink rejection and no-op repeat deploy. These tests use controlled stubs for device state, imports/build environment and target revisions; no device is flashed.
- The final ZIP is extracted into a fresh temporary directory and the same tests run again. Payload hashes are checked against the original beta manifest.

These targeted tests are not a complete passing Ford safety suite. Earlier broad diagnostics recorded **22,556 failures on the stock checkout and the same outcomes/hook traces on that earlier candidate**. That comparison did not make the failing checks pass. It is historical evidence for an earlier candidate, not a fresh full-suite result for this release. No claim of comprehensive safety-suite validation is made.

## Vehicle observations already available

On the development Lightning, the stationary short-length emulation produced both actual mirror-camera feeds. The user reported successful cancellation/toggle behavior, no cross-traffic warning in those successful short-length tests, and no displayed range change. Running Panda signature and installed source were verified after its earlier beta reboot. Community feedback must independently establish compatibility on another truck.

A separate genuine-trailer drive showed camera operation during motion with lateral control active. That drive is **not** validation of moving emulation. This stationary release does not enable motion or active assistance.

## Not established

Actual radar target detection under emulation, isolated receiver/HIL behavior, moving emulation, longitudinal-control interaction, arbitrary speeds, other BluePilot revisions, other fingerprints, unsupported UI/device/harness combinations, or recovery from every power/storage failure. Reported CTA ON and an absent warning are not substitutes for measured detection performance.

## Review and scope

This ZIP is an experimental stationary test distribution. It is not a production-ready claim or a factory-approved feature. The full source, manifest, build logic, verification script, monitor and tests are included for review. No prerecorded raw vehicle logs or credentials are included. Review upstream licensing/redistribution rights before posting modified upstream source publicly.
