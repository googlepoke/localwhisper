"""
Transcription Engine for LocalWhisper

Handles speech-to-text transcription using faster-whisper for optimized inference.
Supports both GPU (CUDA) and CPU modes with automatic detection.
"""

import threading
import queue
import time
from typing import Optional, Callable, Generator, Tuple, List
from dataclasses import dataclass
from pathlib import Path
import platform

import numpy as np

from localwhisper.core.config import TranscriptionSettings, get_cache_dir, AVAILABLE_MODELS


@dataclass
class TranscriptionResult:
    """Result of a transcription."""
    text: str
    language: str
    confidence: float
    duration: float  # Audio duration in seconds
    processing_time: float  # Time taken to process in seconds
    is_partial: bool = False  # True if this is a streaming partial result


@dataclass
class TranscriptionSegment:
    """A segment of transcribed text with timing information."""
    text: str
    start: float
    end: float
    confidence: float


class TranscriptionEngineError(Exception):
    """Base exception for transcription engine errors."""
    pass


class ModelNotFoundError(TranscriptionEngineError):
    """Raised when the requested model is not found."""
    pass


class TranscriptionEngine:
    """
    Speech-to-text transcription engine using faster-whisper.

    Features:
    - Automatic GPU/CPU detection and selection
    - Streaming transcription support
    - Model caching and management
    - Voice Activity Detection (VAD) integration
    """

    def __init__(self, settings: Optional[TranscriptionSettings] = None):
        """
        Initialize the transcription engine.

        Args:
            settings: Transcription configuration settings
        """
        self.settings = settings or TranscriptionSettings()

        self._model = None
        self._model_name: Optional[str] = None
        self._is_loaded = False

        # Streaming state
        self._streaming_buffer: List[np.ndarray] = []
        self._last_transcription = ""

        # Callbacks
        self._progress_callback: Optional[Callable[[str, bool], None]] = None

        # Determine compute device and type
        self._device, self._compute_type = self._detect_compute_config()

    def _detect_compute_config(self) -> Tuple[str, str]:
        """
        Detect the best compute configuration for the current system.

        Returns:
            Tuple of (device, compute_type)
        """
        if self.settings.device != "auto":
            device = self.settings.device
        else:
            device = self._detect_device()

        if self.settings.compute_type != "auto":
            compute_type = self.settings.compute_type
        else:
            compute_type = self._detect_compute_type(device)

        return device, compute_type

    def _detect_device(self) -> str:
        """Detect the best available compute device."""
        # Check for CUDA
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass

        # Check for Apple Silicon (MPS) - faster-whisper doesn't support MPS directly
        # but we can use CPU mode which is still fast on Apple Silicon
        if platform.system() == "Darwin" and platform.processor() == "arm":
            return "cpu"  # Will use accelerated CPU on Apple Silicon

        return "cpu"

    def _detect_compute_type(self, device: str) -> str:
        """Detect the best compute type for the given device."""
        if device == "cuda":
            try:
                import torch
                # Get GPU memory
                gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if gpu_mem >= 8:
                    return "float16"
                else:
                    return "int8"
            except Exception:
                return "int8"
        else:
            # CPU mode
            return "int8"  # int8 is faster on CPU

    def get_model_path(self, model_name: Optional[str] = None) -> Path:
        """Get the path where a model is/should be stored."""
        name = model_name or self.settings.model_name
        return get_cache_dir() / name

    def is_model_downloaded(self, model_name: Optional[str] = None) -> bool:
        """Check if a model is already downloaded."""
        # faster-whisper downloads models automatically, but we can check cache
        model_path = self.get_model_path(model_name)
        return model_path.exists()

    def load_model(
        self,
        model_name: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> None:
        """
        Load the Whisper model.

        Args:
            model_name: Model name to load (default from settings)
            progress_callback: Callback for download progress (0.0 to 1.0)
        """
        name = model_name or self.settings.model_name

        if self._is_loaded and self._model_name == name:
            return  # Already loaded

        # Unload existing model if different
        if self._is_loaded:
            self.unload_model()

        try:
            from faster_whisper import WhisperModel

            # Determine model size for English-only optimization
            if self.settings.language == "en" and name in ["tiny", "base", "small", "medium"]:
                # Use English-only model for better accuracy
                actual_model = f"{name}.en"
            else:
                actual_model = name

            cache_dir = str(get_cache_dir())

            self._model = WhisperModel(
                actual_model,
                device=self._device,
                compute_type=self._compute_type,
                download_root=cache_dir,
            )

            self._model_name = name
            self._is_loaded = True

        except ImportError:
            raise TranscriptionEngineError(
                "faster-whisper is not installed. Install with: pip install faster-whisper"
            )
        except Exception as e:
            raise TranscriptionEngineError(f"Failed to load model: {e}")

    def unload_model(self) -> None:
        """Unload the current model to free memory."""
        if self._model is not None:
            del self._model
            self._model = None
            self._model_name = None
            self._is_loaded = False

            # Force garbage collection
            import gc
            gc.collect()

            if self._device == "cuda":
                try:
                    import torch
                    torch.cuda.empty_cache()
                except ImportError:
                    pass

    def set_progress_callback(self, callback: Callable[[str, bool], None]) -> None:
        """
        Set callback for streaming transcription progress.

        Args:
            callback: Function called with (text, is_final) for each update
        """
        self._progress_callback = callback

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.

        Args:
            audio: Audio data as numpy array (float32, mono)
            sample_rate: Sample rate of the audio (default 16000)

        Returns:
            TranscriptionResult with the transcribed text
        """
        if not self._is_loaded:
            self.load_model()

        start_time = time.time()

        # Ensure audio is the right format
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Resample if needed (Whisper expects 16kHz)
        if sample_rate != 16000:
            audio = self._resample(audio, sample_rate, 16000)

        # Calculate audio duration
        audio_duration = len(audio) / 16000

        # Transcribe
        try:
            segments, info = self._model.transcribe(
                audio,
                language=self.settings.language if self.settings.language != "auto" else None,
                beam_size=self.settings.beam_size,
                vad_filter=self.settings.vad_enabled,
                vad_parameters={
                    "threshold": self.settings.vad_threshold,
                    "min_speech_duration_ms": 250,
                    "min_silence_duration_ms": 100,
                },
            )

            # Collect all segments
            text_parts = []
            total_confidence = 0
            segment_count = 0

            for segment in segments:
                text_parts.append(segment.text)
                # Approximate confidence from avg_logprob
                confidence = np.exp(segment.avg_logprob) if segment.avg_logprob else 0.5
                total_confidence += confidence
                segment_count += 1

                # Call progress callback for streaming
                if self._progress_callback:
                    current_text = "".join(text_parts)
                    self._progress_callback(current_text.strip(), False)

            full_text = "".join(text_parts).strip()
            avg_confidence = total_confidence / segment_count if segment_count > 0 else 0.0
            processing_time = time.time() - start_time

            # Final callback
            if self._progress_callback:
                self._progress_callback(full_text, True)

            return TranscriptionResult(
                text=full_text,
                language=info.language,
                confidence=avg_confidence,
                duration=audio_duration,
                processing_time=processing_time,
                is_partial=False,
            )

        except Exception as e:
            raise TranscriptionEngineError(f"Transcription failed: {e}")

    def transcribe_streaming(
        self,
        audio_chunk: np.ndarray,
        is_final: bool = False
    ) -> Optional[TranscriptionResult]:
        """
        Process an audio chunk for streaming transcription.

        Accumulates audio and transcribes periodically for low-latency results.

        Args:
            audio_chunk: Audio chunk to process
            is_final: Whether this is the final chunk

        Returns:
            TranscriptionResult if transcription was performed, None otherwise
        """
        self._streaming_buffer.append(audio_chunk)

        # Concatenate all chunks
        full_audio = np.concatenate(self._streaming_buffer)

        # Only transcribe if we have enough audio (at least 0.5 seconds)
        # or if this is the final chunk
        min_samples = int(0.5 * 16000)

        if len(full_audio) < min_samples and not is_final:
            return None

        # Transcribe
        result = self.transcribe(full_audio)

        if is_final:
            # Clear buffer on final
            self._streaming_buffer.clear()
            self._last_transcription = ""
        else:
            # Store last transcription for comparison
            self._last_transcription = result.text
            result.is_partial = True

        return result

    def reset_streaming(self) -> None:
        """Reset the streaming buffer."""
        self._streaming_buffer.clear()
        self._last_transcription = ""

    def _resample(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate."""
        if orig_sr == target_sr:
            return audio

        # Simple resampling using linear interpolation
        duration = len(audio) / orig_sr
        target_length = int(duration * target_sr)
        indices = np.linspace(0, len(audio) - 1, target_length)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    def get_available_models(self) -> dict:
        """Get information about available models."""
        return AVAILABLE_MODELS.copy()

    @property
    def is_loaded(self) -> bool:
        """Check if a model is loaded."""
        return self._is_loaded

    @property
    def current_model(self) -> Optional[str]:
        """Get the name of the currently loaded model."""
        return self._model_name

    @property
    def device(self) -> str:
        """Get the compute device being used."""
        return self._device

    @property
    def compute_type(self) -> str:
        """Get the compute type being used."""
        return self._compute_type

    def __enter__(self):
        """Context manager entry."""
        self.load_model()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.unload_model()
        return False
