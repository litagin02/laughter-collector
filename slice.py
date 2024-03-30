import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import soundfile as sf
from pydub import AudioSegment
from pydub.silence import split_on_silence

from utils import is_audio_file, logger


def process_file(file: Path, output_dir: Path, threshold: int):
    chunks = split(file, threshold)
    for i, chunk in enumerate(chunks):
        chunk = chunk.set_channels(1)
        chunk = chunk.set_frame_rate(44100)
        out_file = output_dir / f"{file.stem}_{i}.wav"
        chunk.export(out_file, format="wav", codec="pcm_s16le")
        flag_file = out_file.with_suffix(".flag")
        flag_file.touch()


def split(input_file: Path, threshold: int) -> list[AudioSegment]:
    try:
        audio, sr = sf.read(input_file)
        tmp_file = input_file.name
        sf.write(tmp_file, audio, sr)
        audio = AudioSegment.from_file(tmp_file)
        Path(tmp_file).unlink()
    except Exception as e:
        print(e)
        return []

    min_silence_len = 250
    silence_thresh = -threshold
    keep_silence = 200

    min_chunk_len = 500
    max_chunk_len = 30_000

    if (len(audio) < min_chunk_len) or (len(audio) > max_chunk_len):
        return []

    chunks = split_on_silence(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        keep_silence=keep_silence,
    )

    return [chunk for chunk in chunks if min_chunk_len < len(chunk) < max_chunk_len]


logger.add(f"logs/split.log")

if __name__ == "__main__":
    logger.info("Starting slicing")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_dir",
        "-i",
        type=str,
        default="inputs",
        help="Directory of input wav files",
    )
    parser.add_argument(
        "--output_dir",
        "-o",
        type=str,
    )
    parser.add_argument(
        "--num_workers",
        "-w",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=int,
        default=40,
    )
    args = parser.parse_args()
    logger.info(f"Slicing args: {args}")
    threshold: int = args.threshold

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    output_dir.mkdir(exist_ok=True, parents=True)

    audio_files = [x for x in input_dir.glob("*") if is_audio_file(x)]

    logger.info(f"Found {len(audio_files)} audio files in {input_dir}")

    with ProcessPoolExecutor(max_workers=args.num_workers) as executor:
        futures = [
            executor.submit(process_file, file, output_dir, threshold)
            for file in audio_files
        ]
        for future in futures:
            future.result()

    logger.success(f"Slice done for {input_dir}")
