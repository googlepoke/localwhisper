# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenAI Whisper is a general-purpose speech recognition model built on a Transformer sequence-to-sequence architecture. It performs multilingual speech recognition, speech translation, language identification, and voice activity detection. The model processes audio through a sliding 30-second window approach.

## Development Commands

### Installation
```bash
# Install from source
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"

# External dependency (required)
# ffmpeg must be installed on your system
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_transcribe.py

# Run with verbose output
pytest -v

# Run tests that require CUDA (if available)
pytest -m requires_cuda
```

### Code Quality
```bash
# Format code with black
black .

# Sort imports with isort
isort .

# Run flake8 linting
flake8

# Run pre-commit hooks (includes all checks)
pre-commit run --all-files
```

**Code Style**: This project uses black for formatting (line length: 88), isort for import sorting (black profile), and flake8 for linting. The pre-commit config enforces these standards along with trailing whitespace, end-of-file fixes, and file size limits (4MB max).

## Architecture

### Core Components

**Model (`whisper/model.py`)**:
- `Whisper` class contains `AudioEncoder` (processes mel spectrograms) and `TextDecoder` (generates text tokens)
- `ModelDimensions` dataclass defines model architecture parameters
- Custom layers (`Linear`, `Conv1d`, `LayerNorm`) handle mixed precision by casting weights to input dtype
- `MultiHeadAttention` uses PyTorch's scaled_dot_product_attention when available (toggle via `use_sdpa` class variable or `disable_sdpa()` context manager)
- KV caching system via `install_kv_cache_hooks()` for efficient inference

**Audio Processing (`whisper/audio.py`)**:
- Converts audio to log-Mel spectrograms (80 bands by default)
- Constants: `SAMPLE_RATE=16000`, `N_FFT=400`, `HOP_LENGTH=160`, `CHUNK_LENGTH=30` (seconds)
- `load_audio()`: uses ffmpeg to decode and resample audio
- `pad_or_trim()`: normalizes audio to exactly 30 seconds (480,000 samples)

**Decoding (`whisper/decoding.py`)**:
- `DecodingOptions`: configuration for transcription/translation tasks
- `decode()`: low-level function for single 30-second window
- `detect_language()`: identifies spoken language from audio features
- Supports beam search and temperature-based sampling

**Transcription (`whisper/transcribe.py`)**:
- `transcribe()`: high-level API that processes entire audio files with sliding windows
- Handles multi-temperature fallback on failures (compression ratio or logprob thresholds)
- `cli()`: command-line interface entry point
- Optional word-level timestamps via `add_word_timestamps()` (from `timing.py`)

**Tokenization (`whisper/tokenizer.py`)**:
- Uses tiktoken for fast BPE tokenization
- `get_tokenizer()`: factory function returns appropriate tokenizer for model type
- Special tokens handle task specification (transcribe/translate), language codes, timestamps
- `LANGUAGES` dict maps language codes to names

**Text Normalization (`whisper/normalizers/`)**:
- `BasicTextNormalizer`: removes diacritics, standardizes whitespace and punctuation
- `EnglishTextNormalizer`: comprehensive English-specific normalization (numbers, contractions, spelling variations)

### Model Loading

Models are downloaded from Azure CDN and cached in `~/.cache/whisper` (or `$XDG_CACHE_HOME/whisper`). Available models defined in `_MODELS` dict in `__init__.py`:
- Size variants: tiny, base, small, medium, large, turbo
- English-only versions: tiny.en, base.en, small.en, medium.en
- Version variants: large-v1, large-v2, large-v3

`load_model()` verifies SHA256 checksums and loads with `weights_only=True` for PyTorch >=1.13.

### Entry Points

**Python API**:
```python
import whisper
model = whisper.load_model("turbo")
result = model.transcribe("audio.mp3")  # High-level
# Or low-level:
audio = whisper.load_audio("audio.mp3")
mel = whisper.log_mel_spectrogram(audio)
_, probs = model.detect_language(mel)
result = whisper.decode(model, mel, options)
```

**CLI**: Defined by `scripts.whisper = "whisper.transcribe:cli"` in pyproject.toml

## Important Notes

- **Security**: Recent commits added `weights_only=True` to `torch.load()` to prevent arbitrary code execution
- **Device Handling**: DTW cost tensors and other operations must match input device (CUDA/CPU)
- **Turbo Model Limitation**: Not trained for translation tasks; use multilingual models (tiny-large) for non-English to English translation
- **Test Fixtures**: `conftest.py` sets random seeds (42) for reproducibility
- **Version**: Stored in `whisper/version.py` and used by setuptools dynamic versioning
