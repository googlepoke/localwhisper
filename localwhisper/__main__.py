"""
LocalWhisper - Real-Time Speech-to-Text Desktop Application

Entry point for running as a module: python -m localwhisper
"""

import sys
from localwhisper.app import main

if __name__ == "__main__":
    sys.exit(main())
