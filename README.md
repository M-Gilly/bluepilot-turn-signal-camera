# BluePilot Turn Signal Camera

> **DEVELOPMENT AND TESTING ONLY — NOT READY FOR DEPLOYMENT.**
>
> This experimental code works only while the vehicle is stationary: stopped in Drive, foot brake held, accelerator released and driving assistance inactive. It does not support camera activation while driving. Use it only for controlled stationary testing and development; it is not ready for production deployment, routine vehicle use or road use.

An experimental BluePilot integration that uses the F-150 Lightning's existing factory side cameras to display the corresponding mirror view when a physical turn signal is selected.

**Stationary-only operation is enforced in the published code.** The feature is controlled by **Settings → BluePilot → Vehicle → Turn Signal Blind Spot View** and defaults to OFF on a new community installation.

## Purpose

The project documents a reproducible way to activate the factory side-camera feature and gives other owners and developers a small, inspectable implementation for stationary testing. The repository includes the Python controller integration, Panda camera-message checks, settings toggle, installer, verification tools and test fixtures.

The purpose of publishing this source is to support inspection, controlled stationary testing and development. The project aims to gather compatibility reports, document the factory message sequence and improve installation/recovery behavior. It is not ready for deployment and is not a Ford-endorsed implementation.

## What happens when you signal

After confirming the required vehicle conditions and fresh baseline messages, the runtime:

1. Sends the captured short trailer-length field in CAN message `0x227` toward the camera network.
2. Waits at least 350 ms, then sends trailer-connected status in `0x443`.
3. Refreshes the two messages about once per second during a bounded attempt of up to eight seconds.
4. Restores eligible fresh baselines when the signal is cancelled, the toggle is switched off or the attempt times out. Loss of eligibility stops new output, and temporary forwarding leases expire.

The truck's physical signal state determines left versus right. This runtime does not send a direct `0x3E2` camera-view request or a `0x192` camera-button pulse. It does not activate an entire factory trailer profile or replay range/trailer-ID messages.

This is **partial trailer-state emulation**, not simply a screen overlay. Receiving Ford modules determine how those states affect factory behavior. The mechanism, bytes and timing are documented in [docs/MESSAGE_SEQUENCE.md](docs/MESSAGE_SEQUENCE.md).

## Compatibility

| Component | Supported baseline |
|---|---|
| Vehicle fingerprint | `FORD_F_150_LIGHTNING_MK1` |
| BluePilot commit | `e1d051d7ba270261b4455068bd68f1a58db15a4a` |
| Panda commit | `d994e8e8009d934a94c3a94c863b559118353bdd` |
| Camera hardware | Existing factory side/mirror cameras and applicable factory camera capability |
| UI / firmware verification | Pinned MICI settings layout / supported internal SPI H7 Panda |
| New installation | Exact stock source hashes listed in `manifest.json` |

Other vehicle fingerprints, software versions and device/harness combinations are not established by this release. The installer rejects incompatible baselines. It is not a complete BluePilot distribution and cannot add missing camera hardware or factory configuration.

## Development setup

**The setup instructions are provided only for controlled stationary testing and development. Their presence does not mean the project is ready to deploy.**

Read **[the full installation and restore guide](docs/INSTALL.md)** before running an installer. It covers prerequisites, compatibility checks, the separate firmware build, deployment, reboot, running-firmware verification, stationary testing and rollback.

To create the versioned installer ZIP from a checked-out copy of this repository:

```bash
python3 tools/build_release.py
```

The archive is written to `dist/ford-camera-community-beta-v0.1.zip`. Use that versioned archive with the installation guide. GitHub's automatic “Download ZIP” uses a different top-level folder and should not be substituted in the guide's extraction command.

The stock installer defaults the toggle OFF and preserves checksummed backups. It also pauses staged-update activation and startup rebuilding while the beta is installed; **restore before updating BluePilot**. The guide explains these startup changes and their restoration.

