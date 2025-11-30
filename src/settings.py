import os
from enum import StrEnum
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DEBUG = os.getenv('DEBUG', 'False') == 'True'


class Models(StrEnum):
    CLAUDE_45 = 'eu.anthropic.claude-sonnet-4-5-20250929-v1:0'
    CLAUDE_45_OPUS = 'global.anthropic.claude-opus-4-5-20251101-v1:0'


BYTES_THRESHOLD = 4_300_000
MAX_CONTEXT_CHARS = 150_000
