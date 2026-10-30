"""Test transport against a fake song; never connect to a MIDI device or Live."""

import importlib.util
from contextlib import nullcontext
from pathlib import Path
import sys
import types
import unittest


class FakeSong:
    def __init__(self):
        self.is_playing = False
        self.record_mode = False
        self._tempo = 133.0
        self._tempo_listeners = []
        self.current_song_time = 12.0

    @property
    def tempo(self):
        return self._tempo

    @tempo.setter
    def tempo(self, value):
        changed = value != self._tempo
        self._tempo = value
        if changed:
            for listener in list(self._tempo_listeners):
                listener()

    def add_tempo_listener(self, listener):
        self._tempo_listeners.append(listener)

    def tempo_has_listener(self, listener):
        return listener in self._tempo_listeners

    def remove_tempo_listener(self, listener):
        self._tempo_listeners.remove(listener)


class FakeSurface:
    def __init__(self, c_instance):
        self.instance = c_instance
        self.messages = []
        self.midi = []
        self._tasks = FakeTaskGroup()
        self.disconnected = False

    def component_guard(self):
        return nullcontext()

    def song(self):
        return self.instance

    def log_message(self, message):
        self.messages.append(message)

    def _send_midi(self, message, optimized=True):
        self.midi.append((message, optimized))

    def disconnect(self):
        self.disconnected = True


class FakeTaskGroup:
    def add(self, task):
        return task


class FakeLoop:
    def __init__(self, *tasks):
        self.tasks = tasks
        self.killed = False

    def kill(self):
        self.killed = True


