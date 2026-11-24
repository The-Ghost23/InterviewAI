"""Prepare the server speech model during the native Render build."""
import os
from pathlib import Path
from faster_whisper.utils import download_model

REQUIRED_FILES = ('model.bin', 'config.json', 'tokenizer.json')


def prepare_model(directory: Path) -> None:
    if all((directory / name).is_file() for name in REQUIRED_FILES):
        print('Whisper base.en is already prepared.')
        return
    directory.mkdir(parents=True, exist_ok=True)
    download_model('base.en', output_dir=str(directory))
    if not all((directory / name).is_file() for name in REQUIRED_FILES):
        raise RuntimeError('Speech model preparation is incomplete. Retry the build.')
    print('Whisper base.en prepared for server transcription.')


if __name__ == '__main__':
    default = Path(__file__).resolve().parents[1] / '.models' / 'whisper-base.en'
    prepare_model(Path(os.environ.get('SPEECH_MODEL_DIR', str(default))).expanduser())
