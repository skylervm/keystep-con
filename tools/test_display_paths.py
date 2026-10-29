"""Qualify the stock renderer's scratch-slot lifetime before inserting feedback."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP
from build_names_patch import decode_thumb_bl, elf_text_and_symbols
from firmware_models import MODELS, TEMPO_PATHS, model_address
from test_tempo_hooks import Fixture, BASE, STACK, HEARTBEAT

OWNER, DISPLAY = 0x20030000, 0x20050000
FORMAT = 0x20041000
RENDERERS = {"original": 0x08026624, "chroma": 0x08026930}
VIEWS = {
    0: {"offset": -0x134, "data": 0x1A, "frame": 80, "work": 16, "armed": 0x2A,
        "cache_project": 0x110, "format": b"%s BPM\0",
        "calls": {"data": 0x12, "begin": 0x26, "title": 0x64, "big": 0xC0,
                  "clear": 0xCE, "done": 0x102, "finish": 0x11A}},
    1: {"offset": 0, "data": 0x20, "frame": 72, "work": 8, "armed": 0x26,
        "cache_project": 0x116, "format": b"%d.%.2u BPM\0",
        "calls": {"data": 0xC, "begin": 0x22, "title": 0x5E, "big": 0xAE,
                  "clear": 0xBE, "done": 0xD4, "finish": 0xEA}},
}


def setup_renderer(f, stock=True, view=1):
    raw = MODELS[f.name].read_stock(Path(__file__).resolve().parents[1] / "firmware")
    if stock:
        f.uc.mem_write(BASE, raw)
    info = VIEWS[view]
    entry = RENDERERS[f.name] + info["offset"]
    page = 0x20002C7C if f.name == "original" else 0x20002C9C
    source = OWNER + info["data"]
    f.put(model_address(0x20001510, f.name), OWNER)
    f.put(OWNER, page)
    f.uc.mem_write(OWNER + 0xC, bytes([view]))
    f.uc.mem_write(source, b"\x01\0" + struct.pack("<H", 12000) + b"\0")
    f.put(page + 0x10, model_address(0x0805AE68, f.name))
    f.put(page + 0x14, FORMAT)
    f.uc.mem_write(FORMAT, info["format"])
    f.put(model_address(0x200017F8, f.name), DISPLAY)
    call = lambda offset: decode_thumb_bl(entry + offset, raw[entry + offset - BASE:entry + offset - BASE + 4])
    targets = {name: call(offset) for name, offset in info["calls"].items()}
    captured = []

    def read_string(pointer):
        data = bytes(f.uc.mem_read(pointer, 100))
        return data.split(b"\0", 1)[0].decode("ascii")

    def driver(u, address, _size, _data):
        if address == model_address(0x0803F774, f.name):
            count = u.reg_read(UC_ARM_REG_R3) * 2
            assert count == 16, "unexpected name-flash read"
            u.mem_write(u.reg_read(UC_ARM_REG_R2), b"\xff" * count)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        if address not in targets.values():
            return
        if address == targets["data"]:
            return  # Run the real stock owner-data accessor.
        result = 1 if address == targets["begin"] else 0
        if address in (targets["title"], targets["big"]):
            captured.append(("title" if address == targets["title"] else "bpm", read_string(u.reg_read(UC_ARM_REG_R1))))
        u.reg_write(UC_ARM_REG_R0, result)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    f.uc.hook_add(UC_HOOK_CODE, driver)
    return entry, source, captured


class DisplayPaths(unittest.TestCase):
    def test_native_refresh_from_deeper_rx_context_is_asynchronous(self):
        # A test-only trampoline adds a full register frame to the actual RX
        # call chain. It does not alter a firmware artifact or contact hardware.
        for name in MODELS:
            for page in (0, 1):
                with self.subTest(model=name, page=page):
                    f = Fixture(name)
                    setup_renderer(f, stock=False, view=page)
                    for offset in (0x30, 0x44, 0x52, 0x7F):
                        f.uc.mem_write(OWNER + offset, b"\xa5")
                    before = bytes(f.uc.mem_read(OWNER, 256))
                    f.uc.mem_write(0x20020000 + 0x8E2, b"\x01")
                    f.uc.mem_write(0x20020000 + 0xC, b"\0")
                    site = TEMPO_PATHS[name]["usb_rx_call"]
                    wrapper = decode_thumb_bl(site, f.raw[site-BASE:site-BASE+4])
                    c_entry = decode_thumb_bl(wrapper+4, f.raw[wrapper+4-BASE:wrapper+8-BASE])
                    refresh = model_address(0x0802546C if page == 0 else 0x08025494, name)
                    assembly = f""".syntax unified
