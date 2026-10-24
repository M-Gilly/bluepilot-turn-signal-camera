# Turn Signal Blind Spot View — stationary community beta v0.1

This package automatically attempts the matching factory side-camera view when a physical turn signal is selected, **only while stopped in Drive, foot brake held, accelerator released and assistance inactive**. There is no arming command. The settings toggle is **Turn Signal Blind Spot View**, and a new installation defaults to **OFF**.

This is the stationary camera code previously tested on the development Lightning, with a new stock-installation wrapper. Both actual side feeds, cancellation, the toggle, no cross-traffic warning during the successful short-length tests, and unchanged displayed range were reported on that truck. These observations are not proof of actual radar target-detection performance or compatibility with other trucks. The new community installer has passed host tests; it has not yet been run end to end on a second physical stock device. Treat the first compatible stock installation as installer beta testing too.

## Supported installation — check before proceeding

* F-150 Lightning identified by BluePilot as `FORD_F_150_LIGHTNING_MK1`.
* Existing factory mirror/side-camera hardware and factory turn-signal/trailer side-camera capability. The package cannot add cameras or guarantee missing factory configuration.
* BluePilot root commit **`e1d051d7ba270261b4455068bd68f1a58db15a4a`** and Panda commit **`d994e8e8009d934a94c3a94c863b559118353bdd`**, with the exact stock source hashes in `manifest.json`.
* The MICI settings layout shipped at that revision and an internal SPI-connected H7 Panda for postboot verification. Other device/harness combinations are not established by this release.
* BluePilot already configured and able to identify the truck, then shut down to its normal offroad screen. A stored `CarParamsPersistent` record is required for the vehicle check.
* Working SSH access, sufficient free `/data` space for a separate Panda/safety build and backups (at least 1 GB free recommended), and the existing build tools/dependencies: Python 3.12 venv at `/usr/local/venv/bin/python3`, `git`, `tar`, `scons`, `arm-none-eabi-gcc`, and PyCryptodome. No dependency installation or network downloads are performed by setup.

This is **not** a generic BluePilot/openpilot installer. Do not downgrade, reset files, bypass checks, or mix this with another camera mod to force compatibility. If the exact revision or source check fails, retain the output for a future port. Do not use these instructions to deploy locally edited payload files.

Users with an existing private beta do not need this stock installer. If `check` says the source already matches but lacks this community receipt, retain the earlier private-beta verification and restore tools; the community installer deliberately will not adopt an installation without its own backup.

## What installation changes

The seven camera/controller/UI files in `files/`, the signed H7 firmware artifact, and two launcher conditions are updated. The launcher guards pause activation of staged updates while the camera runtime exists. A `prebuilt` marker prevents automatic startup rebuilding from replacing the custom firmware. Consequently, **normal startup rebuilds and staged update activation are paused during this beta**. Restore before updating BluePilot. All affected original files, modes, absent-file states, firmware, the marker and existing preference are backed up.

The runtime changes only the captured short-length field in `0x227` and the trailer-connection bit in `0x443`, toward camera bus 2. Length precedes connection by 350 ms; both repeat about once per second. An attempt lasts at most eight seconds, with separate native rate/count limits and forwarding leases. Signal cancellation and toggle OFF request eligible baseline cleanup. Unknown/stale inputs or loss of eligibility stop new output. Factory video selection still depends on receiver behavior.

No whole trailer-profile/range/trailer-ID replay is used. Stock steering and braking permission checks are retained. The code still contains legacy experimental helpers, but this runtime uses `LengthAttempt`, not the old direct-view/button strategies.

## 1. Transfer the release from a Mac

Save `ford-camera-community-beta-v0.1.zip` in Downloads. Replace `COMMA_IP` below with the tester's comma IP if different. The truck must be **OFF**, comma powered on its offroad screen, with stable power throughout installation/reboot.

On the Mac:

```bash
scp ~/Downloads/ford-camera-community-beta-v0.1.zip comma@COMMA_IP:/data/
ssh comma@COMMA_IP
```

