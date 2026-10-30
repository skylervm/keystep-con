"""Qualify native foreground cadence, queue consumption and startup readiness."""
from pathlib import Path
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_APSR, UC_ARM_REG_PRIMASK
from build_names_patch import decode_thumb_bl
from firmware_models import MODELS, model_address
from test_display_paths import setup_renderer, OWNER, DISPLAY
from test_tempo_hooks import Fixture, BASE, STACK, SEQ

FOREGROUND = {
    "original": dict(head=0x080173AE, call=0x08016976, update=0x0801F310,
                     encoder=0x08016954, led=0x0801696A, consume=0x08016ACC,
                     rendered=0x08016B00, ctor=0x0801F1EC, ctor_call=0x0801655E,
                     boot=0x08016482, timer_start=0x080167DA),
    "chroma": dict(head=0x08017512, call=0x08016B20, update=0x0801F49C,
                   encoder=0x08016B04, led=0x08016B16, consume=0x08016C76,
                   rendered=0x08016CAA, ctor=0x0801F378, ctor_call=0x08016750,
                   boot=0x0801667E, timer_start=0x08016994),
}


class ForegroundPaths(unittest.TestCase):
    def test_idle_loop_calls_real_ui_update_in_every_state(self):
        # Execute the real normal-loop backedge, with only event polling and LED
        # I/O stubbed. The native UI update and its getters/queue calls run.
        for name in MODELS:
            for playing in (0, 1):
                for page in (0, 1, 0xF, 0x60):
                    with self.subTest(model=name, playing=playing, page=page):
                        f = Fixture(name)
                        setup_renderer(f, view=0)
                        p = FOREGROUND[name]
                        f.uc.mem_write(OWNER + 0xC, bytes([page]))
                        f.uc.mem_write(SEQ + 0xC, bytes([playing]))
                        clock_global = f.word(p["update"] + 0x1D0)
                        f.put(clock_global, 0x20045000)
                        f.uc.mem_write(0x2004500E, struct.pack("<H", 12000))
                        f.call_stack = OWNER - (0x12B40 if name == "original" else 0x12C80)
                        seen = []

                        def trace(u, address, _size, _data):
                            if address in (p["encoder"], p["led"]):
                                u.reg_write(UC_ARM_REG_PC, (address + 4) | 1)
                            if address == p["update"]:
                                seen.append(u.reg_read(UC_ARM_REG_R0))

                        f.uc.hook_add(UC_HOOK_CODE, trace)
                        for _ in range(3):
                            f.uc.reg_write(UC_ARM_REG_R4, 0)
                            f.call(p["head"], stop=p["call"] + 4)
                        self.assertEqual(seen, [OWNER] * 3)

    def test_main_application_consumes_queued_bpm_renderer(self):
        for name in MODELS:
            for page in (0, 1):
                with self.subTest(model=name, page=page):
                    f = Fixture(name)
                    entry, _source, captured = setup_renderer(f, view=page)
                    p = FOREGROUND[name]
                    f.put(DISPLAY + 0x3C, DISPLAY)
                    f.call(model_address(0x08025494 if page else 0x0802546C, name), DISPLAY, 0xFFFFFFFF)
                    index = 0 if f.word(DISPLAY + 0x10) == entry | 1 else 1
                    self.assertEqual(f.word(DISPLAY + index * 24 + 0x10), entry | 1)
                    f.uc.mem_write(STACK + 0x20, bytes([index]))
                    f.put(STACK + 0x24, DISPLAY)
                    f.call(p["consume"], stop=p["rendered"])
                    self.assertTrue(any(kind == "bpm" for kind, _text in captured))

    def test_wrapper_preserves_native_update_results_and_polls_afterwards(self):
        for name in MODELS:
            for mask in (0, 1):
                with self.subTest(model=name, mask=mask):
                    results = []
                    for patched in (False, True):
                        f = Fixture(name)
                        setup_renderer(f, stock=not patched, view=1)
                        p = FOREGROUND[name]
                        f.put(f.word(p["update"] + 0x1D0), 0x20045000)
                        f.uc.mem_write(0x2004500E, struct.pack("<H", 12000))
                        f.uc.reg_write(UC_ARM_REG_PRIMASK, mask)
                        order = []

                        def trace(_u, address, _size, _data):
                            if address == p["update"]:
                                order.append("native")
                            if address == f.poll_address:
                                order.append("poll")

                        f.uc.hook_add(UC_HOOK_CODE, trace)
                        f.call(p["call"], OWNER, stop=p["call"] + 4)
                        results.append(tuple(f.uc.reg_read(reg) for reg in
                                             (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                              UC_ARM_REG_R3, UC_ARM_REG_APSR, UC_ARM_REG_PRIMASK)))
                        self.assertEqual(order, ["native", "poll"] if patched else ["native"])
                    self.assertEqual(results[0], results[1])

    def test_native_ui_pointer_is_a_post_sdram_ready_guard(self):
        for name, model in MODELS.items():
            with self.subTest(model=name):
                f = Fixture(name)
                raw = model.read_stock(Path(__file__).resolve().parents[1] / "firmware")
                f.uc.mem_write(BASE, raw)
                ready = model_address(0x20001510, name)
                f.put(ready, 0xA5A5A5A5)
                reset = struct.unpack_from("<I", raw, 4)[0] & ~1
                f.extra_stop = reset + 0x2A  # first hardware-init call, after data/BSS
                f.uc.emu_start(reset | 1, 0, count=2000000)
                self.assertEqual(f.uc.reg_read(UC_ARM_REG_PC), f.extra_stop)
                self.assertEqual(f.word(ready), 0)
                f.extra_stop = 0
                p = FOREGROUND[name]
                self.assertLess(p["boot"], p["ctor_call"])
                self.assertLess(p["ctor_call"], p["timer_start"])
                self.assertEqual(decode_thumb_bl(p["ctor_call"], raw[p["ctor_call"]-BASE:p["ctor_call"]-BASE+4]), p["ctor"])
                f.call(p["ctor"], OWNER)
                self.assertEqual(f.word(ready), OWNER)


if __name__ == "__main__":
    unittest.main(verbosity=2)
