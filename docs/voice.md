# Voice setup and verification

Install `backend/requirements.txt`, then run:

```powershell
.\.venv\Scripts\python.exe -m scripts.setup_local_voice
.\.venv\Scripts\python.exe -m scripts.setup_local_tts
```

Restart the backend afterwards. `/api/health` reports `local_voice`,
`speech_model`, and `local_hindi_tts`. Downloads are explicit, never triggered by
a user recording. Models and generated audio are not committed to Git.

Recognition uses multilingual faster-whisper **small**, CPU int8, beam size 5,
and voice activity detection. `LOCAL_WHISPER_MODEL` can select a larger model;
run setup again after changing it. `LOCAL_WHISPER_PATH` overrides the directory.
Automatic spoken-language detection is independent of the chat language.
Choose Hindi for short Hindi/Hinglish replies, or English for short English
replies: a single word is often insufficient for reliable automatic detection.
Speech is transcribed, not translated. Review names, dates and amounts before
sending. Microphone noise cancellation and echo cancellation are requested
where supported. Read-aloud stops before recording. Recording is limited to
60 seconds in the UI and 90 seconds on the server; audio is not persisted.

Hindi text in Devanagari uses a local Piper voice and returns private WAV audio.
Other scripts require a matching installed browser voice; we never silently
substitute an English voice for an unsupported script. Roman Hindi is not
automatically transliterated by this speech patch. Playback can be stopped and
is cancelled on case/language changes. Cloud transcription still requires consent.

## Attribution and licensing

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper), MIT, using the
  [Whisper small model](https://huggingface.co/Systran/faster-whisper-small).
- [Piper](https://github.com/OHF-Voice/piper1-gpl), GPL-3.0.
- Hindi Rohan medium, distributed through
  [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/blob/main/hi/hi_IN/rohan/medium/MODEL_CARD).
  It uses IIT Madras Indic TTS Hindi Mono Male data and was fine-tuned from the
  English Lessac medium voice. The setup retains the model card. The card links
  the [Indic TTS dataset license](https://www.iitm.ac.in/donlab/indictts/downloads/license.pdf);
  review those original terms before distribution or commercial deployment.
  `LOCAL_HINDI_VOICE_PATH` supports an alternative Piper model with its adjacent
  `.onnx.json` configuration. Model weights are downloaded separately.

## Checks

`python -m pytest backend/tests -q` covers request validation, owner isolation,
language forwarding, no-consent local synthesis, and transcription error handling.
`python -m scripts.check_local_speech` exercises real installed engines using
the existing JFK English fixture, Hindi synthesized audio and silence. The Hindi
round trip is a smoke test, not an independent accuracy benchmark. Accents,
background noise, mixed languages and device microphones still need user testing.
