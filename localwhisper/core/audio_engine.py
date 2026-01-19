"""
Audio Engine for LocalWhisper

Handles real-time audio capture from the microphone with minimal latency.
"""

import threading
import queue
import time
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
from collections import deque

import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

from localwhisper.core.config import AudioSettings


@dataclass
class AudioDevice:
    """Represents an audio input device."""
    index: int
    name: str
    channels: int
    sample_rate: int
    is_default: bool = False


class AudioEngineError(Exception):
    """Base exception for audio engine errors."""
    pass


class MicrophoneNotFoundError(AudioEngineError):
    """Raised when no microphone is available."""
    pass


class AudioCaptureError(AudioEngineError):
    """Raised when audio capture fails."""
    pass


class AudioEngine:
    """
    Real-time audio capture engine.

    Captures audio from the system microphone and provides:
    - Real-time amplitude data for visualization
    - Audio buffer for transcription
    - Device enumeration and selection
    """

    def __init__(self, settings: Optional[AudioSettings] = None):
        """
        Initialize the audio engine.

        Args:
            settings: Audio configuration settings
        """
        self.settings = settings or AudioSettings()

        # State
        self._is_recording = False
        self._is_initialized = False

        # Audio data
        self._audio_buffer: deque = deque(maxlen=int(30 * self.settings.sample_rate))  # 30 sec max
        self._amplitude_callback: Optional[Callable[[float], None]] = None
        self._audio_callback: Optional[Callable[[np.ndarray], None]] = None

        # Threading
        self._record_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Backend selection
        self._backend = self._select_backend()

        # PyAudio specific
        self._pyaudio: Optional["pyaudio.PyAudio"] = None
        self._stream = None

    def _select_backend(self) -> str:
        """Select the best available audio backend."""
        if HAS_SOUNDDEVICE:
            return "sounddevice"
        elif HAS_PYAUDIO:
            return "pyaudio"
        else:
            raise AudioEngineError(
                "No audio backend available. Install 'sounddevice' or 'pyaudio'."
            )

    def initialize(self) -> None:
        """Initialize the audio engine and verify microphone access."""
        if self._is_initialized:
            return

        devices = self.list_devices()
        if not devices:
            raise MicrophoneNotFoundError("No audio input devices found.")

        if self._backend == "pyaudio":
            self._pyaudio = pyaudio.PyAudio()

        self._is_initialized = True

    def shutdown(self) -> None:
        """Shutdown the audio engine and release resources."""
        self.stop_recording()

        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None

        self._is_initialized = False

    def list_devices(self) -> List[AudioDevice]:
        """
        List available audio input devices.

        Returns:
            List of AudioDevice objects
        """
        devices = []

        if self._backend == "sounddevice":
            device_list = sd.query_devices()
            default_input = sd.default.device[0]

            for i, dev in enumerate(device_list):
                if dev["max_input_channels"] > 0:
                    devices.append(AudioDevice(
                        index=i,
                        name=dev["name"],
                        channels=dev["max_input_channels"],
                        sample_rate=int(dev["default_samplerate"]),
                        is_default=(i == default_input),
                    ))

        elif self._backend == "pyaudio":
            if not self._pyaudio:
                self._pyaudio = pyaudio.PyAudio()

            default_input = self._pyaudio.get_default_input_device_info()["index"]

            for i in range(self._pyaudio.get_device_count()):
                dev = self._pyaudio.get_device_info_by_index(i)
                if dev["maxInputChannels"] > 0:
                    devices.append(AudioDevice(
                        index=i,
                        name=dev["name"],
                        channels=dev["maxInputChannels"],
                        sample_rate=int(dev["defaultSampleRate"]),
                        is_default=(i == default_input),
                    ))

        return devices

    def get_default_device(self) -> Optional[AudioDevice]:
        """Get the default audio input device."""
        devices = self.list_devices()
        for device in devices:
            if device.is_default:
                return device
        return devices[0] if devices else None

    def set_amplitude_callback(self, callback: Callable[[float], None]) -> None:
        """
        Set callback for real-time amplitude updates.

        Args:
            callback: Function called with amplitude value (0.0 to 1.0)
        """
        self._amplitude_callback = callback

    def set_audio_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        Set callback for audio chunk updates.

        Args:
            callback: Function called with audio data as numpy array
        """
        self._audio_callback = callback

    def start_recording(self) -> None:
        """Start recording audio from the microphone."""
        if self._is_recording:
            return

        if not self._is_initialized:
            self.initialize()

        self._audio_buffer.clear()
        self._stop_event.clear()
        self._is_recording = True

        if self._backend == "sounddevice":
            self._start_sounddevice_recording()
        else:
            self._start_pyaudio_recording()

    def _start_sounddevice_recording(self) -> None:
        """Start recording using sounddevice backend."""
        device_idx = None
        if self.settings.input_device:
            devices = self.list_devices()
            for dev in devices:
                if dev.name == self.settings.input_device:
                    device_idx = dev.index
                    break

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"Audio status: {status}")

            # Convert to float32 and mono if needed
            audio_data = indata[:, 0] if indata.ndim > 1 else indata.flatten()
            audio_data = audio_data.astype(np.float32)

            # Apply gain
            audio_data = audio_data * self.settings.gain

            # Add to buffer
            self._audio_buffer.extend(audio_data)

            # Calculate amplitude for visualization
            if self._amplitude_callback:
                amplitude = np.abs(audio_data).mean()
                # Normalize to 0-1 range (assuming audio is already normalized)
                amplitude = min(1.0, amplitude * 3)  # Scale up for better visualization
                self._amplitude_callback(amplitude)

            # Call audio callback
            if self._audio_callback:
                self._audio_callback(audio_data)

        self._stream = sd.InputStream(
            device=device_idx,
            channels=self.settings.channels,
            samplerate=self.settings.sample_rate,
            blocksize=self.settings.chunk_size,
            dtype=np.float32,
            callback=audio_callback,
        )
        self._stream.start()

    def _start_pyaudio_recording(self) -> None:
        """Start recording using PyAudio backend."""
        device_idx = None
        if self.settings.input_device:
            devices = self.list_devices()
            for dev in devices:
                if dev.name == self.settings.input_device:
                    device_idx = dev.index
                    break

        def record_thread():
            stream = self._pyaudio.open(
                format=pyaudio.paFloat32,
                channels=self.settings.channels,
                rate=self.settings.sample_rate,
                input=True,
                input_device_index=device_idx,
                frames_per_buffer=self.settings.chunk_size,
            )
            self._stream = stream

            try:
                while not self._stop_event.is_set():
                    try:
                        data = stream.read(self.settings.chunk_size, exception_on_overflow=False)
                        audio_data = np.frombuffer(data, dtype=np.float32)

                        # Apply gain
                        audio_data = audio_data * self.settings.gain

                        # Add to buffer
                        self._audio_buffer.extend(audio_data)

                        # Calculate amplitude
                        if self._amplitude_callback:
                            amplitude = np.abs(audio_data).mean()
                            amplitude = min(1.0, amplitude * 3)
                            self._amplitude_callback(amplitude)

                        # Call audio callback
                        if self._audio_callback:
                            self._audio_callback(audio_data)

                    except Exception as e:
                        if not self._stop_event.is_set():
                            print(f"Audio capture error: {e}")
                        break
            finally:
                stream.stop_stream()
                stream.close()

        self._record_thread = threading.Thread(target=record_thread, daemon=True)
        self._record_thread.start()

    def stop_recording(self) -> np.ndarray:
        """
        Stop recording and return the captured audio.

        Returns:
            Numpy array of captured audio samples (float32, 16kHz, mono)
        """
        if not self._is_recording:
            return np.array([], dtype=np.float32)

        self._is_recording = False
        self._stop_event.set()

        # Stop the stream
        if self._backend == "sounddevice" and self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        elif self._backend == "pyaudio":
            if self._record_thread:
                self._record_thread.join(timeout=1.0)
                self._record_thread = None

        # Get audio from buffer
        audio = np.array(list(self._audio_buffer), dtype=np.float32)
        self._audio_buffer.clear()

        return audio

    def get_current_audio(self) -> np.ndarray:
        """
        Get the current audio buffer without stopping recording.

        Returns:
            Copy of the current audio buffer
        """
        return np.array(list(self._audio_buffer), dtype=np.float32)

    def get_recent_audio(self, seconds: float = 0.5) -> np.ndarray:
        """
        Get the most recent audio samples.

        Args:
            seconds: Number of seconds of recent audio to get

        Returns:
            Numpy array of recent audio samples
        """
        samples = int(seconds * self.settings.sample_rate)
        buffer_list = list(self._audio_buffer)
        if len(buffer_list) < samples:
            return np.array(buffer_list, dtype=np.float32)
        return np.array(buffer_list[-samples:], dtype=np.float32)

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    @property
    def buffer_duration(self) -> float:
        """Get the duration of audio in the buffer in seconds."""
        return len(self._audio_buffer) / self.settings.sample_rate

    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()
        return False
