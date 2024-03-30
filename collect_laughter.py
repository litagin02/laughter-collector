import argparse
import csv
import datetime
import shutil
import subprocess
import sys
import time

from pathlib import Path

import torch
from torch.utils.data import Dataset
from tqdm import tqdm
from transformers import pipeline

from pattern import is_laughing, is_nv, normalize_text
from utils import is_audio_file, logger


class ListDataset(Dataset):
    def __init__(self, original_list):
        self.original_list = original_list

    def __len__(self):
        return len(self.original_list)

    def __getitem__(self, i):
        return self.original_list[i]


# Add log file
logger.add(f'logs/{datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}.log')

parser = argparse.ArgumentParser()
parser.add_argument("--input_dir", "-i", type=str, required=True)
parser.add_argument("--output_dir", "-o", type=str, default="output")
parser.add_argument("--non_recursive", "-nr", action="store_true")
parser.add_argument("--overwrite", "-ow", action="store_true")
parser.add_argument("--verbose", "-v", action="store_true")
parser.add_argument("--keep", "-k", action="store_true")
parser.add_argument("--num_workers", "-w", type=int, default=2)
parser.add_argument("--model", "-m", type=str, default="medium")
parser.add_argument("--batch_size", "-b", type=int, default=32)
parser.add_argument("--not_do_sample", "-nds", action="store_true")
parser.add_argument("--num_beams", "-nb", type=int, default=1)
parser.add_argument("--threshold", "-t", type=float, default=40)

args = parser.parse_args()

logger.info(f"Args: {args}")


device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model_id = f"openai/whisper-{args.model}"
generate_kwargs = {
    "language": "ja",
    "do_sample": not args.not_do_sample,
    "num_beams": args.num_beams,
    "temperature": 0.1,
    "no_repeat_ngram_size": 10,
}
logger.info(f"Using model: {model_id}")
logger.info(f"generate_kwargs: {generate_kwargs}")
pipe = pipeline(
    model=model_id,
    max_new_tokens=128,
    chunk_length_s=30,
    batch_size=args.batch_size,
    torch_dtype=torch_dtype,
    device=device,
    generate_kwargs=generate_kwargs,
)


input_dir = Path(args.input_dir)
output_dir = Path(args.output_dir)
output_dir.mkdir(exist_ok=True, parents=True)

if args.non_recursive:
    subdirs = [input_dir]
else:
    subdirs = (x for x in input_dir.rglob("*") if x.is_dir())

temp_dir = output_dir / "temp"
if temp_dir.exists():
    # Remove previous temp files
    logger.warning(f"Removing previous temp files in {temp_dir}")
    shutil.rmtree(temp_dir)
temp_dir.mkdir(exist_ok=True, parents=True)


keep_dir = output_dir / "keep"
if args.keep:
    keep_dir.mkdir(exist_ok=True, parents=True)

