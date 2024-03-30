import sys
from pathlib import Path

from loguru import logger


logger.remove()

log_format = (
    "<g>{time:MM-DD HH:mm:ss}</g> |<lvl>{level:^8}</lvl>| {file}:{line} | {message}"
)


logger.add(sys.stdout, format=log_format, backtrace=True, diagnose=True)


def is_audio_file(file: Path) -> bool:
    return file.suffix.lower() in (".wav", ".mp3", ".flac", ".ogg", ".opus")
