"""Server-side English transcription. No visitor-side model downloads."""
from io import BytesIO
from pathlib import Path
import threading
import av
import numpy as np
from .config import settings

MAX_AUDIO_BYTES = 15 * 1024 * 1024
MAX_SECONDS = 180
SAMPLE_RATE = 16000
_gate = threading.Lock()
_model = None


class SpeechUnavailable(Exception):
    pass


class InvalidAudio(Exception):
    pass


class AudioTooLong(InvalidAudio):
    pass


def model_path() -> Path:
    return Path(settings.speech_model_dir).expanduser()


def speech_ready() -> bool:
    return (model_path() / 'model.bin').is_file()


def decode_audio(content: bytes) -> np.ndarray:
    chunks = []
    samples = 0
    try:
        with av.open(BytesIO(content)) as container:
            if not container.streams.audio or container.streams.video:
                raise InvalidAudio('Please record audio only.')
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(format='s16', layout='mono', rate=SAMPLE_RATE)
            for frame in container.decode(stream):
                for converted in resampler.resample(frame):
                    array = converted.to_ndarray().flatten()
                    samples += len(array)
                    if samples > MAX_SECONDS * SAMPLE_RATE:
                        raise AudioTooLong('Recordings must be three minutes or shorter.')
                    chunks.append(array)
            for converted in resampler.resample(None):
                array = converted.to_ndarray().flatten()
                samples += len(array)
                if samples > MAX_SECONDS * SAMPLE_RATE:
                    raise AudioTooLong('Recordings must be three minutes or shorter.')
                chunks.append(array)
    except InvalidAudio:
        raise
    except (av.FFmpegError, ValueError, EOFError, OSError) as exc:
        raise InvalidAudio('The recording could not be decoded. Please record it again.') from exc
    if not samples:
        raise InvalidAudio('The recording contains no audio. Please record it again.')
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def transcribe(content: bytes) -> dict:
    global _model
    if not speech_ready():
        raise SpeechUnavailable('Voice transcription is not ready on the server. You can still type your answer.')
    if not _gate.acquire(blocking=False):
        raise SpeechUnavailable('Another recording is being transcribed. Please retry in a moment.')
    try:
        audio = decode_audio(content)
        if _model is None:
            from faster_whisper import WhisperModel
            try:
                _model = WhisperModel(str(model_path()), device='cpu', compute_type='int8', cpu_threads=4, num_workers=1, local_files_only=True)
            except Exception as exc:
                raise SpeechUnavailable('The server could not load its speech model. You can still type your answer.') from exc
        try:
            segments, _ = _model.transcribe(audio, language='en', beam_size=3, vad_filter=True, condition_on_previous_text=False)
            text = ' '.join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        except Exception as exc:
            raise SpeechUnavailable('The server could not transcribe the recording. Please retry or type your answer.') from exc
        if not text:
            raise InvalidAudio('No clear speech was found. Check your microphone and record again, or type your answer.')
        return {'text': text, 'duration_seconds': round(len(audio) / SAMPLE_RATE, 2)}
    finally:
        _gate.release()