The following commands run on the comma. Extract this archive into `/data` (it already contains its versioned top-level folder):

```bash
/usr/local/venv/bin/python3 -m zipfile -e \
  /data/ford-camera-community-beta-v0.1.zip /data

cd /data/openpilot
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python3 \
  /data/ford-camera-community-beta-v0.1/setup.py check
```

Expected on a compatible fresh stock system: `READY`. Check creates no installed source/firmware changes. If it says `STOP`, do not continue. If it says `ALREADY INSTALLED`, do not rebuild; go to postboot verification. Keep this versioned directory and its receipts/backups. Re-extracting the release replaces packaged source files, so do not edit them in place.

## 2. Build separately

Still on the comma, truck OFF:

```bash
cd /data/openpilot
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python3 \
  /data/ford-camera-community-beta-v0.1/setup.py prepare
```

Wait for `PREPARED` and the firmware SHA256. Build output remains in `/data/ford-community-build-*/build.log`; `prepared.json` records the exact build. The compiler, linker, required camera symbols, binary/signature relationship and RSA signature are checked. Preparation does not replace active source or firmware. A failure leaves the installed version in place. Do not proceed after an error.

## 3. Install, then reboot

Still truck OFF:

```bash
cd /data/openpilot
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python3 \
  /data/ford-camera-community-beta-v0.1/setup.py deploy &&
sudo reboot
```

The installer rechecks compatibility/offroad state, creates a checksummed backup under `/data/ford-community-camera-backups/`, installs the files, sets the preference OFF and checks fresh Python imports. If a normal installation exception occurs after changes start, it attempts rollback. A power interruption cannot be handled by a running Python process; recovery uses the saved receipt as described below. Reboot only follows a successful deployment.

Normal BluePilot startup handles loading the signed Panda firmware. Setup does not directly change live safety mode or transmit CAN. The UI restart and firmware loading can take time; wait for the normal offroad screen.

## 4. Verify after reboot, with truck still OFF

Reconnect from the Mac:

```bash
ssh comma@COMMA_IP
```

On the comma:

```bash
cd /data/openpilot
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python3 \
  /data/ford-camera-community-beta-v0.1/verify.py
```

This checks all installed source hashes, the saved firmware receipt, imports, startup marker and **the running Panda's signature** via read-only internal SPI requests. It does not construct the normal Panda client, reset the Panda, arm anything, or transmit CAN. Wait for `VERIFIED`. If verification fails or reports a mismatch/unavailable Panda, leave the toggle OFF, preserve the output and restore if needed. Source files matching alone are not proof that the firmware is running.

## 5. Stationary camera test

Use a level, clear stationary test location. Leave any physical trailer connector disconnected and select **No active trailer** in the factory interface. Note the starting range, warnings and cross-traffic setting; keep cross-traffic enabled rather than hiding a warning by turning it off.

1. With the beta toggle OFF, confirm the truck and factory camera interface behave normally.
2. Turn ON **Settings → BluePilot → Vehicle → Turn Signal Blind Spot View**.
3. Remain fully stopped in **Drive**, hold the foot brake, leave the accelerator untouched, and keep assistance inactive. Keep signals OFF for at least three seconds.
4. Select RIGHT for approximately four seconds. Visually identify the actual right mirror feed. Cancel and wait at least three seconds.
5. Select LEFT for approximately four seconds. Visually identify the actual left mirror feed. Cancel and wait at least three seconds.
6. Turn the beta toggle OFF. After releasing/reselecting the signal, confirm no new emulated attempt starts. A physically connected trailer may independently activate the factory feature, which is why it must be disconnected for this comparison.
7. Return to Park before interacting with commands/settings further. Report any warning, wrong/blank feed, unexpected state or range change. Do not enable assistance or begin driving as a test of this stationary release.

