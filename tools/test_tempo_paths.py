"""Run the stock dispatch/USB code offline. Does not contact a MIDI device.

These probes start at the encoder dispatch, not at the physical encoder scanner.
They establish a hook candidate, not physical-device compatibility.
"""
from pathlib import Path
import struct
import unittest

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_THUMB, Uc
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R6, UC_ARM_REG_SP,
)

from firmware_models import MODELS, model_address
from build_ksp_patch import model_source
from build_names_patch import decode_thumb_bl, decode_thumb_b_w

BASE, STOP, SEQ, STACK = 0x08008000, 0x08007FF0, 0x20020000, 0x20070000
STOCK = Path(__file__).resolve().parents[1] / "firmware"


def machine(raw):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    uc.mem_map(0x08000000, 0x80000)
    uc.mem_write(BASE, raw)
    uc.mem_map(0x20000000, 0x80000)
    uc.reg_write(UC_ARM_REG_SP, STACK)
    uc.reg_write(UC_ARM_REG_LR, STOP | 1)
    return uc


def application_tick_us(model, hclk=216000000):
    raw = model.read_stock(STOCK)
    entry, setup, call, hclk_get = {
        "original": (0x08017C54, 0x08017B44, 0x08017C06, 0x08040860),
        "chroma": (0x08017DB0, 0x08017CA0, 0x08017D62, 0x08040DC0),
    }[model.name]
    assert decode_thumb_bl(entry + 6, raw[entry+6-BASE:entry+10-BASE]) == setup
    assert decode_thumb_bl(call - 12, raw[call-12-BASE:call-8-BASE]) == hclk_get
    hal_call = model.tick_get - 0x80
    assert decode_thumb_bl(call, raw[call-BASE:call-BASE+4]) == decode_thumb_bl(
        hal_call, raw[hal_call-BASE:hal_call-BASE+4])
    hardware = {decode_thumb_bl(setup + offset, raw[setup+offset-BASE:setup+offset-BASE+4])
                for offset in (0x58, 0x60, 0x84, 0xB0)}
    uc = machine(raw)
    uc.mem_map(0xE000E000, 0x2000)
    uc.mem_map(0x40000000, 0x30000)  # Native RCC/PWR register accesses.

    def trace(m, address, _size, _data):
        if address == hclk_get or address in hardware:
            # Hardware clock/power setup is stubbed; all SysTick/NVIC code runs.
            m.reg_write(UC_ARM_REG_R0, hclk if address == hclk_get else 0)
            m.reg_write(UC_ARM_REG_PC, m.reg_read(UC_ARM_REG_LR))
        if address == STOP:
            m.emu_stop()

    uc.hook_add(UC_HOOK_CODE, trace)
    uc.emu_start(setup | 1, 0, count=1000)
    assert uc.reg_read(UC_ARM_REG_PC) == STOP
    assert uc.reg_read(UC_ARM_REG_SP) == STACK
    assert struct.unpack("<I", uc.mem_read(0xE000E010, 4))[0] == 7
    reload = struct.unpack("<I", uc.mem_read(0xE000E014, 4))[0]
    return (reload + 1) * 1000000 // hclk


