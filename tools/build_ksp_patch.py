#!/usr/bin/env python3
"""Build KSCON (KeyStep Con): KeyStep Pro firmware 2.5.20 with project names + step pads, reporting 2.5.99,
and the display chip's startup screen redrawn as KEYSTEP CON (boot_logo.py).

Names hooks (tools/name_hooks.S) as in build_names_patch.py, plus the pad hooks
(tools/pad_hooks.S) on the event loop's button press/release calls.
Requires clang with an ARM target. Output stays under ignored firmware/.
This tool never contacts or writes to a device.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

from boot_logo import patch_ui
from firmware_models import CHROMA_ADDRESSES, CHROMA_LED_FLUSH_CALLS, DISPLAY_PATHS, FOREGROUND_PATHS, MODELS, TEMPO_PATHS, model_address
from build_names_patch import (
    BASE, FLASH_LIMIT, KSPF, ROOT, SET_DISPATCH, TITLE_CALL, TITLE_FORMATTER,
    decode_thumb_b_w, decode_thumb_bl, elf_text_and_symbols, thumb_branch,
)

PRESS_CALL = 0x08012708      # bl 080500d8 (button press) in the event loop 08012338
RELEASE_CALL = 0x080126EA    # bl 0804e700 (button release)
SAVE_CALL = 0x08047D36       # bl 080475d8 (program the second sector) in Save Project 08047c84
SECTOR_WRITE = 0x080475D8
KEY_SEND_CALL = 0x080156F6   # bl 0801a6e0: a key's note on, in the event loop
MIDI_SEND = 0x0801A6E0
KEY_REC_CALL = 0x08015EE0    # bl 080108a4: live key record, in the event loop
LED_FLUSH = 0x08054C2C
LED_FLUSH_CALLS = (0x0800E328, 0x0800E84A, 0x0801696A, 0x0801F7BE, 0x0802A88C, 0x0802B876, 0x08030BD6)   # every bl to it
STOCK_KEY_REC = 0x080108A4
STOCK_PRESS = 0x080500D8
STOCK_RELEASE = 0x0804E700
# version: the SysEx identity reply builds it from immediates (movs r3,#build / #patch / #minor, major 2 in r2) at
# 0x080181D2/D8/DE, which MCC shows as $3.$2.$1. Patched builds say 2.5.99 so they are not mistaken for stock 2.5.20
# (99 is above MCC's minimum 2.5.14 compared as numbers or as text); the build byte counts our builds.
ID_BUILD_IMM, ID_PATCH_IMM = 0x080181D2, 0x080181D8
PATCH_VERSION = 99
PATCH_BUILD = 13              # scale tempo timeouts to the application's 100us tick
VERSION_TEXT_PTR = 0x080589A4  # Utility > FW version text, stock "Firmware version :\n2.5.20\nbuild 2085"
STOCK_VERSION_TEXT = 0x0805AF3C
SOURCES = [ROOT / "tools/name_hooks.S", ROOT / "tools/pad_hooks.S", ROOT / "tools/tempo_hooks.S"]
C_SOURCES = [ROOT / "tools/bass_gen.c", ROOT / "tools/note_show.c", ROOT / "tools/tempo_control.c"]


def model_source(source: str, model: str) -> str:
    """Keep upstream hook sources readable, with an explicit checked Chroma map."""
    if model == "original":
        return source
    if model != "chroma":
        raise ValueError(f"unsupported model: {model}")
    code = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    code = re.sub(r"(?m)//.*$|@.*$", "", code)
    for number in re.findall(r"0x[0-9a-fA-F]+", code):
        address = int(number, 16)
        if 0x08008000 <= address < 0x08080000:
            address &= ~1
        if 0x08008000 <= address < 0x08080000 and address not in CHROMA_ADDRESSES:
            raise ValueError(f"unmapped firmware address in Chroma source: {number}")
        if 0x20000000 <= address < 0x20010000 and address not in CHROMA_ADDRESSES:
            raise ValueError(f"unmapped RAM address in Chroma source: {number}")

    def translate(match):
        value = int(match[0], 16)
        if value == 0xFEC:
            return "0x1000"
        translated = model_address(value, model)
        return hex(translated) if translated != value else match[0]

    return re.sub(r"0x[0-9a-fA-F]+", translate, source)


def c_to_asm(path: Path, temp: Path, model: str = "original") -> str:
    """clang -fropi: constant data is reached PC-relative, so it can sit in .text with the code (the build
    takes .text only and does not link). Any call to a symbol the file does not define (memset and
    friends) would be left unresolved, so it is refused."""
    out = temp / (path.stem + ".s")
    source_path = path
    if model != "original":
        source_path = temp / path.name
        source_path.write_text(model_source(path.read_text(), model))
    subprocess.run(["clang", "--target=arm-none-eabi", "-mcpu=cortex-m7", "-mthumb", "-mfloat-abi=soft", "-Os",
                    "-I", str(ROOT / "tools"),
                    "-ffreestanding", "-fno-builtin", "-fropi", "-fno-jump-tables", "-fno-exceptions",
                    "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-S", str(source_path), "-o", str(out)], check=True)
    lines = []
    for line in out.read_text().splitlines():
        t = line.strip()
        if t.startswith((".section", ".data", ".bss")):
            if ".note.GNU-stack" in t:
                continue
            if not t.startswith(".section\t.text") and not t.startswith(".section .text"):
                if ".rodata" not in t:
                    raise SystemExit(f"{path.name}: writable data is not supported in the hook block: {t}")
            line = "\t.text"
        if t.startswith((".globl", ".global")):     # global symbols get relocations; the build does not link
            continue
        if t.startswith((".file", ".ident", ".addrsig", ".eabi_attribute", ".syntax", ".cpu", ".fpu", ".arch")):
            continue
        lines.append(line)
    text = "\n".join(lines)
    # each file's compiler-made local labels (.LBB0_1, .LCPI0_0, ...) get the file's name, so they do not clash
    text = re.sub(r"\.L([A-Za-z_$][\w$]*)", lambda m: f".L{path.stem}_{m.group(1)}", text)
    defined = set(re.findall(r"^([A-Za-z_.$][\w.$]*):", text, re.M))
    called = set(re.findall(r"^\s*(?:bl|blx|b|b\.w)\s+([A-Za-z_][\w.$]*)\s*$", text, re.M))
    called = {c for c in called if not re.fullmatch(r"r\d+|lr|ip|sp|pc", c)}
    if called - defined:
        raise SystemExit(f"{path.name} calls {sorted(called - defined)}: no library in the hook block")
    return "\n.balign 4\n.thumb\n" + text + "\n.balign 4\n"


def assemble(address: int, model: str = "original") -> tuple[bytes, dict[str, int]]:
    with tempfile.TemporaryDirectory(prefix="ksp-build-") as temp:
        temp_path = Path(temp)
        source = (f".equ HOOK_IMAGE_ADDRESS, {address:#x}\n" + "\n".join(model_source(p.read_text(), model) for p in SOURCES)
                  + "".join(c_to_asm(p, temp_path, model) for p in C_SOURCES))
        asm_path, obj_path = temp_path / "hooks.S", temp_path / "hooks.o"
        asm_path.write_text(source)
        subprocess.run(["clang", "--target=arm-none-eabi", "-mcpu=cortex-m7", "-mthumb",
                        "-I", str(ROOT / "tools"),
                        "-c", str(asm_path), "-o", str(obj_path)], check=True)
        if relocations(obj_path):
            raise SystemExit(f"unresolved references in the hook block: {relocations(obj_path)} (the build does not link)")
        return elf_text_and_symbols(obj_path)


def relocations(path: Path) -> list[str]:
    """names of non-empty relocation sections: the build copies .text as is, so there must be none"""
    data = path.read_bytes()
    shoff = struct.unpack_from("<I", data, 32)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 46)
    sections = [struct.unpack_from("<IIIIIIIIII", data, shoff + i * shentsize) for i in range(shnum)]
    names = data[sections[shstrndx][4]:sections[shstrndx][4] + sections[shstrndx][5]]
    name = lambda sec: names[sec[0]:names.find(b"\0", sec[0])].decode()
    return [name(sec) for sec in sections if sec[1] in (4, 9) and sec[5] and name(sec).endswith(".text")]


def version_text() -> str:
    return f"Firmware version :\nKSCON 2.5.{PATCH_VERSION} b{PATCH_BUILD}\nbased on 2.5.20"


def build(stock_bin: bytes, model: str = "original") -> tuple[bytearray, dict[str, int], int]:
    raw = MODELS[model].validate_stock(stock_bin)
    addr = lambda a: model_address(a, model)
    led_calls = CHROMA_LED_FLUSH_CALLS if model == "chroma" else LED_FLUSH_CALLS
    tempo = MODELS[model]
    paths = TEMPO_PATHS[model]
    foreground = FOREGROUND_PATHS[model]
    length_word = struct.unpack_from("<I", stock_bin, 4)[0]
    if length_word >> 8 != len(raw) or len(raw) != MODELS[model].payload_size:
        raise SystemExit(f"unexpected 2.5.20 image size: {len(raw):#x}")
    hook_address = (BASE + len(raw) + 3) & ~3
    hooks, symbols = assemble(hook_address, model)
    if symbols.get("title_hook", 2) & ~1 != 0:
        raise SystemExit("title_hook must stay at the start of the hook block")
    if hook_address + len(hooks) > min(FLASH_LIMIT, 0x0807FFF8):
        raise SystemExit("hooks exceed internal flash range")
    site = lambda a: raw[a - BASE:a - BASE + 4]
    if site(addr(TITLE_CALL)) != thumb_branch(addr(TITLE_CALL), addr(TITLE_FORMATTER), True):
        raise SystemExit("project-title formatter call changed; refusing stale patch")
    if site(addr(SET_DISPATCH)) != bytes.fromhex("3a462146"):
        raise SystemExit("project item dispatch changed; refusing stale patch")
    if decode_thumb_bl(addr(PRESS_CALL), site(addr(PRESS_CALL))) != addr(STOCK_PRESS):
        raise SystemExit("button press call changed; refusing stale patch")
    if decode_thumb_bl(addr(RELEASE_CALL), site(addr(RELEASE_CALL))) != addr(STOCK_RELEASE):
        raise SystemExit("button release call changed; refusing stale patch")
    if decode_thumb_bl(addr(SAVE_CALL), site(addr(SAVE_CALL))) != addr(SECTOR_WRITE):
        raise SystemExit("save project sector write changed; refusing stale patch")
    if decode_thumb_bl(addr(KEY_SEND_CALL), site(addr(KEY_SEND_CALL))) != addr(MIDI_SEND):
        raise SystemExit("key note-on send changed; refusing stale patch")
    if decode_thumb_bl(addr(KEY_REC_CALL), site(addr(KEY_REC_CALL))) != addr(STOCK_KEY_REC):
        raise SystemExit("key record call changed; refusing stale patch")
    for call in led_calls:
        if decode_thumb_bl(call, site(call)) != addr(LED_FLUSH):
            raise SystemExit(f"LED send call at {call:#x} changed; refusing stale patch")
    stock_build = 119 if model == "chroma" else 37
    if site(addr(ID_BUILD_IMM))[:2] != bytes((stock_build, 0x23)) or site(addr(ID_PATCH_IMM))[:2] != bytes((0x14, 0x23)):
        raise SystemExit("identity version immediates changed; refusing stale patch")
    if struct.unpack_from("<I", raw, addr(VERSION_TEXT_PTR) - BASE)[0] != addr(STOCK_VERSION_TEXT):
        raise SystemExit("firmware version text pointer changed; refusing stale patch")
    for call in (tempo.encoder_up, tempo.encoder_down):
        if site(call) != bytes.fromhex("9df86a60"):
            raise SystemExit(f"encoder dispatch changed at {call:#x}")
    for source, target in ((paths["usb_rx_call"], paths["byte_parser"]),
                           (paths["boot_call"], paths["sdram_init"]),
                           (foreground["call"], foreground["update"])):
        if decode_thumb_bl(source, site(source)) != target:
            raise SystemExit(f"tempo receive/startup call changed at {source:#x}")
    for source, expected, _hook in DISPLAY_PATHS[model]:
        if raw[source - BASE:source - BASE + len(bytes.fromhex(expected))] != bytes.fromhex(expected):
            raise SystemExit(f"BPM display loads changed at {source:#x}")

    at = lambda name: (hook_address + symbols[name]) & ~1
    patched = bytearray(raw)
    patches = [(addr(TITLE_CALL), hook_address, True), (addr(SET_DISPATCH), at("setname_hook"), False),
               (addr(PRESS_CALL), at("pad_press"), True), (addr(RELEASE_CALL), at("pad_release"), True),
               (addr(SAVE_CALL), at("chord_save"), True), (addr(KEY_SEND_CALL), at("key_send"), True),
               (addr(KEY_REC_CALL), at("key_rec"), True)] + [(c, at("led_flush"), True) for c in led_calls]
    patches += [(tempo.encoder_up, at("tempo_up"), False), (tempo.encoder_down, at("tempo_down"), False),
                (paths["usb_rx_call"], at("tempo_receive"), True), (paths["boot_call"], at("tempo_boot"), True),
                (foreground["call"], at("tempo_foreground"), True)]
    for source, target, link in patches:
        patched[source - BASE:source - BASE + 4] = thumb_branch(source, target, link)
        decode = decode_thumb_bl if link else decode_thumb_b_w
        if decode(source, patched[source - BASE:source - BASE + 4]) != target:
            raise SystemExit(f"branch at {source:#x} does not reach {target:#x}")
    for source, expected, hook in DISPLAY_PATHS[model]:
        count = len(bytes.fromhex(expected))
        patched[source - BASE:source - BASE + count] = thumb_branch(source, at(hook), False) + bytes.fromhex("00bf") * ((count - 4) // 2)
        if decode_thumb_b_w(source, patched[source - BASE:source - BASE + 4]) != at(hook):
            raise SystemExit(f"BPM display branch at {source:#x} does not reach {hook}")
    patched[addr(ID_BUILD_IMM) - BASE] = PATCH_BUILD & 0x7F
    patched[addr(ID_PATCH_IMM) - BASE] = PATCH_VERSION
    patched.extend(b"\xff" * (hook_address - BASE - len(patched)))
    patched.extend(hooks)
    while len(patched) % 4:
        patched.append(0)
    text_address = BASE + len(patched)
    patched.extend(version_text().encode("ascii") + b"\0")
    while len(patched) % 4:
        patched.append(0)
    if BASE + len(patched) > min(FLASH_LIMIT, 0x0807FFF8):
        raise SystemExit("hooks and version text exceed internal flash range")
    struct.pack_into("<I", patched, addr(VERSION_TEXT_PTR) - BASE, text_address)

    out = bytearray(stock_bin[:64]) + patched
    struct.pack_into("<I", out, 4, (len(patched) << 8) | (length_word & 0xFF))
    out[9] = -sum(out[64:]) & 0xFF
    out[63] = -sum(out[:63]) & 0xFF
    if sum(out[:64]) & 0xFF or (sum(out[64:]) + out[9]) & 0xFF:
        raise SystemExit("patched checksum mismatch")
    return out, {k: hook_address + v for k, v in symbols.items()}, hook_address


def metadata_version(data: bytes) -> bytes:
    stock = b'"version_number": "2.5.20"'
    if data.count(stock) != 1:
        raise ValueError("stock metadata version must match exactly once")
    return data.replace(stock, f'"version_number": "2.5.{PATCH_VERSION}"'.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "firmware/patched")
    parser.add_argument("--model", choices=("both", "original", "chroma"), default="both")
    args = parser.parse_args()
    if hashlib.sha256(KSPF.read_bytes()).hexdigest() != "a01b3d9909182e2b284074469d7bace6862587bfa7ffc2c8730d23aae51dfb32":
        raise SystemExit("unsupported stock package hash")
    with zipfile.ZipFile(KSPF) as archive:
        entries = [(item, archive.read(item.filename)) for item in archive.infolist()]
    contents = {item.filename: data for item, data in entries}
    selected = tuple(MODELS) if args.model == "both" else (args.model,)
    outputs = {}
    report = {"models": {}, "version": f"2.5.{PATCH_VERSION}", "build": PATCH_BUILD,
              "stock_sha256": hashlib.sha256(KSPF.read_bytes()).hexdigest()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in selected:
        model = MODELS[name]
        out, _symbols, hook_address = build(contents[model.main_entry], name)
        outputs[model.main_entry] = bytes(out)
        outputs[model.ui_entry] = patch_ui(contents[model.ui_entry])
        output_bin = args.output_dir / ("kscon_" + model.main_entry)
        output_bin.write_bytes(out)
        report["models"][name] = {
            "model_header": f"{model.model_header:#010x}", "hook_address": f"{hook_address:#010x}",
            "main_entry": model.main_entry, "ui_entry": model.ui_entry,
            "main_sha256": hashlib.sha256(out).hexdigest(),
            "ui_sha256": hashlib.sha256(outputs[model.ui_entry]).hexdigest(),
        }
    suffix = "" if args.model == "both" else "_" + args.model
    output_kspf = args.output_dir / f"KSCON_2.5.{PATCH_VERSION}_build{PATCH_BUILD}{suffix}.kspf"
    with zipfile.ZipFile(output_kspf, "w") as archive:
        for item, data in entries:
            if item.filename == "info.json":
                data = metadata_version(data)
            archive.writestr(item, outputs.get(item.filename, data))
    with zipfile.ZipFile(output_kspf) as archive:
        if any(archive.read(name) != data for name, data in outputs.items()) or archive.testzip() is not None:
            raise SystemExit("rebuilt package check failed")
    report["package_sha256"] = hashlib.sha256(output_kspf.read_bytes()).hexdigest()
    (output_kspf.with_suffix(".json")).write_text(json.dumps(report, indent=2) + "\n")
    print(f"verified model images: {', '.join(selected)}")
    print(f"reports version 2.5.{PATCH_VERSION} build {PATCH_BUILD}; menu text {version_text()!r}")
    print(f"candidate package: {output_kspf}")
    print("No device was contacted or written.")


if __name__ == "__main__":
    main()
