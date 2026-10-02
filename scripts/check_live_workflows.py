"""Exercise real HTTP paths through Next.js with synthetic data; clean up own cases."""
import io
import json
from pathlib import Path
from datetime import datetime,timezone
import httpx
from PIL import Image,ImageDraw,ImageFont

def main():
    root=Path(__file__).resolve().parents[1]
    out=root/'tmp';out.mkdir(exist_ok=True)
    image=Image.new('RGB',(1100,440),'white')
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(str(root/'backend/fonts/NotoSans-Regular.ttf'),32)
    draw.multiline_text((35,30),'SYNTHETIC TEST RECEIPT\nAmount: INR 25000\nDate: 2026-09-29\nTransaction reference: TEST987654321\nRecipient: demo@example\nPayment method: UPI',font=font,fill='black',spacing=15)
    image.save(out/'test-receipt.png')
    with httpx.Client(base_url='http://127.0.0.1:3000',timeout=120) as client:
        def request(method,path,**kwargs):
            r=client.request(method,'/api'+path,**kwargs)
            assert r.is_success,f'{method} {path}: {r.status_code} {r.text[:500]}'
            return r
        request('POST','/session')
        c=request('POST','/cases',json={'language':'en','ai_consent':True}).json()
        base='/cases/'+c['id']
        try:
            c=request('POST',base+'/messages',json={'text':'Synthetic test: I paid INR 25000 in a Telegram scam through UPI yesterday.'}).json()
            assert c['facts']['category']=='cyber_fraud' and c['messages'][-1]['text']
            print('Text intake: saved and replied; provider='+c['messages'][-1]['provider'])
            print('Cloud status: '+str((c.get('service_notice') or {}).get('code','available')))
            c=request('POST',base+'/evidence',files={'file':('receipt.png',(out/'test-receipt.png').read_bytes(),'image/png')}).json()
            assert 'TEST987654321' in c['evidence'][-1]['extracted_text']
            assert c['facts']['transaction_reference']=='TEST987654321'
            print('Image upload and local OCR: passed')
            c=request('PUT',base+'/facts',json={'facts':c['facts'],'revision':c['revision']}).json()
            assert c['facts_confirmed']
            for name in ['complaint.pdf','offline.pdf','dossier.zip']:
                data=request('GET',base+'/documents/'+name).content
                assert data.startswith(b'PK' if name.endswith('zip') else b'%PDF')
                (out/name).write_bytes(data)
            print('Fact confirmation and all document downloads: passed')
            c=request('POST',base+'/simulate',json={'approved':True,'revision':c['revision'],'idempotency_key':'http-smoke-test-001'}).json()
            assert c['filings'][-1]['reference_number'].startswith('DEMO-')
            assert c['deadlines']
            c=request('POST',base+'/responses',json={'text':'We have received your report and are investigating. Please retain your receipt.','source':'entity','received_at':datetime.now(timezone.utc).isoformat()}).json()
            assert c['responses'][-1]['explanation']
            print('Filing, event clock and response handling: passed')
            if (out/'test-voice.flac').exists():
                result=request('POST',base+'/transcribe',files={'file':('test.flac',(out/'test-voice.flac').read_bytes(),'audio/flac')}).json()
                assert 'country' in result['text'].lower(),result['text']
                assert result['provider']=='local_whisper'
                print('Real audio transcription: passed (local Whisper, expected speech recognized)')
            else: print('Voice fixture missing; voice check skipped')
        finally:
            request('DELETE',base)

if __name__=='__main__': main()
