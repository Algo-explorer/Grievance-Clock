"""Download the multilingual Whisper base model once; audio never leaves this app."""
import os
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
os.environ['HF_HUB_DISABLE_XET']='1'
from faster_whisper.utils import download_model
from backend.local_media import model_dir

if __name__=='__main__':
    target=model_dir();target.mkdir(parents=True,exist_ok=True)
    download_model('base',output_dir=str(target))
    print('Local multilingual voice model installed.')