Existing private-beta users should keep their original installer/receipt and use its verification/restore tools. Matching source without this community installer's backup receipt is not adopted as a fresh installation.

## What has been tested

On the development Lightning, both actual mirror feeds appeared during stationary tests. The toggle and cancellation were reported working. The successful short-length tests had no reported cross-traffic warning or displayed range change.

These are observations from those tests. They do not establish actual radar target-detection performance, every receiving module's behavior or compatibility with another truck. Moving operation with a genuine physical trailer was recorded separately; it is not validation of moving emulation, and this beta retains its stationary restrictions.

The source release has passed **41 targeted host tests**: 21 native-hook tests, 9 runtime/settings/UI tests and 11 installer transaction tests. The community stock installer has not yet completed an end-to-end installation on a second physical stock device. Earlier broad diagnostics also contained stock test failures; this project does not claim a fully passing Ford safety suite.

Passing these host tests and the reported stationary experiments does not establish deployment readiness. **The project remains development/testing-only and is not ready for deployment.**

See [docs/VALIDATION.md](docs/VALIDATION.md) for the evidence, test scope and remaining gaps.

## Run the host tests

Requirements: Python 3.10 or later and a host C compiler (`clang`, `cc` or `gcc`). The intended comma environment uses its existing Python 3.12 venv. No vehicle or CAN hardware is used by these tests.

```bash
python3 -m unittest discover -s . -p test_installer.py -v
python3 -m unittest discover -s . -p test_toggle.py -v
python3 -m unittest discover -s tests/native -p test_length.py -v
```

The native suite compiles the packaged safety headers into temporary host libraries. Installer tests use temporary filesystems and controlled device-state stubs. They do not flash firmware or establish vehicle detection performance.

## Source map

| Location | Role |
|---|---|
| `files/opendbc_repo/opendbc/car/ford/carcontroller.py` | Integration with the existing Ford sender |
| `files/opendbc_repo/opendbc/car/ford/sidecamera_engine.py` | Shared eligibility and legacy experiment helpers |
| `files/opendbc_repo/opendbc/car/ford/sidecamera_runtime.py` | Current bounded `LengthAttempt` sequence |
| `files/opendbc_repo/opendbc/car/ford/sidecamera_settings.py` | Persistent toggle preference |
| `files/opendbc_repo/opendbc/safety/modes/ford_sidecamera.h` | Camera-message checks and forwarding leases |
| `files/selfdrive/ui/bp/mici/layouts/settings/vehicle_mici.py` | Vehicle settings toggle |
| `setup.py` / `build_helpers.py` | Pinned build, deployment, backups and restore |
| `verify.py` | Offroad source, saved-firmware and running-Panda verification |
| `monitor.py` | Receive-only targeted CAN/state capture |
| `manifest.json` | Stock and installed payload hashes |

The working runtime uses `LengthAttempt`; the older `Engine` strategies are not its active camera path. Read the actual code rather than interpreting every legacy helper as current behavior.

## Feedback and contributions

Use the [feedback template](docs/FEEDBACK.md) or open an issue describing the exact vehicle/software baseline, installation/verification results, the actual left/right video observed, cancellation behavior and any warnings or range change. Include relevant capture timestamps. Redact VIN, account information and identifying location data from shared logs.

Please keep compatibility ports, installer changes and message-behavior changes reviewable as separate contributions. Describe the trigger, expected behavior, exact files changed and evidence supporting the change. Keep checksums and generated release contents consistent; checksums establish file integrity, not behavioral correctness.

## Source provenance

This repository includes project-specific code and modified/fixture files from the pinned BluePilot, Panda and opendbc sources. Existing notices and upstream terms continue to apply. No new blanket license is assigned to mixed upstream code. See [NOTICE.md](NOTICE.md).

The repository and release builder exclude device receipts, firmware artifacts, private keys, credentials and recorded vehicle logs. Firmware is built locally from the supported checkout.
