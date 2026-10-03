"""Container build-time model downloads; no request-time external downloads."""
import os
import shutil
os.environ['HF_HUB_DISABLE_XET']='1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
from faster_whisper.utils import download_model
from huggingface_hub import hf_hub_download
from .local_media import model_dir,speech_model,hindi_voice_path

if __name__=='__main__':
    target=model_dir();target.mkdir(parents=True,exist_ok=True)
    download_model(speech_model(),output_dir=str(target))
    voice=hindi_voice_path();voice.parent.mkdir(parents=True,exist_ok=True)
    for name,path in [('hi_IN-rohan-medium.onnx',voice),('hi_IN-rohan-medium.onnx.json',voice.with_suffix('.onnx.json')),('MODEL_CARD',voice.parent/'ROHAN_MODEL_CARD')]:
        source=hf_hub_download('rhasspy/piper-voices','hi/hi_IN/rohan/medium/'+name,
            revision='c10ece1aade47bb51c153c893d14e5bf8e5b7117')
        shutil.copyfile(source,path)
    print('Local transcription and Hindi speech models installed.')
