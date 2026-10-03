"""Local, no-key media processing. Models are installed explicitly, not during a request."""
import io
import os
import wave
from pathlib import Path
from threading import Lock
import importlib.util

ROOT=Path(__file__).resolve().parents[1]
_speech=None
_ocr=None
_speech_lock=Lock()
_ocr_lock=Lock()
_tts=None
_tts_lock=Lock()

def speech_model():
    return os.getenv('LOCAL_WHISPER_MODEL') or 'small'

def model_dir():
    base=Path(os.getenv('MODEL_DIR') or str(ROOT/'data'/'models'))
    return Path(os.getenv('LOCAL_WHISPER_PATH') or str(base/('whisper-'+speech_model())))

def hindi_voice_path():
    base=Path(os.getenv('MODEL_DIR') or str(ROOT/'data'/'models'))
    return Path(os.getenv('LOCAL_HINDI_VOICE_PATH') or str(base/'piper'/'hi_IN-rohan-medium.onnx'))

def status():
    return {'local_voice':bool(importlib.util.find_spec('faster_whisper')) and (model_dir()/'model.bin').exists(),
            'speech_model':speech_model(),
            'local_hindi_tts':bool(importlib.util.find_spec('piper')) and hindi_voice_path().exists() and Path(str(hindi_voice_path())+'.json').exists(),
            'local_ocr':bool(importlib.util.find_spec('rapidocr_onnxruntime'))}

def transcribe(raw,language=None):
    global _speech
    if not status()['local_voice']:
        raise RuntimeError('Local voice model is not installed. Run python -m scripts.setup_local_voice.')
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    audio=decode_audio(io.BytesIO(raw),sampling_rate=16000)
    if len(audio)>16000*90:
        raise ValueError('Please keep recordings under 90 seconds.')
    if len(audio)<1600 or float(abs(audio).max())<0.003:
        raise ValueError('No audible speech was found. Please record again, closer to the microphone.')
    with _speech_lock:
        if _speech is None:
            _speech=WhisperModel(str(model_dir()),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
        segments,_=_speech.transcribe(audio,language=language,task='transcribe',beam_size=5,
            vad_filter=True,vad_parameters={'min_silence_duration_ms':500,'speech_pad_ms':400},
            condition_on_previous_text=False,language_detection_segments=3)
        # Whisper already combines confidence with no-speech probability. A second
        # probability-only filter drops valid quiet speech and accented words.
        text=' '.join(s.text.strip() for s in segments).strip()
    if not text: raise ValueError('No clear speech was detected. Please record again or type your message.')
    return text

def synthesize_hindi(text):
    global _tts
    if not status()['local_hindi_tts']:
        raise RuntimeError('The Hindi voice is not installed. Run python -m scripts.setup_local_tts.')
    from piper import PiperVoice, SynthesisConfig
    with _tts_lock:
        if _tts is None:
            _tts=PiperVoice.load(str(hindi_voice_path()))
        output=io.BytesIO()
        with wave.open(output,'wb') as wav:
            _tts.synthesize_wav(text,wav,syn_config=SynthesisConfig(length_scale=1.08))
        return output.getvalue()

def ocr_image(raw):
    global _ocr
    from rapidocr_onnxruntime import RapidOCR
    with _ocr_lock:
        if _ocr is None:
            _ocr=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
        result,_=_ocr(raw)
    return '\n'.join(line[1] for line in (result or []) if line[2]>=0.55)[:16000]

def ocr_pdf(raw):
    import pypdfium2 as pdfium
    chunks=[]
    with pdfium.PdfDocument(raw) as doc:
        for i in range(min(len(doc),5)):
            page=doc[i]
            # Bound image dimensions even for PDFs with abnormal page sizes.
            scale=min(1.5,1800/max(page.get_size()))
            bitmap=page.render(scale=scale)
            image=bitmap.to_pil()
            data=io.BytesIO();image.save(data,format='PNG')
            chunks.append(ocr_image(data.getvalue()))
            image.close();bitmap.close();page.close()
    return '\n'.join(chunks)[:16000]
