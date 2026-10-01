"""Fetch OFL-licensed Noto fonts from the official Noto repository."""
from pathlib import Path
import urllib.request
base='https://raw.githubusercontent.com/notofonts/noto-fonts/main/'
out=Path('backend/fonts');out.mkdir(exist_ok=True)
for family in ['NotoSans','NotoSansDevanagari','NotoSansBengali','NotoSansTamil','NotoSansTelugu']:
    name=family+'-Regular.ttf'
    urllib.request.urlretrieve(base+'hinted/ttf/'+family+'/'+name,out/name)
    print('Saved '+name)
urllib.request.urlretrieve(base+'LICENSE',out/'LICENSE')
