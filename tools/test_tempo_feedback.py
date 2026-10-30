"""Live feedback through real USB reception, renderers and firmware snprintf."""
import unittest

from unicorn import UC_HOOK_CODE
from firmware_models import MODELS, model_address
from test_tempo_hooks import Fixture, heartbeat, SESSION, SEQ
from test_display_paths import setup_renderer, OWNER, DISPLAY
from test_tempo_paths import application_tick_us


def observe_refreshes(f):
    calls = []
    addresses = {model_address(0x0802546C, f.name), model_address(0x08025494, f.name)}

    def trace(_u, address, _size, _data):
        if address in addresses:
            calls.append(address)

    f.uc.hook_add(UC_HOOK_CODE, trace)
    return calls


class TempoFeedback(unittest.TestCase):
    def test_host_display_holds_until_true_three_second_expiry(self):
        for name in MODELS:
            for view in (0, 1):
                with self.subTest(model=name, view=view):
                    f = Fixture(name)
                    entry, _source, captured = setup_renderer(f, stock=False, view=view)
                    tick_us = application_tick_us(f.model)
                    f.usb(heartbeat(bpm=13650))
                    for elapsed_us in (0, 1162000, 2999000, 3000000):
                        f.tick(10000 + elapsed_us // tick_us)
                        f.poll()
                        # Invalidate the native painted-value cache to exercise redraw.
                        f.uc.mem_write(DISPLAY + (0x118 if view else 0x112), b"\0\0")
                        captured.clear()
                        f.call(entry, DISPLAY)
                        self.assertIn(("bpm", "136.50 BPM"), captured)
                    f.tick(10000 + 3000000 // tick_us + 1)
                    f.poll()
                    captured.clear()
                    f.call(entry, DISPLAY)
                    self.assertIn(("bpm", "120.00 BPM" if view else "120 BPM"), captured)

    def test_host_value_renders_without_changing_project_or_menu_data(self):
        for name in MODELS:
            for view in (0, 1):
                for bpm in (2000, 14725, 77536, 99900):
                    with self.subTest(model=name, view=view, bpm=bpm):
                        f = Fixture(name)
                        entry, source, captured = setup_renderer(f, stock=False, view=view)
                        owner_before = bytes(f.uc.mem_read(OWNER, 256))
                        project_before = bytes(f.uc.mem_read(SEQ, 0x2000))
                        calls = observe_refreshes(f)
                        f.usb(heartbeat(bpm=bpm))
                        f.poll()
                        self.assertEqual(len(calls), 1)
                        f.call(entry, DISPLAY)
                        expected = f"{bpm // 100}.{bpm % 100:02d} BPM"
                        self.assertIn(("bpm", expected), captured)
                        self.assertEqual(bytes(f.uc.mem_read(OWNER, 256)), owner_before)
                        self.assertEqual(bytes(f.uc.mem_read(SEQ, 0x2000)), project_before)
                        self.assertEqual(bytes(f.uc.mem_read(source + 2, 2)), b"\xe0\x2e")  # Still 120.00.
                        captured.clear()
                        f.usb(heartbeat(bpm=bpm))
                        f.poll()
                        self.assertEqual(len(calls), 1, "equal heartbeat requeued a painted value")
                        f.call(entry, DISPLAY)
                        self.assertFalse(any(kind == "bpm" for kind, _text in captured))

    def test_off_page_feedback_is_silent_and_draws_on_return(self):
        for name in MODELS:
            for view in (0, 1):
                for other in (0xF, 0x60):  # Con note popup and a menu.
                    with self.subTest(model=name, view=view, other=other):
                        f = Fixture(name)
                        entry, _source, captured = setup_renderer(f, stock=False, view=view)
                        f.uc.mem_write(OWNER + 0xC, bytes([other]))
                        before = bytes(f.uc.mem_read(OWNER, 256))
                        calls = observe_refreshes(f)
                        f.usb(heartbeat(bpm=14550))
                        f.poll()
                        self.assertEqual(calls, [])
                        self.assertEqual(bytes(f.uc.mem_read(OWNER, 256)), before)
                        f.uc.mem_write(OWNER + 0xC, bytes([view]))
                        f.usb(heartbeat(bpm=14550))
                        f.poll()
                        self.assertEqual(len(calls), 1)
                        f.call(entry, DISPLAY)
                        self.assertIn(("bpm", "145.50 BPM"), captured)

    def test_disable_and_expiry_force_stock_redraw_even_with_equal_low_word(self):
        for name in MODELS:
            for view in (0, 1):
                for disable in (False, True):
                    with self.subTest(model=name, view=view, disable=disable):
                        f = Fixture(name)
                        entry, _source, captured = setup_renderer(f, stock=False, view=view)
                        f.usb(heartbeat(bpm=77536))  # Its low word equals stock's 12000.
                        f.poll()
                        f.call(entry, DISPLAY)
                        self.assertIn(("bpm", "775.36 BPM"), captured)
                        captured.clear()
                        if disable:
                            f.usb(heartbeat(enabled=0, bpm=77536))
                            f.poll()
                        else:
                            f.tick(40001)
                            f.poll()
                        f.call(entry, DISPLAY)
                        self.assertIn(("bpm", "120 BPM" if view == 0 else "120.00 BPM"), captured)
                        self.assertEqual(f.word(0xC01EF80C), 0)

    def test_silent_expiry_is_queued_by_foreground_poll_and_draws_stock(self):
        for name in MODELS:
            for view in (0, 1):
                with self.subTest(model=name, view=view):
                    f = Fixture(name)
                    entry, _source, captured = setup_renderer(f, stock=False, view=view)
                    calls = observe_refreshes(f)
                    f.usb(heartbeat(bpm=13300))
                    self.assertEqual(calls, [], "RX queued a display call")
                    f.poll()
                    pending = bytes(f.uc.mem_read(DISPLAY, 0x40))
                    f.poll()
                    self.assertEqual(bytes(f.uc.mem_read(DISPLAY, 0x40)), pending,
                                     "duplicate poll changed the native pending callback")
                    f.call(entry, DISPLAY)
                    captured.clear()
                    calls.clear()
                    f.tick(40001)
                    f.poll()  # No disable frame and no forced renderer call yet.
                    self.assertEqual(len(calls), 1, "expiry did not request a redraw")
                    f.call(entry, DISPLAY)
                    self.assertIn(("bpm", "120 BPM" if view == 0 else "120.00 BPM"), captured)
                    calls.clear()
                    f.poll()
                    self.assertEqual(calls, [], "painted stock value was requeued")

    def test_other_project_preview_keeps_its_stock_tempo(self):
        for name in MODELS:
            with self.subTest(model=name):
                f = Fixture(name)
                entry, source, captured = setup_renderer(f, stock=False, view=0)
                f.uc.mem_write(source, b"\x02")
                calls = observe_refreshes(f)
                f.usb(heartbeat(bpm=14725))
                f.poll()
                self.assertEqual(calls, [])
                f.call(entry, DISPLAY)
                self.assertIn(("bpm", "120 BPM"), captured)

    def test_reconnect_same_value_after_stock_render_draws_host_again(self):
        for name in MODELS:
            for view in (0, 1):
                with self.subTest(model=name, view=view):
                    f = Fixture(name)
                    entry, _source, captured = setup_renderer(f, stock=False, view=view)
                    f.usb(heartbeat(bpm=13300))
                    f.poll()
                    f.call(entry, DISPLAY)
                    f.usb(heartbeat(enabled=0, bpm=13300))
                    f.poll()
                    f.call(entry, DISPLAY)
                    captured.clear()
                    f.usb(heartbeat(session=SESSION + 1, bpm=13300))
                    f.poll()
                    f.call(entry, DISPLAY)
                    self.assertIn(("bpm", "133.00 BPM"), captured)


if __name__ == "__main__":
    unittest.main(verbosity=2)
