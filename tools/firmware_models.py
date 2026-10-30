"""Exact stock inputs and verified tempo/USB paths. This module never patches firmware."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import struct


@dataclass(frozen=True)
class FirmwareModel:
    name: str
    main_entry: str
    ui_entry: str
    main_sha256: str
    model_header: int
    payload_size: int
    encoder_up: int
    encoder_down: int
    loop_continue: int
    clock_mode_get: int
    tempo_get: int
    seq_pointer: int
    usb_enqueue: int
    usb_convert: int
    usb_queue: int
    parser: int
    tick_get: int
    tick_counter: int

    def read_stock(self, directory: Path) -> bytes:
        return self.validate_stock((directory / self.main_entry).read_bytes())

    def validate_stock(self, image: bytes) -> bytes:
        if sha256(image).hexdigest() != self.main_sha256:
            raise ValueError(f"{self.name}: unsupported stock image hash")
        if struct.unpack_from("<I", image)[0] != self.model_header:
            raise ValueError(f"{self.name}: model header mismatch")
        length_word = struct.unpack_from("<I", image, 4)[0]
        if len(image) != self.payload_size + 64 or length_word >> 8 != self.payload_size:
            raise ValueError(f"{self.name}: payload length mismatch")
        if sum(image[:64]) & 255 or (sum(image[64:]) + image[9]) & 255:
            raise ValueError(f"{self.name}: checksum mismatch")
        return image[64:]


MODELS = {
    "original": FirmwareModel(
        "original", "keysteppro_main__fw2_5_20_2085__2024_03_04.bin",
        "keysteppro_ui__fw0_0_1_1823__2024_03_04.bin",
        "5cef3d2fa93610028dcb9a92c3d09949e6b56de79ff0d05050b61a57ff86fb15",
        0x02181C75, 0x551AC,
        0x0801271C, 0x08013BD2, 0x08012358, 0x0802AA62, 0x0802AA90,
        0x20001498, 0x0801A49C, 0x0801A504, 0x20004F14, 0x0803D586,
        0x0803E440, 0x20006218,
    ),
    "chroma": FirmwareModel(
        "chroma", "keysteppro_main_chroma__fw2_5_20_375__2024_03_04.bin",
        "keysteppro_ui_chroma__fw0_0_1_336__2024_03_03.bin",
        "cfc18db3e7f2c54ad0b123a3a8efc6adf75ddaef9789230ad8e0285585fe6616",
        0x22181C75, 0x55884,
        0x08012930, 0x08013DE6, 0x0801256C, 0x0802AEA6, 0x0802AED0,
        0x2000149C, 0x0801A5F8, 0x0801A660, 0x20004F34, 0x0803DAE6,
        0x0803E9A0, 0x20006238,
    ),
}

# Derived from matching the exact stock images, checked against stock callees.
# The Chroma project stride is 0x1000; field offsets inside each project match.
# Scale masks and track colours precede the inserted initialized-data word and
# remain at their original addresses. Other RAM locations must be explicit.
CHROMA_ADDRESSES = {
    0x0800CCA8: 0x0800CDE0,
    0x0800DF28: 0x0800E0F0,
    0x0800DF32: 0x0800E0FA,
    0x0800E328: 0x0800E4F0,
    0x0800E84A: 0x0800EA5C,
    0x0800EFBC: 0x0800F1D0,
    0x0800F358: 0x0800F56C,
    0x080108A4: 0x08010AB8,
    0x080126EA: 0x080128FE,
    0x08012708: 0x0801291C,
    0x08012720: 0x08012934,
    0x08013BD6: 0x08013DEA,
    0x080156F6: 0x0801590A,
    0x08015EE0: 0x080160F4,
    0x08016482: 0x0801667E,
    0x0801696A: 0x08016B16,
    0x08017E28: 0x08017F84,
    0x08017C68: 0x08017DC4,
    0x08017E70: 0x08017FCC,
    0x080181D2: 0x0801832E,
    0x080181D8: 0x08018334,
    0x08018B58: 0x08018CB4,
    0x0801A8A6: 0x0801AA02,
    0x0801A6E0: 0x0801A83C,
    0x0801F7BE: 0x0801F94A,
    0x0801F96C: 0x0801FAF8,
    0x0801F310: 0x0801F49C,
    0x0801FAA0: 0x0801FC2C,
    0x08020E4E: 0x08020FDA,
    0x08025274: 0x08025580,
    0x0802546C: 0x08025778,
    0x08025494: 0x080257A0,
    0x0802654C: 0x08026858,
    0x08026560: 0x0802686C,
    0x08026690: 0x0802699C,
    0x08029E78: 0x0802A184,
    0x0802A244: 0x0802A550,
    0x0802A88C: 0x0802AB92,
    0x0802CAF0: 0x0802D188,
    0x0802CEAC: 0x0802D504,
    0x0802D160: 0x0802D9C8,
    0x0802F340: 0x0802FA94,
    0x0803094C: 0x0803108C,
    0x08030BD6: 0x080312EE,
    0x080347C8: 0x08034E0C,
    0x08034AB4: 0x080350F8,
    0x0803B0D0: 0x0803B660,
    0x0803D586: 0x0803DAE6,
    0x0803E440: 0x0803E9A0,
    0x0803F6E0: 0x0803FC40,
    0x0803F774: 0x0803FCD4,
    0x0803F814: 0x0803FD74,
    0x0803F944: 0x0803FEA4,
    0x08046858: 0x08046DB8,
    0x080470EC: 0x080476DC,
    0x08047148: 0x08047738,
    0x080475D8: 0x08047C2C,
    0x08047D36: 0x080483B0,
    0x0804E700: 0x0804ED80,
    0x0804AEBA: 0x0804B53A,
    0x080500D8: 0x08050758,
    0x08053EB8: 0x08054564,
    0x08054C2C: 0x080552D8,
    0x0805761C: 0x08057CC8,
    0x080589A4: 0x08059050,
    0x08059274: 0x0805992C,
    0x0805AE68: 0x0805B540,
    0x0805AF3C: 0x0805B614,
    0x0805CB60: 0x0805D234,
    0x0805D1AC: 0x0805D884,
    0x20000004: 0x20000004,
    0x20000058: 0x20000058,
    0x200001A4: 0x200001A8,
    0x20000650: 0x20000654,
    0x20000671: 0x20000675,
    0x20000674: 0x20000678,
    0x20000874: 0x20000878,
    0x20001490: 0x20001494,
    0x20001498: 0x2000149C,
    0x200014A8: 0x200014AC,
    0x200014B8: 0x200014BC,
    0x200014C8: 0x200014CC,
    0x200014D7: 0x200014DB,
    0x20001510: 0x20001514,
    0x200017F8: 0x200017FC,
    0x20001800: 0x20001804,
    0x20001804: 0x20001808,
    0x20001820: 0x20001824,
    0x20002D5B: 0x20002D7B,
    0x20002C7C: 0x20002C9C,
    0x20003D91: 0x20003DB1,
    0x20003D9D: 0x20003DBD,
    0x20003DA0: 0x20003DC0,
    0x20004DA8: 0x20004DC8,
    0x20004DAD: 0x20004DCD,
    0x20004DDC: 0x20004DFC,
    0x20004F14: 0x20004F34,
}

# Chroma's stock LED lifecycle differs. Enumerate its own callers rather than
# assuming a counterpart exists for every original-model call site.
CHROMA_LED_FLUSH_CALLS = (
    0x0800E4F0, 0x0800EA5C, 0x08016B16, 0x0801F94A, 0x0802AB92,
    0x0802D7FE, 0x0802D96E, 0x080312EE, 0x0805212C,
)

TEMPO_PATHS = {
    "original": {"usb_rx": 0x08018A74, "usb_drain": 0x08018B24, "usb_rx_call": 0x08018B58,
                 "din_rx": 0x08018B76, "din_rx_call": 0x08018B7C, "byte_parser": 0x0801A8A6,
                 "boot_call": 0x08016482, "sdram_init": 0x08017C68,
                 "usb_drain_call": 0x08049602},
    "chroma": {"usb_rx": 0x08018BD0, "usb_drain": 0x08018C80, "usb_rx_call": 0x08018CB4,
               "din_rx": 0x08018CD2, "din_rx_call": 0x08018CD8, "byte_parser": 0x0801AA02,
               "boot_call": 0x0801667E, "sdram_init": 0x08017DC4,
               "usb_drain_call": 0x08049C82},
}

FOREGROUND_PATHS = {
    "original": {"call": 0x08016976, "update": 0x0801F310},
    "chroma": {"call": 0x08016B20, "update": 0x0801F49C},
}

DISPLAY_PATHS = {
    "original": (
        (0x0802655A, "b4f812117288", "tempo_project_values"),
        (0x08026688, "b4f81811b8f80230", "tempo_screen_values"),
    ),
    "chroma": (
        (0x08026866, "b4f812117288", "tempo_project_values"),
        (0x08026994, "b4f81811b8f80230", "tempo_screen_values"),
    ),
}


def model_address(address: int, model: str) -> int:
    if model == "original":
        return address
    if model != "chroma":
        raise ValueError(f"unsupported model: {model}")
    if address in CHROMA_ADDRESSES:
        return CHROMA_ADDRESSES[address]
    if 0x08008000 <= address < 0x08080000:
        return CHROMA_ADDRESSES.get(address & ~1, address & ~1) | (address & 1)
    return address
