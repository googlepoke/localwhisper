# LocalWhisper

Real-time local speech-to-text desktop application using OpenAI's Whisper model.

## Features

- **Privacy-First**: All processing happens locally - no audio data leaves your device
- **Real-Time Transcription**: Sub-500ms latency with optimized Whisper Turbo model
- **Universal Compatibility**: Works with any application that accepts text input
- **Cross-Platform**: Supports Windows, macOS, and Linux
- **Press-and-Hold Activation**: Simple hotkey interaction (default: Alt+S)
- **Beautiful UI**: Modern waveform visualization with customizable accent colors
- **Transcription History**: Searchable history with export capabilities

## Installation

### Prerequisites

- Python 3.10 or higher
- FFmpeg (for audio processing)

### Install from source

```bash
cd localwhisper
pip install -e .
```

### Install with GPU support (NVIDIA CUDA)

```bash
pip install -e ".[cuda]"
```

### Install development dependencies

```bash
pip install -e ".[dev]"
```

## Usage

### Running the Application

```bash
# Run as module
python -m localwhisper

# Or use the installed command
localwhisper
```

### Default Hotkey

- **Alt+S** (press and hold): Start recording
- Release Alt+S: Stop recording and transcribe

The transcribed text will be typed at your current cursor position.

### Configuration

Settings are stored in:
- **Windows**: `%APPDATA%\LocalWhisper\config.json`
- **macOS**: `~/Library/Application Support/LocalWhisper/config.json`
- **Linux**: `~/.config/localwhisper/config.json`

## Architecture

```
localwhisper/
├── core/
│   ├── audio_engine.py      # Microphone capture
│   ├── transcription_engine.py  # Whisper inference
│   ├── hotkey_manager.py    # Global hotkey handling
│   ├── text_injector.py     # Keyboard simulation
│   ├── history_manager.py   # SQLite history storage
│   ├── audio_feedback.py    # Sound cues
│   └── config.py            # Configuration management
├── ui/
│   ├── waveform_widget.py   # Waveform visualization
│   ├── settings_window.py   # Settings dialog
│   ├── history_window.py    # History viewer
│   └── tray_icon.py         # System tray integration
├── tests/                   # Unit tests
└── app.py                   # Main application
```

## Supported Models

| Model | Size | VRAM | Speed | Notes |
|-------|------|------|-------|-------|
| tiny.en | 75MB | 1GB | 32x | Fastest, English only |
| base.en | 145MB | 1GB | 16x | Good balance |
| small.en | 488MB | 2GB | 6x | Better accuracy |
| medium.en | 1.5GB | 5GB | 2x | High accuracy |
| turbo | 1.6GB | 6GB | 8x | **Recommended** |
| large-v3 | 3.1GB | 10GB | 1x | Highest accuracy |

## Development

### Running Tests

```bash
pytest localwhisper/tests/ -v
```

### Code Formatting

```bash
black localwhisper/
isort localwhisper/
```

## Requirements

- PyQt6 >= 6.5.0
- faster-whisper >= 1.0.0
- sounddevice >= 0.4.6
- pynput >= 1.7.6
- numpy >= 1.24.0

## License

MIT License