for subdir in subdirs:
    logger.info(f"Processing {subdir}...")

    current_out_dir_laugh = output_dir / "laugh" / subdir.relative_to(input_dir)
    current_out_dir_nv = output_dir / "nv" / subdir.relative_to(input_dir)

    csv_path_laugh = current_out_dir_laugh / "laugh.csv"
    csv_path_nv = current_out_dir_nv / "nv.csv"

    trans_all_csv = output_dir / "trans" / subdir.relative_to(input_dir) / "trans.csv"

    if trans_all_csv.exists():
        logger.warning(f"{trans_all_csv} already exists.")
        if not args.overwrite:
            logger.warning("Use --overwrite (-ow) to overwrite. Skipping...")
            continue

    audio_files = [x for x in subdir.iterdir() if is_audio_file(x)]
    if len(audio_files) == 0:
        logger.warning(f"No audio files found in {subdir}.")
        continue

    python = sys.executable
    slice_process = subprocess.Popen(
        [
            python,
            "split.py",
            "-i",
            str(subdir),
            "-o",
            str(temp_dir),
            "-t",
            str(args.threshold),
            "-w",
            str(args.num_workers),
        ],
    )

    process_finished = False

    trans_results_all: list[tuple[Path, str, str]] = []

    while True:
        logger.info("Waiting for slicing...")
        if slice_process.poll() is not None and not process_finished:
            logger.info("Finished slicing.")
            process_finished = True
        elif process_finished:
            break
        flag_files = [file for file in temp_dir.iterdir() if file.suffix == ".flag"]
        sliced_files = [file.with_suffix(".wav") for file in flag_files]
        if len(sliced_files) == 0:
            # sleep 1 sec
            logger.info("No sliced files found.")
            time.sleep(1)
            continue

        logger.info(f"Found {len(sliced_files)} sliced files.")

        trans_results = []
        dataset = ListDataset([str(file) for file in sliced_files])
        for whisper_result in tqdm(
            pipe(dataset), total=len(sliced_files), desc="Transcribing"
        ):
            trans_results.append(whisper_result["text"])  # type: ignore
        logger.success(f"Finished transcribing.")

        # Normalize texts to avoid crashes
        logger.info("Normalizing texts...")
        normalized_results = []
        for text in tqdm(trans_results):
            normalized_results.append(normalize_text(text))

        def process_text(item: tuple[Path, str]) -> tuple[Path, str, str]:
            file, text = item
            if args.verbose:
                logger.debug(f"Processing {file}: {text}")
            if is_laughing(text):
                return (file, text, "laugh")
            elif is_nv(text):
                return (file, text, "nv")
            else:
                if args.keep:
                    shutil.move(file, keep_dir / file.name)
                else:
                    file.unlink()
                file.with_suffix(".flag").unlink()
                return (file, text, "no-nv")

        logger.info("Processing texts...")
        text_results: list[tuple[Path, str, str]] = []
        for item in tqdm(
            zip(sliced_files, normalized_results),
            total=len(sliced_files),
            desc="Processing",
        ):
            text_results.append(process_text(item))

        trans_results_all.extend(text_results)

        results_laugh = [x for x in text_results if x[2] == "laugh"]
        results_nv = [x for x in text_results if x[2] == "nv"]

        for file, text, _ in results_laugh:
            logger.success(f"laugh: {file}: {text}")
        for file, text, _ in results_nv:
            logger.info(f"nv: {file}: {text}")

        if len(results_laugh) > 0:
            logger.success(
                f"Moving {len(results_laugh)} laugh files to {current_out_dir_laugh}"
            )
            current_out_dir_laugh.mkdir(exist_ok=True, parents=True)
            for file, text, _ in results_laugh:
                out_file = current_out_dir_laugh / file.name
                if not args.keep:
                    file.replace(out_file)
                else:
                    shutil.copy(file, out_file)
                    file.replace(keep_dir / subdir.relative_to(input_dir) / file.name)
                file.with_suffix(".flag").unlink()

            # CSVファイルが存在しないかサイズが0の場合は、ヘッダーを書き込む
            if not csv_path_laugh.exists() or csv_path_laugh.stat().st_size == 0:
                with csv_path_laugh.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["file", "text"])

            # データの追加
            with csv_path_laugh.open("a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(
                    (str(file.name), text) for file, text, _ in results_laugh
                )
        else:
            logger.info(f"No laugh files found in this loop.")

        if len(results_nv) > 0:
            logger.success(f"Moving {len(results_nv)} nv files to {current_out_dir_nv}")
            current_out_dir_nv.mkdir(exist_ok=True, parents=True)
            for file, text, _ in results_nv:
                out_file = current_out_dir_nv / file.name
                if not args.keep:
                    file.replace(out_file)
                else:
                    shutil.copy(file, out_file)
                    file.replace(keep_dir / subdir.relative_to(input_dir) / file.name)
                file.with_suffix(".flag").unlink()

            # CSVファイルが存在しないかサイズが0の場合は、ヘッダーを書き込む
            if not csv_path_nv.exists() or csv_path_nv.stat().st_size == 0:
                with csv_path_nv.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["file", "text"])

            # データの追加
            with csv_path_nv.open("a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows((str(file.name), text) for file, text, _ in results_nv)
        else:
            logger.info(f"No nv files found in this loop.")

    # Sort trans_results_all by file name
    trans_results_all.sort(key=lambda x: x[0].name)

    trans_all_csv.parent.mkdir(exist_ok=True, parents=True)

    # Write all transcriptions to a csv file
    with trans_all_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "text", "label"])
        writer.writerows(
            (str(file.name), text, label) for file, text, label in trans_results_all
        )

    logger.success(f"Finished processing {subdir}.")
