"""Real local-engine smoke checks; no API calls or personal case data."""
import io
import json
import time
import wave
from pathlib import Path
from backend import local_media

if __name__=='__main__':
    start=time.monotonic()
    sample='नमस्ते। कृपया बताइए कि आपके साथ क्या हुआ। कितने पैसे का मामला है?'
    audio=local_media.synthesize_hindi(sample)
    Path('tmp').mkdir(exist_ok=True)
    Path('tmp/hindi-voice-check.wav').write_bytes(audio)
    with wave.open(io.BytesIO(audio)) as wav:
        assert wav.getnframes()>wav.getframerate()
    hindi=local_media.transcribe(audio,'hi')
    assert 'पैसे' in hindi or 'मामला' in hindi, hindi
    fixture=Path('tmp/test-voice.flac')
    if not fixture.exists():
        raise SystemExit('Place the official OpenAI Whisper tests/jfk.flac fixture at tmp/test-voice.flac first.')
    english=local_media.transcribe(fixture.read_bytes(),None)
    assert 'fellow americans' in english.lower(),english
    silence=io.BytesIO()
    with wave.open(silence,'wb') as wav:
        wav.setparams((1,2,16000,0,'NONE','not compressed'));wav.writeframes(b'\0'*32000)
    try: local_media.transcribe(silence.getvalue(),None)
    except ValueError: pass
    else: raise AssertionError('Silence should not produce words')
    print(json.dumps({'english':english,'hindi_roundtrip':hindi,'seconds':round(time.monotonic()-start,1)},ensure_ascii=True))
