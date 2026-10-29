#!/usr/bin/env python3
"""Exercise the built Thumb hooks in Unicorn with mocked flash helpers."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_THUMB, Uc
from unicorn.arm_const import (
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R3,
    UC_ARM_REG_R4,
    UC_ARM_REG_R6,
    UC_ARM_REG_R7,
    UC_ARM_REG_R8,
    UC_ARM_REG_SP,
)

FLASH_BASE = 0x60000000
FLASH_SIZE = 0x200000
STAGE_BASE = 0xC01F0000
STOP = 0x08007FF0
TITLE_HOOK = 0x0805D1AC
SET_DISPATCH = 0x0800DF28
STOCK_SETTER = 0x0800CCA8

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_names_patch import decode_thumb_b_w  # noqa: E402
from set_project_name import encode_frames  # noqa: E402


def reg(uc: Uc, name: int) -> int:
    return uc.reg_read(name)


def run(path: Path) -> None:
    image = path.read_bytes()
    raw = image[64:]
    assert sum(image[:64]) & 0xFF == 0, "header checksum byte not updated"
    assert (sum(raw) + image[9]) & 0xFF == 0, "payload checksum byte not updated"
    set_hook = decode_thumb_b_w(SET_DISPATCH, raw[SET_DISPATCH - 0x08008000:SET_DISPATCH - 0x08008000 + 4])
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    uc.mem_map(0x08000000, 0x80000)
    uc.mem_write(0x08008000, raw)
    uc.mem_map(0x20000000, 0x100000)
    uc.mem_map(FLASH_BASE, FLASH_SIZE)
    uc.mem_map(STAGE_BASE, 0x10000)
    flash = bytearray(b"\xff" * FLASH_SIZE)
    flash_reads: list[int] = []
    sector_reads: list[int] = []
    flash_writes: list[int] = []
    formatter_calls: list[int] = []
    formatter_sp: list[int] = []
    stock_setter_calls: list[tuple[int, ...]] = []

    def callback(machine: Uc, address: int, _size: int, _data: object) -> None:
        if address == 0x0803F774:  # read halfwords from external NOR
            source = reg(machine, UC_ARM_REG_R1)
            dest = reg(machine, UC_ARM_REG_R2)
            length = reg(machine, UC_ARM_REG_R3) * 2
            machine.mem_write(dest, bytes(flash[source - FLASH_BASE:source - FLASH_BASE + length]))
            flash_reads.append(source)
            machine.reg_write(UC_ARM_REG_R0, 0)
            machine.reg_write(UC_ARM_REG_PC, reg(machine, UC_ARM_REG_LR))
        elif address == 0x0805761C:  # stock formatter fallback
            dest = reg(machine, UC_ARM_REG_R0)
            value = reg(machine, UC_ARM_REG_R3)
            text = f"Project {value}".encode("ascii") + b"\0"
            machine.mem_write(dest, text)
            formatter_calls.append(value)
            formatter_sp.append(reg(machine, UC_ARM_REG_SP))
            machine.reg_write(UC_ARM_REG_R0, len(text) - 1)
            machine.reg_write(UC_ARM_REG_PC, reg(machine, UC_ARM_REG_LR))
        elif address == 0x080470EC:  # read complete sector into staging RAM
            source = reg(machine, UC_ARM_REG_R1)
            offset = source - FLASH_BASE
            machine.mem_write(STAGE_BASE, bytes(flash[offset:offset + 0x10000]))
            sector_reads.append(source)
            machine.reg_write(UC_ARM_REG_PC, reg(machine, UC_ARM_REG_LR))
        elif address == 0x08047148:  # patch staging RAM (length is halfwords)
            offset = reg(machine, UC_ARM_REG_R1)
            source = reg(machine, UC_ARM_REG_R2)
            length = reg(machine, UC_ARM_REG_R3) * 2
            stage = machine.mem_read(reg(machine, UC_ARM_REG_SP), 4)
            dest_base = int.from_bytes(stage, "little")
            machine.mem_write(dest_base + offset, bytes(machine.mem_read(source, length)))
            machine.reg_write(UC_ARM_REG_PC, reg(machine, UC_ARM_REG_LR))
        elif address == 0x080475D8:  # program the staging sector
            dest = reg(machine, UC_ARM_REG_R1)
            offset = dest - FLASH_BASE
            flash[offset:offset + 0x10000] = machine.mem_read(STAGE_BASE, 0x10000)
            flash_writes.append(dest)
            machine.reg_write(UC_ARM_REG_PC, reg(machine, UC_ARM_REG_LR))
        elif address == STOCK_SETTER:
            stock_setter_calls.append(tuple(reg(machine, r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)))
            machine.reg_write(UC_ARM_REG_PC, reg(machine, UC_ARM_REG_LR))
        elif address == STOP or address == 0x0800DF32:
            machine.emu_stop()

    uc.hook_add(UC_HOOK_CODE, callback)

    def execute(address: int, regs: dict[int, int], setup: Callable[[], None] | None = None) -> None:
        uc.reg_write(UC_ARM_REG_SP, 0x200FF000)
        uc.reg_write(UC_ARM_REG_LR, STOP | 1)
        for number, value in regs.items():
            uc.reg_write(number, value)
        if setup:
            setup()
        uc.emu_start(address | 1, 0, count=20000)

    output = 0x20010000
    slot = 3
    name = b"Amazing Grace\0\0\0"
    name_address = FLASH_BASE + slot * 0x20000 + 0x1FFF0
    flash[name_address - FLASH_BASE:name_address - FLASH_BASE + 16] = name
    execute(TITLE_HOOK, {
        UC_ARM_REG_R0: output,
        UC_ARM_REG_R1: 100,
        UC_ARM_REG_R2: 0x0805AE68,
        UC_ARM_REG_R3: slot + 1,
    })
    actual = bytes(uc.mem_read(output, 17))
    assert actual == b"Amazing Grace\0\0\0\0", actual
    assert flash_reads[-1] == name_address

    flash_reads.clear()
    execute(TITLE_HOOK, {
        UC_ARM_REG_R0: output,
        UC_ARM_REG_R1: 100,
        UC_ARM_REG_R2: 0x0805AE68,
        UC_ARM_REG_R3: 17,
    })
    assert formatter_calls[-1] == 17
    assert not flash_reads
    actual_fallback = bytes(uc.mem_read(output, 11))
    assert actual_fallback == b"Project 17\0", actual_fallback
    assert formatter_sp[-1] % 8 == 0, "formatter called with misaligned stack"

    flash[:] = b"\xa5" * FLASH_SIZE
    project = 5
    sector = FLASH_BASE + project * 0x20000 + 0x10000
    payload = b"Amazing Grace\0\0\0"
    struct_addr, data_addr = 0x20011000, 0x20012000
    flash_reads.clear()
    sector_reads.clear()
    flash_writes.clear()
    uc.mem_write(struct_addr, b"\0\0" + bytes((project,)) + b"\0" * 5 + bytes((0x7C,)))
    uc.mem_write(data_addr, payload)
    uc.mem_write(0x20000671, b"\x02")
    execute(set_hook, {
        UC_ARM_REG_R1: 0xDEADBEEF,
        UC_ARM_REG_R4: struct_addr,
        UC_ARM_REG_R6: 0x20001820,
        UC_ARM_REG_R7: data_addr,
        UC_ARM_REG_R8: 16,
    })
    saved_at = sector + 0xFFF0
    assert bytes(flash[saved_at - FLASH_BASE:saved_at - FLASH_BASE + 16]) == payload
    assert flash_writes == [sector]
    assert sector_reads == [sector]
    assert flash[sector - FLASH_BASE] == 0xA5
    assert uc.mem_read(0x20000671, 1) == b"\0"

    writes_before = len(flash_writes)
    uc.mem_write(0x20000671, b"\x02")
    execute(set_hook, {
        UC_ARM_REG_R1: 0xDEADBEEF,
        UC_ARM_REG_R4: struct_addr,
        UC_ARM_REG_R6: 0x20001820,
        UC_ARM_REG_R7: data_addr,
        UC_ARM_REG_R8: 15,
    })
    assert len(flash_writes) == writes_before
    assert uc.mem_read(0x20000671, 1) == b"\x02"
    assert not stock_setter_calls

    # Project byte above 15 (past the 16 x 128 KB slots) is ignored.
    writes_before = len(flash_writes)
    uc.mem_write(struct_addr + 2, bytes((16,)))
    execute(set_hook, {
        UC_ARM_REG_R1: 0xDEADBEEF,
        UC_ARM_REG_R4: struct_addr,
        UC_ARM_REG_R6: 0x20001820,
        UC_ARM_REG_R7: data_addr,
        UC_ARM_REG_R8: 16,
    })
    assert len(flash_writes) == writes_before

    # Other item-0x78 params reach the stock setter with the message pointer from r4.
    uc.mem_write(struct_addr, b"\0\0\x02" + b"\0" * 5 + b"\x10")
    execute(set_hook, {
        UC_ARM_REG_R1: 0xDEADBEEF,
        UC_ARM_REG_R4: struct_addr,
        UC_ARM_REG_R6: 0x20001820,
        UC_ARM_REG_R7: data_addr,
        UC_ARM_REG_R8: 1,
    })
    assert stock_setter_calls == [(0x20001820, struct_addr, data_addr)], stock_setter_calls
    assert reg(uc, UC_ARM_REG_R4) == struct_addr

    # Round trip: Mac tool frame for screen "Project 1" -> setter -> title for Project 1.
    flash[:] = b"\xff" * FLASH_SIZE
    _open, frame = encode_frames(1, "Amazing Grace")
    # 08009048 normalizes the SysEx project byte: 0 = current project, else byte - 1.
    normalized = frame[7] - 1
    assert frame[7] == 1 and normalized == 0
    uc.mem_write(struct_addr, b"\0\0" + bytes((normalized,)) + b"\0" * 5 + bytes((frame[8],)))
    uc.mem_write(data_addr, frame[13:29])
    execute(set_hook, {
        UC_ARM_REG_R1: 0xDEADBEEF,
        UC_ARM_REG_R4: struct_addr,
        UC_ARM_REG_R6: 0x20001820,
        UC_ARM_REG_R7: data_addr,
        UC_ARM_REG_R8: frame[12],
    })
    uc.mem_write(output, b"\0" * 32)
    execute(TITLE_HOOK, {
        UC_ARM_REG_R0: output,
        UC_ARM_REG_R1: 100,
        UC_ARM_REG_R2: 0x0805AE68,
        UC_ARM_REG_R3: 1,
    })
    assert bytes(uc.mem_read(output, 14)) == b"Amazing Grace\0", bytes(uc.mem_read(output, 14))
    for neighbour in (2, 16):
        execute(TITLE_HOOK, {
            UC_ARM_REG_R0: output,
            UC_ARM_REG_R1: 100,
            UC_ARM_REG_R2: 0x0805AE68,
            UC_ARM_REG_R3: neighbour,
        })
        assert formatter_calls[-1] == neighbour
    print("PASS: title lookup, stock fallback, per-slot write, sector preservation, length guard, "
          "slot range guard, stock setter passthrough, Mac-tool round trip, header checksum, stack alignment")


def chord_pads(path: Path) -> None:
    """Chord pad write (item 0x78 param 0x7d) through the real SysEx path in kspemu."""
    from ksp_link import EmuLink, frame
    link = EmuLink(str(path))
    emu = link.emu
    block = lambda proj: bytes(emu.nor[(proj - 1) * 0x20000 + 0x1FEF0:(proj - 1) * 0x20000 + 0x1FFF0])
    pad_state = 0xC01EF800
    emu.uc.mem_write(pad_state, b"ZDAR")
    emu.uc.mem_write(pad_state + 6, b"\x02")                  # RAM copy holds project 3
    emu.uc.mem_write(pad_state + 112, b"\x01")                # with an undo pending
    pads = [[60, 64, 67], [], [62, 65, 69, 72, 74]]
    link.set_chord_pads(3, 3, pads)
    b = block(3)
    assert b[:8] == b"CHD1" + b"\xff" * 4, b[:8]
    want = bytes(sum(([*p] + [0xFF] * (5 - len(p)) for p in pads), [])) + b"\xff" * 65
    assert b[88:168] == want and b[8:88] == b"\xff" * 80 and b[168:] == b"\xff" * 88
    assert bytes(emu.uc.mem_read(pad_state + 6, 1)) == b"\xff", "RAM copy not dropped"
    assert bytes(emu.uc.mem_read(pad_state + 112, 1)) == b"\x00", "undo not cleared"
    assert all(block(p) == b"\xff" * 256 for p in (1, 2, 4, 16))
    link.set_chord_pads(3, 2, [[48, 55]])                      # another track keeps track 3
    b2 = block(3)
    assert b2[8:10] == bytes((48, 55)) and b2[88:168] == want
    link.set_name(3, "Song")                                   # name and a stock commit keep it
    link.open(3)
    link.set(3, 0x6B, 0x7C, 1, [0x20])
    link.commit(3)
    assert block(3) == b2 and emu.nor[2 * 0x20000 + 0x1FFF0:2 * 0x20000 + 0x1FFF5] == b"Song\0"
    before = bytes(emu.nor)
    link.send(frame(0x0C, 3, 0x7D, 1, 0x78, 4, 80, *[60] * 80))   # track index past 4
    link.send(frame(0x0C, 3, 0x7D, 1, 0x78, 1, 79, *[60] * 79))   # short payload
    assert bytes(emu.nor) == before and not emu.errors, emu.errors
    print("PASS: chord pad write via SysEx (block layout, empty-block init, per-track update, RAM copy "
          "dropped, other projects untouched, survives name write + stock commit, guards)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: test_names_hooks.py patched-main.bin")
    run(Path(sys.argv[1]))
    chord_pads(Path(sys.argv[1]))
