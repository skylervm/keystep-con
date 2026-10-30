"""Exercise both directions across the real emulated firmware and fake Live."""
from pathlib import Path
import sys
import unittest

import test_transport as transport_fakes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from firmware_models import MODELS  # noqa: E402
from test_tempo_hooks import Fixture, SEQ  # noqa: E402
from test_display_paths import setup_renderer, DISPLAY  # noqa: E402


class EndToEndTempo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        transport_fakes.TransportTests.setUpClass()
        cls.module = transport_fakes.TransportTests.module

    @classmethod
    def tearDownClass(cls):
        transport_fakes.TransportTests.tearDownClass()

    def test_knob_laptop_display_and_disconnect(self):
        for name in MODELS:
            for playing in (False, True):
                with self.subTest(model=name, playing=playing):
                    song = transport_fakes.FakeSong()
                    song.is_playing = playing
                    surface = self.module.create_instance(song)
                    f = Fixture(name)
                    entry, _source, captured = setup_renderer(f, stock=False, view=1)
                    f.uc.mem_write(SEQ + 0xC, bytes([int(playing)]))
                    project = bytes(f.uc.mem_read(SEQ, 0x2000))

                    def host_to_controller():
                        f.usb(bytes(surface.midi[-1][0]))
                        f.poll()
                        captured.clear()
                        f.call(entry, DISPLAY)

                    def controller_to_host():
                        tail = f.word(f.model.usb_queue + 4)
                        wire = f.wire(tail)
                        f.put(f.model.usb_queue + 4, f.word(f.model.usb_queue))
                        surface._tempo.receive(tuple(wire))

                    host_to_controller()
                    self.assertIn(("bpm", "133.00 BPM"), captured)
                    self.assertEqual(f.turn(magnitude=3), 255)
                    controller_to_host()
                    self.assertEqual(song.tempo, 136.0)
                    host_to_controller()
                    self.assertIn(("bpm", "136.00 BPM"), captured)
                    song.tempo = 147.25
                    host_to_controller()
                    self.assertIn(("bpm", "147.25 BPM"), captured)
                    self.assertEqual(f.turn(direction=1, magnitude=2, fine=True), 255)
                    controller_to_host()
                    self.assertAlmostEqual(song.tempo, 147.23)
                    host_to_controller()
                    self.assertIn(("bpm", "147.23 BPM"), captured)
                    self.assertEqual(song.is_playing, playing)
                    self.assertEqual(bytes(f.uc.mem_read(SEQ, 0x2000)), project)
                    self.assertTrue(all(msg[:6] == (0xF0, 0x7D, 0x4B, 0x53, 1, 1)
                                        for msg, _optimized in surface.midi))
                    surface.disconnect()
                    host_to_controller()
                    self.assertEqual(f.turn(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