class FakeSysexInput:
    def __init__(self, message_prefix, name):
        self.prefix = message_prefix
        self.listener = None

    def add_value_listener(self, listener):
        self.listener = listener

    def receive(self, message):
        # Route only full messages with the registered prefix, as Live does.
        if message[:len(self.prefix)] == self.prefix and message[-1:] == (0xF7,):
            self.listener(message[len(self.prefix):-1])


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        modules = {
            "_Framework": types.ModuleType("_Framework"),
            "_Framework.ControlSurface": types.ModuleType("_Framework.ControlSurface"),
            "_Framework.SysexValueControl": types.ModuleType("_Framework.SysexValueControl"),
        }
        modules["_Framework.ControlSurface"].ControlSurface = FakeSurface
        modules["_Framework.SysexValueControl"].SysexValueControl = FakeSysexInput
        modules["_Framework"].Task = types.SimpleNamespace(
            loop=FakeLoop, wait=lambda seconds: seconds, run=lambda callback: callback
        )
        cls.previous = {name: sys.modules.get(name) for name in modules}
        sys.modules.update(modules)
        path = Path(__file__).parents[1] / "KeyStepPro_Transport/__init__.py"
        spec = importlib.util.spec_from_file_location("transport_under_test", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        for name, module in cls.previous.items():
            if module is None:
                del sys.modules[name]
            else:
                sys.modules[name] = module

    def setUp(self):
        self.song = FakeSong()
        self.surface = self.module.create_instance(self.song)

    def command(self, command, device=0x7F):
        self.surface._mmc.receive((0xF0, 0x7F, device, 0x06, command, 0xF7))

    def tempo(self, flags=0, low=1, high=0, session=None):
        token = self.surface._tempo_session_bytes if session is None else self.surface._encode21(session)
        self.surface._tempo.receive((0xF0, 0x7D, 0x4B, 0x53, 1, 2) + token + (flags, low, high, 0xF7))

    def test_tempo_turns_follow_laptop_edits_stopped_and_playing(self):
        for playing in (False, True):
            self.song.is_playing = playing
            self.song.tempo = 120.0
            self.tempo(low=3)
            self.assertEqual(self.song.tempo, 123.0)
            self.song.tempo = 147.5
            self.tempo(flags=1, low=2)
            self.assertEqual(self.song.tempo, 145.5)
            self.tempo(flags=2, low=5)
            self.assertAlmostEqual(self.song.tempo, 145.55)
            self.tempo(flags=3, low=2)
            self.assertAlmostEqual(self.song.tempo, 145.53)
            self.assertEqual(self.song.is_playing, playing)
            self.assertEqual(self.song.current_song_time, 12.0)
            self.assertFalse(self.song.record_mode)
        self.assertTrue(all(message[:6] == (0xF0, 0x7D, 0x4B, 0x53, 1, 1)
                            for message, _optimized in self.surface.midi))  # Host-value feedback only; no clock/turn echo.

    def test_tempo_bounds_and_full_byte_magnitude(self):
        self.song.tempo = 990.0
        self.tempo(low=127, high=1)
        self.assertEqual(self.song.tempo, 999.0)
        self.song.tempo = 21.0
        self.tempo(flags=1, low=127, high=1)
        self.assertEqual(self.song.tempo, 20.0)
        self.tempo(flags=2)
        self.assertAlmostEqual(self.song.tempo, 20.01)

    def test_bad_tempo_messages_and_other_commands_are_ignored(self):
        messages = [
            (0xF0, 0x7D, 0x4B, 0x53, 1, 1, 1, 0xF7),
            (0xF0, 0x7D, 0x4B, 0x53, 2, 2, 0, 1, 0, 0xF7),
            (0xF0, 0x7D, 0x4B, 0x53, 1, 2, 0, 1, 0),
        ]
        for payload in [(0, 0, 0), (4, 1, 0), (0, 0, 2), (0, 128, 0), (0, -1, 0), (0, 1), (0, 1, 0, 0)]:
            messages.append((0xF0, 0x7D, 0x4B, 0x53, 1, 2) + self.surface._tempo_session_bytes + payload + (0xF7,))
        for message in messages:
            with self.subTest(message=message):
                self.surface._tempo.receive(message)
                self.assertEqual(self.song.tempo, 133.0)

    def test_heartbeat_repeats_and_disconnect_disables_it(self):
        heartbeat = (self.surface._heartbeat_message(1), False)
        self.assertEqual(self.surface.midi, [heartbeat])
        wait, callback = self.surface._heartbeat_task.tasks
        self.assertEqual(wait, 1.0)
        callback()
        callback()
        self.assertEqual(self.surface.midi, [heartbeat] * 3)
        self.surface.disconnect()
        self.assertEqual(self.surface.midi[-1], (self.surface._heartbeat_message(0), False))
        self.assertTrue(self.surface._heartbeat_task.killed)
        self.assertTrue(self.surface.disconnected)
        before = list(self.surface.midi)
        callback()
        self.tempo()
        self.assertEqual(self.surface.midi, before)
        self.assertEqual(self.song.tempo, 133.0)

    def test_laptop_tempo_change_sends_immediate_display_feedback(self):
        self.song.tempo = 147.25
        self.assertEqual(len(self.surface.midi), 2)
        message, optimized = self.surface.midi[-1]
        self.assertFalse(optimized)
        self.assertEqual(message, self.surface._heartbeat_message(1))
        self.assertEqual(message[-4:-1], self.surface._encode21(14725))
        self.surface.disconnect()
        before = list(self.surface.midi)
        self.song.tempo = 150.0
        self.assertEqual(self.surface.midi, before)

    def test_stale_session_turns_are_ignored(self):
        old_session = self.surface._tempo_session ^ 1
        self.tempo(session=old_session)
        self.assertEqual(self.song.tempo, 133.0)

    def test_play_pause_continue_stop_preserve_position_and_tempo(self):
        for command, playing in [(2, True), (9, False), (3, True), (1, False)]:
            self.command(command)
            self.assertEqual(self.song.is_playing, playing)
            self.assertEqual(self.song.tempo, 133.0)
            self.assertEqual(self.song.current_song_time, 12.0)

    def test_record_strobe_and_exit_are_explicit_and_idempotent(self):
        for command, recording in [(6, True), (6, True), (7, False), (7, False), (8, True)]:
            self.command(command)
            self.assertEqual(self.song.record_mode, recording)
            self.assertFalse(self.song.is_playing)

    def test_addressed_mmc_is_accepted_on_the_assigned_port(self):
        self.command(2, device=3)
        self.assertTrue(self.song.is_playing)

    def test_captured_keystep_sequence_ends_recording_with_stop(self):
        # Captured physical sequence: Play, Stop, Record, Record, Stop.
        # The second Record press emitted no MMC message.
        for command in (2, 1, 6):
            self.command(command)
        self.assertTrue(self.song.record_mode)
        self.command(1)
        self.assertFalse(self.song.record_mode)
        self.assertFalse(self.song.is_playing)

    def test_stop_disarms_record_even_before_playback_starts(self):
        self.command(6)
        self.assertTrue(self.song.record_mode)
        self.command(1)
        self.assertFalse(self.song.record_mode)

    def test_pause_preserves_record_arm(self):
        self.command(6)
        self.command(2)
        self.command(9)
        self.assertFalse(self.song.is_playing)
        self.assertTrue(self.song.record_mode)

    def test_unrelated_midi_and_malformed_mmc_do_nothing(self):
        messages = [
            (0xFA,), (0xFB,), (0xFC,), (0xF8,),
            (0x90, 60, 127), (0xB0, 54, 127),
            (0xF0, 0x7E, 0x7F, 6, 2, 0xF7),
            (0xF0, 0x7F, 0x7F, 1, 2, 0xF7),
            (0xF0, 0x7F, 0x7F, 6, 0xF7),
            (0xF0, 0x7F, 0x7F, 6, 2, 0, 0xF7),
            (0xF0, 0x7F, 0x80, 6, 2, 0xF7),
            (0xF0, 0x7F, 0x7F, 6, 4, 0xF7),
            (0xF0, 0x7F, 0x7F, 6, 2),
        ]
        for message in messages:
            with self.subTest(message=message):
                self.surface._mmc.receive(message)
                self.assertFalse(self.song.is_playing)
                self.assertFalse(self.song.record_mode)
        self.assertEqual(len(self.surface.messages), 1)


if __name__ == "__main__":
    unittest.main()
