"""Inject real USB reception between unmasked foreground instructions."""
from functools import lru_cache
from pathlib import Path
import struct
import unittest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_PRIMASK,
                               UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_SP)
from build_ksp_patch import build
from firmware_models import MODELS, model_address
from test_display_paths import setup_renderer, OWNER, DISPLAY
from test_tempo_hooks import Fixture, BASE, STOP, STACK, heartbeat, SESSION

ROOT = Path(__file__).resolve().parents[1]
NEW_SESSION, OLD_BPM, NEW_BPM = 0x20205, 13300, 14725
IRQ_STACK = 0x20090000


@lru_cache(maxsize=2)
def symbols(name):
    model = MODELS[name]
    image, labels, _base = build((ROOT / "firmware" / model.main_entry).read_bytes(), name)
    current = (ROOT / "firmware/patched" / ("kscon_" + model.main_entry)).read_bytes()
    assert bytes(image) == current, "test symbols must match the exact candidate"
    return labels


def exercise(name, path, inject_at=None, mask=0):
    f = Fixture(name)
    entry, _source, captured = setup_renderer(f, stock=False, view=path if path in (0, 1) else 1)
    labels = symbols(name)
    f.usb(heartbeat(bpm=OLD_BPM))
    if path == "poll":
        entry, r0, stop = f.poll_address, 0, STOP
    elif path == "turn":
        entry, r0, stop = f.model.encoder_up, 0, f.model.encoder_up + 4
        f.uc.mem_write(STACK + 0x6A, b"\0\x03")
    else:
        r0, stop = DISPLAY, STOP
    f.extra_stop = 0 if stop == STOP else stop
    for reg, value in ((UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, STOP | 1),
                       (UC_ARM_REG_R0, r0), (UC_ARM_REG_R1, 0), (UC_ARM_REG_R2, 0),
                       (UC_ARM_REG_PRIMASK, mask)):
        f.uc.reg_write(reg, value)
    # C tempo code is the last compiled source; exclude stock printf/driver code.
    low = labels["tempo_receive_byte"] & ~1
    high = BASE + len(f.raw)
    snapshot = labels["snapshot"] & ~1
    eligible, snapshots = [], []
    state = dict(irq=False, injected=False, pause=False, snapshot=None)

    def trace(u, address, _size, _data):
        if state["irq"]:
            return
        if address == snapshot:
            state["snapshot"] = (u.reg_read(UC_ARM_REG_LR) & ~1, u.reg_read(UC_ARM_REG_R0))
        call = state["snapshot"]
        if call and address == call[0]:
            snapshots.append((u.reg_read(UC_ARM_REG_R0), struct.unpack("<II", u.mem_read(call[1], 8))))
            state["snapshot"] = None
        if low <= address < high and not u.reg_read(UC_ARM_REG_PRIMASK):
            number = len(eligible)
            eligible.append(address)
            if inject_at == number and not state["injected"]:
                state["pause"] = True
                u.emu_stop()

    f.uc.hook_add(UC_HOOK_CODE, trace)
    f.uc.emu_start(entry | 1, 0, count=30000)
    if state["pause"]:
        saved = f.uc.context_save()
        saved_stop = f.extra_stop
        owner = bytes(f.uc.mem_read(OWNER, 256))
        display = bytes(f.uc.mem_read(DISPLAY, 512))
        drawn = f.word(0xC01EF80C)
        state["irq"] = True
        f.call_stack = IRQ_STACK
        f.usb(heartbeat(session=NEW_SESSION, bpm=NEW_BPM))
        assert bytes(f.uc.mem_read(OWNER, 256)) == owner, "IRQ changed UI owner"
        assert bytes(f.uc.mem_read(DISPLAY, 512)) == display, "IRQ changed display queue/cache"
        assert f.word(0xC01EF80C) == drawn, "IRQ changed foreground-only drawn cache"
        f.call_stack = STACK
        f.extra_stop = saved_stop
        f.uc.context_restore(saved)
        state.update(irq=False, injected=True, pause=False)
        f.uc.emu_start(f.uc.reg_read(UC_ARM_REG_PC) | 1, 0, count=30000)
    assert f.uc.reg_read(UC_ARM_REG_PC) == stop, "foreground did not return"
    assert f.uc.reg_read(UC_ARM_REG_SP) == STACK, "foreground stack changed"
    assert f.uc.reg_read(UC_ARM_REG_PRIMASK) == mask, "prior interrupt mask changed"
    assert snapshots, "snapshot was not exercised"
    assert all(active == 1 and pair in ((SESSION, OLD_BPM), (NEW_SESSION, NEW_BPM))
               for active, pair in snapshots), (path, inject_at, snapshots)
    if path in (0, 1):
        bpms = [text for kind, text in captured if kind == "bpm"]
        assert bpms and all(text in ("133.00 BPM", "147.25 BPM") for text in bpms), bpms
    if inject_at is not None:
        assert state["injected"], "scheduled interruption did not happen"
    return len(eligible)


class TempoConcurrency(unittest.TestCase):
    def test_receive_interleavings_in_poll_turn_and_both_renderers(self):
        total = 0
        for name in MODELS:
            for path in ("poll", "turn", 0, 1):
                count = exercise(name, path)
                self.assertGreater(count, 10)
                for point in range(count):
                    with self.subTest(model=name, path=path, boundary=point):
                        exercise(name, path, point)
                        total += 1
        print(f"Exercised {total} unmasked C instruction boundaries with real USB receive/drain")

    def test_already_masked_foreground_preserves_the_mask(self):
        for name in MODELS:
            for path in ("poll", "turn", 0, 1):
                with self.subTest(model=name, path=path):
                    exercise(name, path, mask=1)

    def test_early_usb_does_not_access_uninitialized_sdram(self):
        for name in MODELS:
            with self.subTest(model=name):
                f = Fixture(name)
                f.put(model_address(0x20001510, name), 0)
                f.uc.mem_unmap(0xC0000000, 0x200000)
                f.usb(heartbeat())


if __name__ == "__main__":
    unittest.main(verbosity=2)
