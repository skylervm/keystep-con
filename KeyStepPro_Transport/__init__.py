"""MMC transport and Con relative tempo control on the assigned KeyStep Pro ports."""

from _Framework import Task
from random import SystemRandom
from _Framework.ControlSurface import ControlSurface
from _Framework.SysexValueControl import SysexValueControl


def create_instance(c_instance):
    return KeyStepProTransport(c_instance)


class KeyStepProTransport(ControlSurface):
    def __init__(self, c_instance):
        super(KeyStepProTransport, self).__init__(c_instance)
        self._suggested_input_port = "KeyStep Pro"
        self._suggested_output_port = "KeyStep Pro"
        self._active = True
        self._tempo_session = SystemRandom().randrange(1, 1 << 21)
        self._tempo_session_bytes = self._encode21(self._tempo_session)
        with self.component_guard():
            # Listen to universal real-time SysEx on the assigned input only.
            # The callback receives bytes after this prefix, without the F7.
            self._mmc = SysexValueControl(
                message_prefix=(0xF0, 0x7F), name="KeyStep_MMC_Input"
            )
            self._mmc.add_value_listener(self._on_mmc)
            self._tempo = SysexValueControl(
                message_prefix=(0xF0, 0x7D, 0x4B, 0x53, 1, 2), name="KeyStep_Tempo_Input"
            )
            self._tempo.add_value_listener(self._on_tempo)
        self.song().add_tempo_listener(self._send_heartbeat)
        self._send_heartbeat()
        self._heartbeat_task = self._tasks.add(
            Task.loop(Task.wait(1.0), Task.run(self._send_heartbeat))
        )
        self.log_message("KeyStepPro_Transport v2.0 ready (MMC + Con tempo)")

    @staticmethod
    def _encode21(value):
        return (value & 127, (value >> 7) & 127, (value >> 14) & 127)

    def _heartbeat_message(self, enabled):
        bpm = max(2000, min(99900, int(round(self.song().tempo * 100))))
        return ((0xF0, 0x7D, 0x4B, 0x53, 1, 1, enabled) + self._tempo_session_bytes
                + self._encode21(bpm) + (0xF7,))

    def _send_heartbeat(self):
        if self._active:
            self._send_midi(self._heartbeat_message(1), optimized=False)

    def _on_tempo(self, value):
        if not self._active or len(value) != 6:
            return
        if any(byte < 0 or byte > 0x7F for byte in value):
            return
        session = value[0] | (value[1] << 7) | (value[2] << 14)
        if session != self._tempo_session:
            return
        flags, low, high = value[3:]
        magnitude = low | (high << 7)
        if flags > 3 or not 1 <= magnitude <= 255:
            return
        step = 0.01 if flags & 2 else 1.0
        direction = -1 if flags & 1 else 1
        song = self.song()
        song.tempo = max(20.0, min(999.0, song.tempo + direction * magnitude * step))

    def disconnect(self):
        self._active = False
        if self.song().tempo_has_listener(self._send_heartbeat):
            self.song().remove_tempo_listener(self._send_heartbeat)
        self._heartbeat_task.kill()
        self._send_midi(self._heartbeat_message(0), optimized=False)
        super(KeyStepProTransport, self).disconnect()

    def _on_mmc(self, value):
        # MMC transport has a device ID, sub-ID 06, then one command byte.
        if len(value) != 3 or value[1] != 0x06:
            return
        if any(byte < 0 or byte > 0x7F for byte in value):
            return

        command = value[2]
        song = self.song()
        if command in (0x02, 0x03):
            if not song.is_playing:
                song.is_playing = True
            action = "play"
        elif command in (0x01, 0x09):
            if song.is_playing:
                song.is_playing = False
            # KeyStep Pro 2.5.14 sends no MMC Record Exit when Record is
            # pressed a second time. Stop is the reliable recording end.
            if command == 0x01 and song.record_mode:
                song.record_mode = False
            action = "stop" if command == 0x01 else "pause"
        elif command in (0x06, 0x08):
            if not song.record_mode:
                song.record_mode = True
            action = "record on"
        elif command == 0x07:
            if song.record_mode:
                song.record_mode = False
            action = "record off"
        else:
            return
        self.log_message("KeyStepPro_Transport: " + action)
