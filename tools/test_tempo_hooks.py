"""Offline tests through stock USB reception and the patched tempo dispatch."""
from pathlib import Path
import struct
import unittest

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_APSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_PRIMASK,
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_R12, UC_ARM_REG_SP,
)
from firmware_models import MODELS, TEMPO_PATHS, model_address

ROOT = Path(__file__).resolve().parents[1]
BASE, STOP, STACK = 0x08008000, 0x08007FF0, 0x20070000
OBJECT, BUFFER, BUTTONS, SEQ = 0x20010000, 0x20012000, 0x20018000, 0x20020000
LEASE, LEASE_SIZE = 0xC01EF9E4, 28
SESSION = 0x10203


def pack21(value):
    return bytes((value & 127, (value >> 7) & 127, (value >> 14) & 127))


def heartbeat(enabled=1, session=SESSION, bpm=12000):
    return bytes.fromhex("f07d4b530101") + bytes([enabled]) + pack21(session) + pack21(bpm) + b"\xf7"


HEARTBEAT = heartbeat()
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
        UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
        UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_R12)


class Fixture:
    def __init__(self, name):
        self.name, self.model, self.paths = name, MODELS[name], TEMPO_PATHS[name]
        self.raw = (ROOT / "firmware/patched" / ("kscon_" + self.model.main_entry)).read_bytes()[64:]
        self.uc = u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        u.mem_map(0x08000000, 0x80000)
        u.mem_write(BASE, self.raw)
        u.mem_map(0x20000000, 0x100000)
        u.mem_map(0xC0000000, 0x200000)
        start = model_address(0x0805CB60, name)
        count = model_address(0x20000650, name) - 0x20000004
        u.mem_write(0x20000004, self.raw[start-BASE:start-BASE+count])
        self.put(model_address(0x20001800, name), OBJECT)
        self.put(model_address(0x200014B8, name), BUTTONS)
        self.put(self.model.seq_pointer, SEQ)
        u.mem_write(SEQ + 0x8E2, b"\x02")
        u.mem_write(BUTTONS + 0x70, b"\x00\x01")
        self.extra_stop = 0
        self.init_calls = 0
        self.parser_bytes = []
        u.hook_add(UC_HOOK_CODE, self.trace)
        self.tick(10000)

    def put(self, address, value):
        self.uc.mem_write(address, struct.pack("<I", value))

    def word(self, address):
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def tick(self, value):
        self.put(self.model.tick_counter, value & 0xFFFFFFFF)

    def trace(self, u, address, _size, _data):
        if address == self.paths["byte_parser"]:
            self.parser_bytes.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)))
        if address == self.paths["sdram_init"]:
            self.init_calls += 1
            u.reg_write(UC_ARM_REG_R0, 123)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
        if address in (STOP, self.extra_stop):
            u.emu_stop()

    def call(self, address, r0=0, r1=0, r2=0, stop=0):
        u = self.uc
        self.extra_stop = stop
        for reg, value in ((UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, STOP | 1),
                           (UC_ARM_REG_R0, r0), (UC_ARM_REG_R1, r1), (UC_ARM_REG_R2, r2)):
            u.reg_write(reg, value)
        u.emu_start(address | 1, 0, count=30000)
        assert u.reg_read(UC_ARM_REG_PC) == (stop or STOP), "instruction budget exhausted"
        assert u.reg_read(UC_ARM_REG_SP) == STACK, "stack changed"
        self.extra_stop = 0

    def boot(self):
        self.call(self.paths["boot_call"], stop=self.paths["boot_call"] + 4)

    def tap(self, data, stream=None):
        for byte in data:
            self.call(self.paths["usb_rx_call"], OBJECT + 0x164 if stream is None else stream,
                      byte, stop=self.paths["usb_rx_call"] + 4)

    def usb(self, data):
        packets = bytearray()
        for i in range(0, len(data), 3):
            part = data[i:i+3]
            cin = 4 if part[-1] != 0xF7 else 4 + len(part)
            packets += bytes([cin]) + part.ljust(3, b"\0")
        self.uc.mem_write(BUFFER, bytes(packets))
        self.call(self.paths["usb_rx"], OBJECT, BUFFER, len(packets))
        self.call(self.paths["usb_drain"], OBJECT)

    def turn(self, direction=0, magnitude=1, fine=False, index=0, mask=0):
        u = self.uc
        u.mem_write(STACK + 0x6A, bytes((index, magnitude)))
        u.mem_write(BUTTONS + 0x70, bytes([int(fine), int(not fine)]))
        self.call(model_address(0x0804AEBA, self.name), BUTTONS, 1)
        assert u.reg_read(UC_ARM_REG_R0) == int(fine), "stock fine selector disagrees"
        for i, reg in enumerate(REGS):
            u.reg_write(reg, 0x11000000 + i)
        u.reg_write(UC_ARM_REG_LR, STOP | 1)
        u.reg_write(UC_ARM_REG_SP, STACK)
        u.reg_write(UC_ARM_REG_APSR, 0xA8000000)
        u.reg_write(UC_ARM_REG_PRIMASK, mask)
        before = {reg: u.reg_read(reg) for reg in REGS if reg != UC_ARM_REG_R6}
        entry = self.model.encoder_down if direction else self.model.encoder_up
        self.extra_stop = entry + 4
        u.emu_start(entry | 1, 0, count=30000)
        assert u.reg_read(UC_ARM_REG_PC) == entry + 4, "hook did not return to stock dispatch"
        assert u.reg_read(UC_ARM_REG_SP) == STACK
        assert u.reg_read(UC_ARM_REG_LR) == STOP | 1
        assert u.reg_read(UC_ARM_REG_APSR) & 0xF8000000 == 0xA8000000
        assert u.reg_read(UC_ARM_REG_PRIMASK) == mask
        assert all(u.reg_read(reg) == value for reg, value in before.items()), "register clobber"
        self.extra_stop = 0
        return u.reg_read(UC_ARM_REG_R6)

    def wire(self, start=0):
        data = bytearray()
        head = self.word(self.model.usb_queue)
        while start != head:
            packet = bytes(self.uc.mem_read(self.model.usb_queue + 8 + 4 * start, 4))
            cin = packet[0] & 15
            assert cin in (4, 5, 6, 7)
            data += packet[1:1 + (3 if cin == 4 else cin - 4)]
            start = (start + 1) & 63
        return bytes(data)


