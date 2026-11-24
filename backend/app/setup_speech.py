"""Run once on the backend host: uv run --locked python -m app.setup_speech"""
from faster_whisper.utils import download_model
from .transcription import model_path

if __name__ == '__main__':
    directory = model_path()
    directory.mkdir(parents=True, exist_ok=True)
    download_model('base.en', output_dir=str(directory))
    print(f'Server speech model ready: {directory}')
