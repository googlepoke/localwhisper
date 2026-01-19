"""
Pytest configuration and fixtures for LocalWhisper tests.
"""

import pytest
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_audio():
    """Create sample audio data for testing."""
    import numpy as np

    # Generate 1 second of silence with some noise
    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)

    # White noise at low amplitude
    audio = np.random.randn(samples).astype(np.float32) * 0.01

    return audio


@pytest.fixture
def sample_speech_audio():
    """Create sample audio that simulates speech (sine wave)."""
    import numpy as np

    sample_rate = 16000
    duration = 2.0
    samples = int(sample_rate * duration)

    # Generate a tone that simulates speech energy
    t = np.linspace(0, duration, samples)
    # Mix of frequencies typical of speech
    audio = (
        0.3 * np.sin(2 * np.pi * 200 * t) +  # Low frequency
        0.2 * np.sin(2 * np.pi * 500 * t) +  # Mid frequency
        0.1 * np.sin(2 * np.pi * 1000 * t)   # High frequency
    ).astype(np.float32)

    return audio
