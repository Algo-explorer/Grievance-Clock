"""Install the local Hindi voice and retain its attribution/model card.

Rohan uses the Indic TTS dataset; see docs/voice.md for attribution and terms.
"""
import os
import shutil
from dotenv import load_dotenv
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
os.environ['HF_HUB_DISABLE_XET']='1'
from huggingface_hub import hf_hub_download
from backend.local_media import ROOT, hindi_voice_path
load_dotenv(ROOT/'backend'/'.env.local')
load_dotenv(ROOT/'.env.local')

if __name__=='__main__':
    target=hindi_voice_path()
    target.parent.mkdir(parents=True,exist_ok=True)
    for name, destination in [('hi_IN-rohan-medium.onnx',target),
                              ('hi_IN-rohan-medium.onnx.json',target.with_suffix('.onnx.json')),
                              ('MODEL_CARD',target.parent/'ROHAN_MODEL_CARD')]:
        source=hf_hub_download('rhasspy/piper-voices','hi/hi_IN/rohan/medium/'+name,
            revision='c10ece1aade47bb51c153c893d14e5bf8e5b7117')
        shutil.copyfile(source,destination)
    print('Local Hindi voice installed (Rohan; Indic TTS dataset).')