.thumb
.text
push.w {{r0-r12,lr}}
ldr r0, ={DISPLAY}
mov.w r1, #-1
ldr r12, ={refresh | 1}
blx r12
pop.w {{r0-r12,lr}}
ldr pc, ={c_entry | 1}
.ltorg
"""
                    out = Path(__file__).resolve().parents[1] / "out"
                    out.mkdir(exist_ok=True)
                    with tempfile.TemporaryDirectory(dir=out) as tmp:
                        src, obj = Path(tmp)/"probe.S", Path(tmp)/"probe.o"
                        src.write_text(assembly)
                        subprocess.run(["clang", "--target=arm-none-eabi", "-mcpu=cortex-m7",
                                        "-mthumb", "-c", str(src), "-o", str(obj)], check=True)
                        code, _symbols = elf_text_and_symbols(obj)
                    trampoline = 0x0807E000
                    f.uc.mem_write(trampoline, code)
                    injected, renders, depth = [False], [], [0]
                    renderers = (0x080264F0, 0x08026624) if name == "original" else (0x080267FC, 0x08026930)

                    def trace(u, address, _size, _data):
                        depth[0] = max(depth[0], STACK-u.reg_read(UC_ARM_REG_SP))
                        if address in renderers:
                            renders.append(address)
                        if address == c_entry and u.reg_read(UC_ARM_REG_R1) == 0xF7 and not injected[0]:
                            injected[0] = True
                            u.reg_write(UC_ARM_REG_PC, trampoline | 1)

                    f.uc.hook_add(UC_HOOK_CODE, trace)
                    f.usb(HEARTBEAT)
                    self.assertTrue(injected[0])
                    self.assertEqual(renders, [])
                    self.assertEqual(bytes(f.uc.mem_read(OWNER, 256)), before)
                    self.assertIn(renderers[page] | 1, (f.word(DISPLAY+0x10), f.word(DISPLAY+0x28)))
                    self.assertLess(depth[0], 1024)

    def test_native_refresh_only_queues_without_touching_edit_state(self):
        for name in MODELS:
            for page in (0, 1):
                with self.subTest(model=name, page=page):
                    f = Fixture(name)
                    setup_renderer(f)
                    f.uc.mem_write(OWNER + 0xC, bytes([page]))
                    for offset in (0x30, 0x44, 0x52, 0x7F):
                        f.uc.mem_write(OWNER + offset, b"\xa5")
                    before = bytes(f.uc.mem_read(OWNER, 256))
                    f.uc.mem_write(0x20020000 + 0x8E2, b"\x01")  # Internal clock.
                    f.uc.mem_write(0x20020000 + 0xC, b"\0")     # Stopped.
                    render_calls, stack_depth = [], [0]
                    renderers = (0x080264F0, 0x08026624) if name == "original" else (0x080267FC, 0x08026930)

                    def trace(u, address, _size, _data):
                        stack_depth[0] = max(stack_depth[0], STACK - u.reg_read(UC_ARM_REG_SP))
                        if address in renderers:
                            render_calls.append(address)

                    f.uc.hook_add(UC_HOOK_CODE, trace)
                    refresh = model_address(0x0802546C if page == 0 else 0x08025494, name)
                    f.call(refresh, DISPLAY, 0xFFFFFFFF)
                    self.assertEqual(render_calls, [])
                    self.assertEqual(bytes(f.uc.mem_read(OWNER, 256)), before)
                    self.assertIn(renderers[page] | 1, (f.word(DISPLAY + 0x10), f.word(DISPLAY + 0x28)))
                    self.assertLess(stack_depth[0], 256)

    def test_descriptor_slot_is_dead_and_source_record_is_read_only(self):
        for name in MODELS:
            for view, info in VIEWS.items():
                for project_cached in (0, 1):
                    with self.subTest(model=name, view=view, project_cached=project_cached):
                        f = Fixture(name)
                        entry, source, captured = setup_renderer(f, view=view)
                        f.uc.mem_write(source + 4, b"\x01")
                        f.uc.mem_write(DISPLAY + info["cache_project"], bytes([project_cached]))
                        armed = [False]
                        accesses, source_writes = [], []
                        slot = STACK - info["frame"] + info["work"]

                        def code(_u, address, _size, _data):
                            if address == entry + info["armed"]:
                                armed[0] = True

                        def memory(u, access, address, size, _value, _data):
                            if armed[0] and address < slot + 8 and address + size > slot:
                                accesses.append((hex(u.reg_read(UC_ARM_REG_PC)), hex(address)))
                            if armed[0] and access == UC_MEM_WRITE and address < source + 5 and address + size > source:
                                source_writes.append(hex(u.reg_read(UC_ARM_REG_PC)))

                        f.uc.hook_add(UC_HOOK_CODE, code)
                        f.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, memory)
                        f.call(entry, DISPLAY)
                        self.assertTrue(armed[0], "descriptor call did not return")
                        self.assertEqual(accesses, [])
                        self.assertEqual(source_writes, [])
                        self.assertIn(("bpm", "120.00 BPM"), captured)


if __name__ == "__main__":
    unittest.main(verbosity=2)