class StockTempoPaths(unittest.TestCase):
    def test_wrong_variant_and_corrupt_stock_are_rejected(self):
        for name, model in MODELS.items():
            image = (STOCK / model.main_entry).read_bytes()
            other = MODELS["chroma" if name == "original" else "original"]
            with self.subTest(model=name):
                with self.assertRaises(ValueError):
                    other.validate_stock(image)
                corrupt = bytearray(image)
                corrupt[100] ^= 1
                # Even a recomputed checksum must not bypass the exact-input hash.
                corrupt[9] = -sum(corrupt[64:]) & 255
                corrupt[63] = -sum(corrupt[:63]) & 255
                with self.assertRaises(ValueError):
                    model.validate_stock(corrupt)
                with self.assertRaises(ValueError):
                    model.validate_stock(b"")

    def test_address_map_preserves_byte_addresses_and_thumb_bits(self):
        self.assertEqual(model_address(0x20000671, "chroma"), 0x20000675)
        self.assertEqual(model_address(0x20004DAD, "chroma"), 0x20004DCD)
        self.assertEqual(model_address(0x0800DF33, "chroma"), 0x0800E0FB)
        self.assertEqual(model_address(0x20000004, "chroma"), 0x20000004)
        self.assertEqual(model_address(0x20000058, "chroma"), 0x20000058)
        with self.assertRaises(ValueError):
            model_address(0, "unsupported")

    def test_new_unmapped_hook_addresses_fail_closed(self):
        for source in ("ldr r0,=0x08040000", "ldr r0,=0x20001234"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                model_source(source, "chroma")

    def test_encoder_reaches_hook_before_clock_gate(self):
        for model in MODELS.values():
            raw = model.read_stock(STOCK)
            for entry in (model.encoder_up, model.encoder_down):
                for mode in (0, 1, 2, 3):
                    for playing in (0, 1):
                        with self.subTest(model=model.name, entry=hex(entry), mode=mode, playing=playing):
                            self.assertEqual(raw[entry - BASE:entry - BASE + 4], bytes.fromhex("9df86a60"))
                            uc = machine(raw)
                            uc.mem_write(model.seq_pointer, struct.pack("<I", SEQ))
                            uc.mem_write(SEQ + 0x8E2, bytes([mode]))
                            uc.mem_write(SEQ + 0xC, bytes([playing]))
                            uc.mem_write(STACK + 0x6A, b"\x00\x03")
                            visited = []

                            def trace(m, address, _size, _data):
                                visited.append(address)
                                if address in (model.loop_continue, model.tempo_get):
                                    m.emu_stop()

                            uc.hook_add(UC_HOOK_CODE, trace)
                            uc.emu_start(entry | 1, 0, count=200)
                            self.assertEqual(visited[0], entry)
                            self.assertIn(model.clock_mode_get, visited)
                            self.assertEqual(uc.reg_read(UC_ARM_REG_R6), 0)
                            self.assertEqual(visited[-1], model.tempo_get if mode == 1 else model.loop_continue)

    def test_usb_packet_round_trip_and_no_din_queue_write(self):
        # USB-MIDI packets: CIN 4, then CIN 7 for three bytes ending in F7.
        # The stock converter preserves raw SysEx packets with CIN <= 7.
        packets = (bytes.fromhex("04f07d4b"), bytes.fromhex("075301f7"))
        for model in MODELS.values():
            raw = model.read_stock(STOCK)
            with self.subTest(model=model.name):
                uc = machine(raw)
                writes = []
                uc.hook_add(UC_HOOK_MEM_WRITE, lambda _m, _a, address, size, _v, _d: writes.append((address, size)))
                uc.hook_add(UC_HOOK_CODE, lambda m, a, _s, _d: m.emu_stop() if a == STOP else None)
                for index, packet in enumerate(packets):
                    uc.reg_write(UC_ARM_REG_SP, STACK)
                    uc.reg_write(UC_ARM_REG_LR, STOP | 1)
                    uc.reg_write(UC_ARM_REG_R1, int.from_bytes(packet, "little"))
                    uc.emu_start(model.usb_enqueue | 1, 0, count=500)
                    self.assertEqual(uc.reg_read(UC_ARM_REG_PC), STOP)
                    self.assertEqual(bytes(uc.mem_read(model.usb_queue + 8 + index * 4, 4)), packet)
                    self.assertEqual(struct.unpack("<I", uc.mem_read(model.usb_queue, 4))[0], index + 1)
                    uc.reg_write(UC_ARM_REG_SP, STACK)
                    uc.reg_write(UC_ARM_REG_LR, STOP | 1)
                    uc.reg_write(UC_ARM_REG_R1, int.from_bytes(packet, "little"))
                    uc.emu_start(model.usb_convert | 1, 0, count=500)
                    self.assertEqual(uc.reg_read(UC_ARM_REG_PC), STOP)
                    self.assertEqual(uc.reg_read(UC_ARM_REG_R0), int.from_bytes(packet, "little"))
                # This path writes only its stack and USB ring, not either DIN queue.
                for address, size in writes:
                    self.assertTrue(STACK - 128 <= address < STACK or
                                    model.usb_queue <= address and address + size <= model.usb_queue + 264,
                                    f"unexpected write at {address:#x}")

    def test_consumed_encoder_exits_stock_dispatch_without_side_effects(self):
        for model in MODELS.values():
            for entry in (model.encoder_up + 4, model.encoder_down + 4):
                with self.subTest(model=model.name, entry=hex(entry)):
                    uc = machine(model.read_stock(STOCK))
                    uc.reg_write(UC_ARM_REG_R6, 0xFF)
                    visited, writes = [], []

                    def trace(m, address, _size, _data):
                        visited.append(address)
                        if address == model.loop_continue:
                            m.emu_stop()

                    uc.hook_add(UC_HOOK_CODE, trace)
                    uc.hook_add(UC_HOOK_MEM_WRITE, lambda _m, _a, address, size, _v, _d: writes.append((address, size)))
                    uc.emu_start(entry | 1, 0, count=100)
                    self.assertEqual(visited[-1], model.loop_continue)
                    self.assertEqual(writes, [])
                    self.assertNotIn(model.tempo_get, visited)
                    self.assertTrue(all(entry <= address < entry + 32 for address in visited[:-1]))

    def test_tempo_page_selector_calls_the_expected_native_functions(self):
        for model in MODELS.values():
            with self.subTest(model=model.name):
                raw = model.read_stock(STOCK)
                entry = model_address(0x0801FAA0, model.name)
                targets = []
                for address in range(entry, entry + 0x72, 2):
                    try:
                        targets.append(decode_thumb_bl(address, raw[address - BASE:address - BASE + 4]))
                    except ValueError:
                        pass
                self.assertEqual(targets.count(model_address(0x0801F96C, model.name)), 4)
                self.assertEqual(targets.count(model.tempo_get), 1)
                self.assertEqual(targets.count(model_address(0x08025494, model.name)), 1)

    def test_tick_counter_is_read_without_mutation(self):
        for model in MODELS.values():
            with self.subTest(model=model.name):
                uc = machine(model.read_stock(STOCK))
                uc.mem_write(model.tick_counter, struct.pack("<I", 0x12345678))
                uc.hook_add(UC_HOOK_CODE, lambda m, a, _s, _d: m.emu_stop() if a == STOP else None)
                uc.emu_start(model.tick_get | 1, 0, count=20)
                self.assertEqual(uc.reg_read(UC_ARM_REG_PC), STOP)
                self.assertEqual(uc.reg_read(UC_ARM_REG_R0), 0x12345678)
                self.assertEqual(bytes(uc.mem_read(model.tick_counter, 4)), struct.pack("<I", 0x12345678))

    def test_application_overrides_hal_tick_to_100_microseconds(self):
        for model in MODELS.values():
            for hclk in (108000000, 216000000):
                with self.subTest(model=model.name, hclk=hclk):
                    self.assertEqual(application_tick_us(model, hclk), 100)

    def test_clock_reconfiguration_callers_and_normal_usb_resume(self):
        for name, model in MODELS.items():
            with self.subTest(model=name):
                raw = model.read_stock(STOCK)
                entry, setup, config, resume_setup, usb_init, resume = {
                    "original": (0x08017C54, 0x08017B44, 0x08017C06,
                                 0x0800F488, 0x0803E004, 0x0803E1A4),
                    "chroma": (0x08017DB0, 0x08017CA0, 0x08017D62,
                               0x0800F69C, 0x0803E564, 0x0803E704),
                }[name]
                target = lambda site: decode_thumb_bl(site, raw[site-BASE:site-BASE+4])
                calls = {}
                for offset in range(0, len(raw) - 4, 2):
                    try:
                        callee = target(BASE + offset)
                    except ValueError:
                        try:
                            callee = decode_thumb_b_w(BASE + offset, raw[offset:offset+4])
                        except ValueError:
                            continue
                    calls.setdefault(callee, []).append(BASE + offset)
                self.assertEqual(target(entry + 2), model.tick_get - 0x4C)  # HAL init first.
                self.assertEqual(calls[target(config)],
                                 [resume_setup + 0xB6, config, model.tick_get - 0x80])
                self.assertEqual(calls[model.tick_get - 0x98],
                                 [model.tick_get - 0x28, target(setup + 0x84) + 0x1EA])
                for app_offset, resume_offset in ((0x84, 0x7C), (0xB0, 0xA4)):
                    self.assertEqual(calls[target(setup + app_offset)],
                                     [resume_setup + resume_offset, setup + app_offset])
                self.assertEqual(calls[resume_setup], [resume + 0x28])

                uc = machine(raw)
                uc.mem_map(0xE000E000, 0x2000)
                uc.mem_map(0x50000000, 0x1000)  # USB core registers.
                uc.reg_write(UC_ARM_REG_R0, 0x20010000)
                phase = ["init"]
                clock_restores = []

                def trace(m, address, _size, _data):
                    if address == resume_setup:
                        clock_restores.append(address)
                        m.emu_stop()
                    if phase[0] == "init" and address == usb_init + 0x34:
                        m.emu_stop()  # Hardware PCD initialization is not needed.
                    if phase[0] == "resume" and address == target(resume + 0x22):
                        m.reg_write(UC_ARM_REG_PC, m.reg_read(UC_ARM_REG_LR))
                    if address == STOP:
                        m.emu_stop()

                uc.hook_add(UC_HOOK_CODE, trace)
                uc.emu_start(usb_init | 1, 0, count=100)
                self.assertEqual(uc.reg_read(UC_ARM_REG_PC), usb_init + 0x34)
                handle = uc.reg_read(UC_ARM_REG_R0)
                uc.mem_write(handle, b"\xa5" * 0x400)
                self.assertNotEqual(struct.unpack("<I", uc.mem_read(handle + 0x20, 4))[0], 0)
                uc.reg_write(UC_ARM_REG_SP, STACK)
                uc.reg_write(UC_ARM_REG_LR, STOP | 1)
                uc.reg_write(UC_ARM_REG_R0, 0x20010000)
                uc.emu_start(usb_init | 1, 0, count=100)
                self.assertEqual(uc.reg_read(UC_ARM_REG_PC), usb_init + 0x34)
                self.assertEqual(uc.reg_read(UC_ARM_REG_R0), handle)
                self.assertEqual(struct.unpack("<I", uc.mem_read(handle + 0x20, 4))[0], 0)
                uc.mem_write(0xE000E010, struct.pack("<II", 7, 21599))
                phase[0] = "resume"
                uc.reg_write(UC_ARM_REG_SP, STACK)
                uc.reg_write(UC_ARM_REG_LR, STOP | 1)
                uc.reg_write(UC_ARM_REG_R0, handle)
                uc.reg_write(UC_ARM_REG_R1, 0)
                uc.emu_start(resume | 1, 0, count=200)
                self.assertEqual(clock_restores, [], "normal USB resume changed the application clock")
                self.assertEqual(uc.reg_read(UC_ARM_REG_PC), STOP)
                self.assertEqual(bytes(uc.mem_read(0xE000E010, 8)), struct.pack("<II", 7, 21599))

    def test_initial_hal_tick_configuration_before_application_override(self):
        for model in MODELS.values():
            with self.subTest(model=model.name):
                raw = model.read_stock(STOCK)
                uc = machine(raw)
                uc.mem_map(0xE000E000, 0x2000)  # SysTick and NVIC registers
                init = model.tick_get - 0x98
                frequency, clock, _priority = struct.unpack_from("<III", raw, init + 64 - BASE)
                uc.mem_write(frequency, b"\x01")
                uc.mem_write(clock, struct.pack("<I", 216000000))
                uc.hook_add(UC_HOOK_CODE, lambda m, a, _s, _d: m.emu_stop() if a == STOP else None)
                uc.reg_write(UC_ARM_REG_R0, 0)
                uc.emu_start(init | 1, 0, count=200)
                self.assertEqual(uc.reg_read(UC_ARM_REG_PC), STOP)
                self.assertEqual(struct.unpack("<I", uc.mem_read(0xE000E014, 4))[0], 215999)
                self.assertEqual(struct.unpack("<I", uc.mem_read(0xE000E010, 4))[0], 7)
                uc.reg_write(UC_ARM_REG_LR, STOP | 1)
                uc.emu_start((model.tick_get - 0x18) | 1, 0, count=30)
                self.assertEqual(uc.reg_read(UC_ARM_REG_PC), STOP)
                self.assertEqual(struct.unpack("<I", uc.mem_read(model.tick_counter, 4))[0], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
