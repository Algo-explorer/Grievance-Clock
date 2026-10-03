"""Download a multilingual Whisper model once; audio stays local."""
import os
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
os.environ['HF_HUB_DISABLE_XET']='1'
from faster_whisper.utils import download_model
from dotenv import load_dotenv
from backend.local_media import model_dir, speech_model, ROOT
load_dotenv(ROOT/'backend'/'.env.local')
load_dotenv(ROOT/'.env.local')

if __name__=='__main__':
    target=model_dir();target.mkdir(parents=True,exist_ok=True)
    download_model(speech_model(),output_dir=str(target))
    print('Local multilingual voice model installed.')
