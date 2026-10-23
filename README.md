# Mechintel firmware

Tested firmware builds for Mechintel flight controllers, and the list the **amidFly app** reads to
offer them in its Firmware Flasher (Tools → Firmware Flasher → Online).

- `manifest.json` — the list the app reads. **Editing it changes what customers can flash**, so
  treat changes like a release.
- `boards/<board>/` — notes and a changelog per board.
- Firmware files (`.hex`) are attached to **GitHub Releases**, not committed to the repo.
- `tools/check_manifest.py` — checks the list; also runs automatically on GitHub for every change.

The app reads `https://raw.githubusercontent.com/mechinteldynamics/mechintel-firmware/main/manifest.json`. Changes reach
users within about 5–15 minutes (GitHub's cache plus the app's own), with no app update. This repo
must stay **public**: the app downloads without logging in.

## Publishing a new build

1. **Build** the firmware `.hex` (for ArduPilot, the `*_with_bl.hex`, not `.apj`).
2. **Get its CRC** (of the flashed image, not of the .hex text):
   ```
   python tools/check_manifest.py crc inav_9.1.0_VAJRAF4.hex
   ```
3. **Create a GitHub Release** named and tagged `<board>-<firmware>-<version>`, e.g.
   `vajra-f4-inav-9.1.0`, and attach the `.hex`. Write the release notes there. Tick
   "Set as a pre-release" for beta builds.
4. **Add an entry to `manifest.json`** under the board's `firmware` list:
   ```json
   {
     "family": "INAV",
     "version": "9.1.0",
     "url": "https://github.com/mechinteldynamics/mechintel-firmware/releases/download/vajra-f4-inav-9.1.0/inav_9.1.0_VAJRAF4.hex",
     "crc32": "0x595E5931",
     "channel": "stable",
     "recommended": true,
     "date": "2026-10-20",
     "notes": "First release for VAJRA F4.",
     "notesUrl": "https://github.com/mechinteldynamics/mechintel-firmware/releases/tag/vajra-f4-inav-9.1.0"
   }
   ```
   Move `"recommended": true` off the previous build of the same firmware (one per firmware family).
5. **Check it**: `python tools/check_manifest.py` (downloads every build and verifies its CRC).
6. **Commit and push**, ideally through a pull request so someone else reviews it. The GitHub check
   must pass before merging.

To withdraw a bad build, remove its entry from `manifest.json` (keep the GitHub Release for the
record). To roll back, move `recommended` to the previous build.

## manifest.json fields

Board: `id` (stable, e.g. `vajra-f4`), `name` (shown to users), `mcu` (`STM32F405`; the only MCU the
Bluetooth bridge can flash today), `match` (names the board reports over MSP, compared ignoring
case, spaces, `_` and `-`), `firmware` (list of builds, can be empty).

Build: `family` (`INAV`, `Betaflight` or `ArduPilot`), `version`, `url` (https), and optionally
`title` (defaults to "<family> <version>"), `crc32` (strongly recommended: the app refuses a download
that doesn't match), `channel` (`stable` or `beta`; beta shows only with "Show beta builds"),
`recommended`, `date`, `notes`, `notesUrl`.

## Adding a new board

Add an object to `boards` (unique `id`, its `match` names), create `boards/<id>/README.md`, and
publish releases named `<id>-<firmware>-<version>`.
