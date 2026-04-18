"""
Testes unitarios de selecao dinamica de entrada de audio.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.voice.audio_capture import SoundDeviceCapture


class FakeSoundDevice:
    def __init__(self, fail_open_devices=()):
        self.default = type("DefaultDevice", (), {"device": [1, 5]})()
        self.fail_open_devices = set(fail_open_devices)
        self.opened = []
        self.devices = [
            {"name": "Mapeador", "max_input_channels": 2, "default_samplerate": 44100.0},
            {"name": "Virtual Desktop Audio", "max_input_channels": 1, "default_samplerate": 44100.0},
            {"name": "Microfone (USB Audio Device)", "max_input_channels": 1, "default_samplerate": 48000.0},
            {"name": "Speaker", "max_input_channels": 0, "default_samplerate": 44100.0},
            {"name": "Headset Microphone (OCULUSVAD Wave Microphone Headphone)", "max_input_channels": 1, "default_samplerate": 48000.0},
        ]

    def check_input_settings(self, device, channels, samplerate, dtype):
        if device == 4 and samplerate != 48000:
            raise ValueError("Invalid sample rate")

    def query_devices(self, device=None):
        if device is None:
            return self.devices
        return self.devices[device]

    def InputStream(self, samplerate, channels, dtype, device, blocksize, callback):
        if device in self.fail_open_devices:
            raise ValueError("Invalid device")
        self.opened.append((device, samplerate))
        return object()


def test_configure_input_device_uses_device_default_sample_rate(monkeypatch):
    fake_sd = FakeSoundDevice()
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    capture = SoundDeviceCapture(sample_rate=16000, channels=1, device=4)

    assert capture.device == 4
    assert capture.sample_rate == 48000


def test_make_queue_stream_falls_back_to_usb_before_default(monkeypatch):
    fake_sd = FakeSoundDevice(fail_open_devices={4})
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    capture = SoundDeviceCapture(sample_rate=48000, channels=1, device=4)
    stream, audio_q = capture._make_queue_stream(4800)

    assert stream is not None
    assert audio_q is not None
    assert fake_sd.opened[0] == (2, 48000)
    assert capture.device == 2