class TempoHooks(unittest.TestCase):
    def test_usb_identity_framing_and_din_isolation(self):
        for name in MODELS:
            with self.subTest(model=name):
                f = Fixture(name)
                for byte in HEARTBEAT:
                    f.call(f.paths["din_rx"], OBJECT, byte)
                self.assertEqual(bytes(f.uc.mem_read(LEASE, LEASE_SIZE)), b"\0" * LEASE_SIZE)
                f.tap(HEARTBEAT, OBJECT + 0x214)
                self.assertEqual(bytes(f.uc.mem_read(LEASE, LEASE_SIZE)), b"\0" * LEASE_SIZE)
                f.parser_bytes.clear()
                f.usb(HEARTBEAT)
                self.assertEqual(f.parser_bytes, [(OBJECT + 0x164, b) for b in HEARTBEAT])
                self.assertEqual(f.turn(), 255)

    def test_relative_turns_flags_and_registers(self):
        for name in MODELS:
            for direction in (0, 1):
                for fine in (False, True):
                    for mask in (0, 1):
                        with self.subTest(model=name, direction=direction, fine=fine, mask=mask):
                            f = Fixture(name)
                            f.usb(HEARTBEAT)
                            self.assertEqual(f.turn(direction, 255, fine, mask=mask), 255)
                            flags = direction | (2 if fine else 0)
                            self.assertEqual(f.wire(), bytes.fromhex("f07d4b530102") + pack21(SESSION) + bytes([flags, 127, 1, 247]))
                            self.assertEqual(bytes(f.uc.mem_read(SEQ + 0x8E2, 1)), b"\x02")

    def test_no_lease_other_knob_disable_and_expiry(self):
        for name in MODELS:
            with self.subTest(model=name):
                f = Fixture(name)
                self.assertEqual(f.turn(), 0)
                self.assertEqual(f.word(f.model.usb_queue), 0)
                f.usb(HEARTBEAT)
                self.assertEqual(f.turn(index=3), 3)
                self.assertEqual(f.word(f.model.usb_queue), 0)
                f.usb(heartbeat(enabled=0))
                self.assertEqual(f.turn(), 0)
                f.tick(0xFFFFFFF0)
                f.usb(HEARTBEAT)
                f.tick(0x10)
                self.assertEqual(f.turn(), 255)
                f.tick((0xFFFFFFF0 + 3001) & 0xFFFFFFFF)
                self.assertEqual(f.turn(), 0)
                self.assertNotEqual(f.word(LEASE), 0x32504D55)

    def test_bad_and_truncated_frames_do_not_renew(self):
        bad = (HEARTBEAT[:-1], HEARTBEAT[:-1] + b"\x00\xf7",
               HEARTBEAT.replace(b"\x7d", b"\x7e"), HEARTBEAT.replace(b"\x53", b"\x54"),
               heartbeat(enabled=2), heartbeat(session=0), heartbeat(bpm=1000), heartbeat(bpm=99901),
               HEARTBEAT[:4] + b"\x90" + HEARTBEAT[4:])
        for name in MODELS:
            for frame in bad:
                with self.subTest(model=name, frame=frame.hex()):
                    f = Fixture(name)
                    f.usb(HEARTBEAT)
                    f.tick(12900)
                    f.tap(frame)
                    f.tick(13001)
                    self.assertEqual(f.turn(), 0)
            f = Fixture(name)
            f.tap(HEARTBEAT[:-1])
            f.tick(10251)
            f.tap(b"\xf7")
            self.assertEqual(f.turn(), 0)
            f = Fixture(name)
            f.tap(b"\xf8".join(bytes([b]) for b in HEARTBEAT))
            self.assertEqual(f.turn(), 255)

    def test_queue_full_wrap_and_corruption(self):
        for name in MODELS:
            with self.subTest(model=name):
                f = Fixture(name)
                f.usb(HEARTBEAT)
                for head, tail in ((59, 0), (100, 0), (0, 100)):
                    f.put(f.model.usb_queue, head)
                    f.put(f.model.usb_queue + 4, tail)
                    before = bytes(f.uc.mem_read(f.model.usb_queue, 264))
                    self.assertEqual(f.turn(), 255)
                    self.assertEqual(bytes(f.uc.mem_read(f.model.usb_queue, 264)), before)
                f.put(f.model.usb_queue, 62)
                f.put(f.model.usb_queue + 4, 20)
                self.assertEqual(f.turn(), 255)
                self.assertEqual(f.word(f.model.usb_queue), 3)
                self.assertEqual(f.wire(62), bytes.fromhex("f07d4b530102") + pack21(SESSION) + bytes.fromhex("000100f7"))
                f.put(LEASE + 8, 0)
                self.assertEqual(f.turn(), 0)

    def test_boot_clears_only_reserved_gap_after_sdram_init(self):
        for name in MODELS:
            with self.subTest(model=name):
                f = Fixture(name)
                f.uc.mem_write(0xC01EF800, b"\xa5" * 2048)
                f.boot()
                self.assertEqual(f.init_calls, 1)
                self.assertEqual(f.uc.reg_read(UC_ARM_REG_R0), 123)
                self.assertEqual(bytes(f.uc.mem_read(LEASE, LEASE_SIZE)), b"\0" * LEASE_SIZE)
                self.assertEqual(bytes(f.uc.mem_read(LEASE - 4, 4)), b"\xa5" * 4)
                self.assertEqual(bytes(f.uc.mem_read(LEASE + LEASE_SIZE, 4)), b"\xa5" * 4)
                self.assertEqual(bytes(f.uc.mem_read(0xC01EF808, 8)), b"\0" * 8)
                self.assertEqual(bytes(f.uc.mem_read(0xC01EF804, 4)), b"\xa5" * 4)
                self.assertEqual(bytes(f.uc.mem_read(0xC01EF810, 4)), b"\xa5" * 4)

    def test_old_disable_does_not_cancel_new_host_session(self):
        for name in MODELS:
            with self.subTest(model=name):
                f = Fixture(name)
                f.usb(heartbeat(session=SESSION + 1))
                f.usb(heartbeat(enabled=0, session=SESSION))
                self.assertEqual(f.turn(), 255)
                self.assertEqual(f.wire(), bytes.fromhex("f07d4b530102") + pack21(SESSION + 1) + bytes.fromhex("000100f7"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
