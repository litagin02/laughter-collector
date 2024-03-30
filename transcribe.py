import argparse
import datetime
from pathlib import Path

from faster_whisper import WhisperModel

from utils import is_audio_file, logger

model = WhisperModel("large-v2", device="cuda")

logger.add(
    f'logs/transcribe_{datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}.log'
)


def transcribe_local(audio_path: Path) -> str:
    segments, _ = model.transcribe(
        str(audio_path),
        language="ja",
    )
    texts = [segment.text for segment in segments]
    return "".join(texts)


parser = argparse.ArgumentParser(description="Transcribe audio files")
parser.add_argument(
    "-i", "--input_dir", type=Path, required=True, help="Input directory"
)
parser.add_argument(
    "-o",
    "--output_file",
    default="transcriptions.csv",
)

args = parser.parse_args()

input_dir = Path(args.input_dir)
csv_path = Path(args.output_file)

for d in input_dir.rglob("*"):
    if not d.is_dir():
        continue
    audio_files = [f for f in d.glob("*") if is_audio_file(f)]
    if not audio_files:
        logger.info(f"No audio files found in {d}")
        continue
    logger.info(f"Found {len(audio_files)} files in {d}")
    for i, audio_path in enumerate(audio_files):
        logger.info(f"{i + 1}/{len(audio_files)}: Processing {audio_path}")
        text = transcribe_local(audio_path)
        logger.info(f"Transcribed: {text}")
        # Write to csv
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            f.write(f"{audio_path.relative_to(input_dir)},{text}\n")
