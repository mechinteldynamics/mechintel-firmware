#!/usr/bin/env python3
"""
Check manifest.json before publishing (also runs automatically on GitHub for every change).

    python tools/check_manifest.py              # structure + download every build and verify its CRC
    python tools/check_manifest.py --offline    # structure only (no downloads)
    python tools/check_manifest.py crc FILE.hex # print the crc32 to put in the manifest

Standard library only. The HEX → image conversion and CRC are the same as the amidFly app
(src/services/FirmwareImage.ts) and the bridge's tools/stm32_ble_flash.py.
"""

import argparse
import json
import sys
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"

FAMILIES = {"INAV", "Betaflight", "ArduPilot"}
CHANNELS = {"stable", "beta"}
# What the ESP32-C3 bridge can flash today.
MCU_FLASH = {"STM32F405": (0x08000000, 1024 * 1024)}
DEFAULT_FLASH = MCU_FLASH["STM32F405"]


# ------------------------------------------------------------------ image + crc

def hex_to_image(text):
    """Intel HEX -> (base, image). Gaps filled with 0xFF. Raises ValueError on bad input."""
    chunks = {}
    upper = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if not line.startswith(":"):
            raise ValueError(f"line {lineno}: not an Intel HEX record")
        rec = bytes.fromhex(line[1:])
        if sum(rec) & 0xFF:
            raise ValueError(f"line {lineno}: bad checksum")
        count, addr, rtype = rec[0], (rec[1] << 8) | rec[2], rec[3]
        data = rec[4:4 + count]
        if rtype == 0x00:
            chunks[upper + addr] = data
        elif rtype == 0x01:
            break
        elif rtype == 0x02:
            upper = int.from_bytes(data, "big") << 4
        elif rtype == 0x04:
            upper = int.from_bytes(data, "big") << 16
    if not chunks:
        raise ValueError("no data records")
    base = min(chunks)
    end = max(a + len(d) for a, d in chunks.items())
    image = bytearray(b"\xff" * (end - base))
    for a, d in chunks.items():
        image[a - base:a - base + len(d)] = d
    return base, bytes(image)


def load_image(name, raw):
    if name.lower().endswith(".hex") or raw[:1] == b":":
        return hex_to_image(raw.decode("ascii", errors="replace"))
    return DEFAULT_FLASH[0], raw


def crc_hex(image):
    return f"0x{zlib.crc32(image) & 0xFFFFFFFF:08X}"


# ------------------------------------------------------------------ checks

def check(offline):
    errors, warnings = [], []
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"manifest.json is not valid JSON: {e}")
        return 1

    if manifest.get("schema") != 1:
        errors.append("schema must be 1")
    boards = manifest.get("boards")
    if not isinstance(boards, list):
        print("manifest.json: 'boards' must be a list")
        return 1

    seen_ids, seen_match = set(), {}
    for b in boards:
        where = f"board {b.get('id', '?')}"
        for key in ("id", "name", "match", "firmware"):
            if key not in b:
                errors.append(f"{where}: missing '{key}'")
        if b.get("id") in seen_ids:
            errors.append(f"{where}: duplicate id")
        seen_ids.add(b.get("id"))
        flash = MCU_FLASH.get(b.get("mcu", "STM32F405"))
        if flash is None:
            warnings.append(f"{where}: mcu {b.get('mcu')} can't be flashed by the bridge yet")
            flash = DEFAULT_FLASH
        for m in b.get("match", []):
            key = "".join(ch for ch in str(m).upper() if ch not in " _-")
            if key in seen_match and seen_match[key] != b.get("id"):
                errors.append(f"{where}: match '{m}' is also used by board {seen_match[key]}")
            seen_match[key] = b.get("id")

        recommended = {}
        urls = set()
        for i, f in enumerate(b.get("firmware", [])):
            fw = f"{where} / firmware[{i}] {f.get('family', '?')} {f.get('version', '?')}"
            for key in ("family", "version", "url"):
                if not f.get(key):
                    errors.append(f"{fw}: missing '{key}'")
            if f.get("family") and f["family"] not in FAMILIES:
                errors.append(f"{fw}: family must be one of {sorted(FAMILIES)}")
            if f.get("channel", "stable") not in CHANNELS:
                errors.append(f"{fw}: channel must be 'stable' or 'beta'")
            url = f.get("url", "")
            if url and not url.startswith("https://"):
                errors.append(f"{fw}: url must start with https://")
            if url in urls:
                errors.append(f"{fw}: same url listed twice")
            urls.add(url)
            if url.lower().endswith(".apj"):
                errors.append(f"{fw}: .apj can't be flashed; use the ArduPilot *_with_bl.hex")
            if f.get("recommended"):
                if f.get("family") in recommended:
                    errors.append(f"{fw}: more than one recommended {f['family']} build")
                recommended[f.get("family")] = True
                if f.get("channel") == "beta":
                    warnings.append(f"{fw}: a beta build is marked recommended")
            if "crc32" not in f:
                warnings.append(f"{fw}: no crc32 (the app can't detect a corrupted download)")

            if offline or not url.startswith("https://"):
                continue
            print(f"  downloading {url} ...")
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    raw = r.read()
                base, image = load_image(url.split("?")[0], raw)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{fw}: couldn't download/parse: {e}")
                continue
            start, size = flash
            if base < start or base + len(image) > start + size or base % 4:
                errors.append(f"{fw}: image 0x{base:08X}+{len(image)} doesn't fit the {b.get('mcu', 'STM32F405')} flash")
            actual = crc_hex(image)
            if "crc32" in f and int(str(f["crc32"]), 16) != int(actual, 16):
                errors.append(f"{fw}: crc32 is {f['crc32']} in the manifest but the file is {actual}")
            else:
                print(f"    ok: {len(image)} bytes at 0x{base:08X}, crc {actual}")

    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    builds = sum(len(b.get("firmware", [])) for b in boards)
    print(f"{len(boards)} board(s), {builds} build(s): {'FAILED' if errors else 'OK'}")
    return 1 if errors else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="skip downloading builds")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("crc", help="print the crc32 of a .hex/.bin for the manifest")
    c.add_argument("file")
    args = ap.parse_args()

    if args.cmd == "crc":
        path = Path(args.file)
        base, image = load_image(path.name, path.read_bytes())
        print(f"{crc_hex(image)}  ({len(image)} bytes at 0x{base:08X})")
        return 0
    return check(args.offline)


if __name__ == "__main__":
    sys.exit(main())