A matching `0x3EE` status does not prove correct video. No cross-traffic warning does not prove target detection. A stopped attempt may end after eight seconds even if the signal remains on; cancel and leave a neutral interval before another attempt. Missing baseline/factory configuration may produce no camera even though installation succeeded. Do not change allowlists, safety modes or safeguards to force output.

## Optional receive-only recording

A second SSH connection can run this while the truck is in the stationary test state:

```bash
cd /data/openpilot
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python3 \
  /data/ford-camera-community-beta-v0.1/monitor.py --seconds 35
```

It records only selected camera/trailer/signal CAN frames plus vehicle/control state, with source numbers preserved. There is no arming or CAN transmission by this recorder. It writes `/data/ford-camera-community-YYYYMMDD-HHMMSS.csv`. Use the actual filename it prints to retrieve it from the Mac, for example:

```bash
scp comma@COMMA_IP:/data/ford-camera-community-YYYYMMDD-HHMMSS.csv ~/Downloads/
```

Normal route logs can provide deeper diagnostics. TX-return/echo frames alone do not establish what a receiving module accepted, and forwarded traffic can also appear as TX echoes. The recorder preserves raw source identifiers so these cases can be distinguished during review.

## Disable, uninstall and recovery

The UI toggle OFF disables new emulation attempts. It does not restore source files/firmware or resume updates. To return to the exact pre-installation state, first turn the truck OFF and leave comma powered on the offroad screen. On the comma:

```bash
cd /data/openpilot
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python3 \
  /data/ford-camera-community-beta-v0.1/setup.py restore &&
sudo reboot
```

This restores original source files (removing helpers that were absent), signed firmware, launchers, prebuilt marker and the previous preference. On a supported stock installation it returns those affected items to stock. Preserve the package directory and backup until recovery is verified. Do not delete the runtime by itself; that would leave an incomplete installation.

The same restore action supports a mixture of old/new files left by an interrupted deployment as long as the backup and receipt were successfully written. It refuses unrelated later edits, changed firmware or corrupt backups. If it stops, share the error rather than force overwriting. If SSH/offroad startup is unavailable, use your normal BluePilot/comma recovery/reinstallation procedure; this package cannot guarantee recovery from every power or storage failure.

## Troubleshooting

| Result | Meaning/action |
|---|---|
| Unsupported revision | Wrong BluePilot or Panda commit. Stop; request a reviewed port. |
| Expected exact stock source | A previous camera mod or another edit is present. Stop; use that mod's original restore procedure first if appropriate. Do not blindly reset. |
| Missing existing build tool | Save output. This package does not install tools or alter the device OS. |
| No stored vehicle identification | Configure/identify the vehicle using normal BluePilot, then turn it OFF and rerun check. |
| Source already matches, no community receipt | Existing private beta. No reinstall needed; use its existing verification/restore tools. |
| ALREADY INSTALLED | Community source and saved firmware already match. Run postboot verification instead of rebuilding. |
| Import/build/signature failure | Do not test. Save full output/build log; check whether deployment rolled back. |
| VERIFIED, no camera | Check toggle, valid CAN, stationary Drive, brake held, inactive assistance, signals neutral first, no real trailer/profile and factory camera capability. Capture evidence; do not weaken checks. |
| Cross-traffic warning/range change | Stop the attempt, turn toggle OFF, record exact text/state; do not hide it by disabling cross-traffic. |

## Evidence and feedback

Use `docs/FEEDBACK.md`. Include model year/trim, device/harness, exact revisions, settings/factory camera capability, verification output, correct/blank/wrong feed for each side, exit behavior, warnings, starting/ending range and capture filename. Redact VIN, account details and identifying location data before sharing full logs. Do not post private SSH keys or credentials. Share only the data needed to reproduce the result.

`docs/VALIDATION.md` records what was actually tested and what remains unverified. `checksums.json` covers packaged files for integrity comparison; it is not an independent publisher signature. Keep upstream copyright/license notices with redistributed source and dependencies. This release does not include prerecorded vehicle logs, credentials, compiled Panda firmware or a general-purpose CAN sender. It builds the firmware locally from the pinned checkout.
