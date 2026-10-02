import hashlib
import io
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from backend import main
from backend.storage import Store
from backend.engine import reminders, add_clock, next_escalation

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('AI_MODE','demo')
    monkeypatch.setattr(main,'store',Store(tmp_path))
    main.rate_buckets.clear()
    main.provider.reset()
    with TestClient(main.app) as c:
        assert c.post('/api/session').status_code==200
        yield c

def demo(c,kind='broker'):
    r=c.post('/api/demo/'+kind)
    assert r.status_code==200,r.text
    case=r.json()
    r=c.put(f"/api/cases/{case['id']}/facts",json={'facts':case['facts'],'revision':case['revision']})
    assert r.status_code==200,r.text
    return r.json()

def submit(c,case,key='test-idempotency-1'):
    r=c.post(f"/api/cases/{case['id']}/simulate",json={'approved':True,'revision':case['revision'],'idempotency_key':key})
    assert r.status_code==200,r.text
    return r.json()

def test_auth_and_owner_isolation(client):
    case=demo(client)
    with TestClient(main.app) as other:
        assert other.get('/api/cases').status_code==401
        other.post('/api/session')
        assert other.get('/api/cases/'+case['id']).status_code==404
        assert other.delete('/api/cases/'+case['id']).status_code==404
        assert other.get('/api/cases/'+case['id']+'/documents/complaint.pdf').status_code==404

def test_simulation_approval_idempotency_and_entity_clock(client):
    case=demo(client)
    path=f"/api/cases/{case['id']}/simulate"
    assert client.post(path,json={'approved':False,'revision':case['revision'],'idempotency_key':'abc123456'}).status_code==422
    filed=submit(client,case)
    assert filed['filings'][0]['reference_number'].startswith('DEMO-')
    assert filed['deadlines'][0]['regulatory'] is False
    assert filed['deadlines'][0]['simulated'] is True
    assert len(submit(client,case)['filings'])==1
    assert client.post(path,json={'approved':True,'revision':filed['revision'],'idempotency_key':'another12345'}).status_code==409

def test_cyber_urgency_independent_of_missing_fields(client):
    case=client.post('/api/cases',json={}).json()
    r=client.post(f"/api/cases/{case['id']}/messages",json={'text':'I paid Rs 25000 to a Telegram scam via UPI.'})
    assert r.status_code==200,r.text
    c=r.json()
    assert c['route']['urgent'] is True
    assert 'transaction_reference' in c['missing_fields']
    assert '1930' in c['messages'][-1]['text']
    assert not c['deadlines']

def test_evidence_integrity_and_encryption(client):
    case=demo(client,'scam')
    original=b'UTR TEST987654321 payment receipt INR 25000'
    r=client.post(f"/api/cases/{case['id']}/evidence",files={'file':('receipt.txt',original,'text/plain')})
    assert r.status_code==200,r.text
    case=r.json(); ev=case['evidence'][0]
    assert ev['sha256']==hashlib.sha256(original).hexdigest()
    assert case['facts_confirmed'] is False
    assert main.store.read_evidence(ev['id'])==original
    assert original not in (main.store.root/'evidence'/ev['id']).read_bytes()
    assert client.get(f"/api/cases/{case['id']}/evidence/{ev['id']}").content==original
    client.delete('/api/cases/'+case['id'])
    assert not (main.store.root/'evidence'/ev['id']).exists()

def test_invalid_file_and_secrets_rejected(client):
    case=demo(client)
    base=f"/api/cases/{case['id']}"
    assert client.post(base+'/evidence',files={'file':('fake.png',b'not an image','image/png')}).status_code==422
    assert client.post(base+'/messages',json={'text':'My OTP is 123456'}).status_code==422
    assert client.post(base+'/evidence',files={'file':('secrets.txt',b'password: 123456','text/plain')}).status_code==422

def test_scope_guard(client):
    case=demo(client)
    r=client.post(f"/api/cases/{case['id']}/messages",json={'text':'Should I buy Reliance stock?'}).json()
    assert 'cannot give investment' in r['messages'][-1]['text']
    assert r['facts']==case['facts']

def test_review_and_escalation_workflow(client):
    case=submit(client,demo(client))
    base=f"/api/cases/{case['id']}"
    ts=datetime.now(timezone.utc).isoformat()
    r=client.post(base+'/responses',json={'text':'Your withdrawal is delayed. We will investigate the issue.','source':'entity','received_at':ts})
    assert r.status_code==200,r.text
    assert client.post(base+'/decision',json={'satisfied':False}).json()['status']=='escalation_ready'
    case=client.post(base+'/escalate').json()
    assert case['pending_portal']=='SCORES'
    case=submit(client,case,'scores-submission-key')
    assert case['deadlines'][-1]['type']=='scores_atr'
    assert case['deadlines'][-1]['regulatory']
    ts=datetime.now(timezone.utc).isoformat()
    r=client.post(base+'/responses',json={'text':'The entity denies the complaint based on its internal records.','source':'SCORES_ENTITY_ATR','received_at':ts})
    assert r.status_code==200,r.text
    case=r.json()
    assert case['deadlines'][-1]['type']=='review_1'
    assert case['escalation']['available']
    case=client.post(base+'/decision',json={'satisfied':True}).json()
    assert case['status']=='resolved'
    assert not any(d['status']=='open' for d in case['deadlines'])
    assert client.post(base+'/escalate').status_code==409

def test_calendar_days_ist_and_idempotent_notifications(client):
    case=demo(client)
    add_clock(case,'SCORES_RECEIVED','2026-09-30T20:00:00+00:00',False,'evt1')
    assert case['deadlines'][-1]['due_date']=='2026-10-22'
    add_clock(case,'SCORES_RECEIVED','2026-09-30T20:00:00+00:00',False,'evt1')
    assert len(case['deadlines'])==1
    check=datetime.fromisoformat('2026-10-22T12:00:00+05:30')
    assert reminders(case,check)
    assert not reminders(case,check)
    assert len(case['notifications'])==1

def test_stale_confirmation_and_future_ack(client):
    case=demo(client)
    base=f"/api/cases/{case['id']}"
    assert client.put(base+'/facts',json={'facts':case['facts'],'revision':0}).status_code==409
    r=client.post(base+'/acknowledgements',json={'portal':'entity','reference_number':'ABC123','occurred_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'confirmed':True})
    assert r.status_code==422

def test_pdf_zip_and_offline_route(client):
    case=demo(client,'offline')
    assert case['route']['mode']=='physical_action'
    base=f"/api/cases/{case['id']}"
    pdf=client.get(base+'/documents/offline.pdf')
    assert pdf.status_code==200,pdf.text
    reader=PdfReader(io.BytesIO(pdf.content))
    text=''.join(p.extract_text() for p in reader.pages)
    assert 'branch visit checklist' in text
    assert 'not an official ISR' in text
    assert client.get(base+'/documents/dossier.zip').content.startswith(b'PK')

def test_cross_origin_mutation_blocked(client):
    assert client.post('/api/cases',json={},headers={'origin':'https://malicious.example'}).status_code==403

def test_unknown_cannot_submit(client):
    case=client.post('/api/cases',json={}).json()
    assert client.post(f"/api/cases/{case['id']}/simulate",json={'approved':True,'revision':0,'idempotency_key':'unknown1234'}).status_code==422

def test_cloud_quota_does_not_lose_text(client,monkeypatch):
    import httpx
    from openai import RateLimitError
    monkeypatch.setenv('AI_MODE','live')
    calls=[]
    def fail(*args,**kwargs):
        calls.append(True)
        raise RateLimitError('quota exhausted',response=httpx.Response(429,request=httpx.Request('POST','https://api.openai.com/v1/responses')),body={'code':'insufficient_quota'})
    monkeypatch.setattr(main.ai,'extract',fail)
    c=client.post('/api/cases',json={'ai_consent':True}).json()
    base=f"/api/cases/{c['id']}"
    c=client.post(base+'/messages',json={'text':'My broker has not processed my withdrawal.'}).json()
    assert c['messages'][0]['text']=='My broker has not processed my withdrawal.'
    assert c['service_notice']['code']=='quota'
    assert c['messages'][-1]['provider']=='local_rules'
    assert 'name of the broker' in c['messages'][-1]['text']
    c=client.post(base+'/messages',json={'text':'Example Securities'}).json()
    assert c['facts']['entity_name']=='Example Securities'
    assert len(calls)==1  # cooldown prevents repeated failures for every reply
    c=client.post(base+'/messages',json={'text':'yesterday'}).json()
    assert c['facts']['incident_date']
    assert len(c['messages'])==6
    saved=client.get(base).json()
    assert saved['facts']==c['facts']

def test_local_intake_keeps_payment_context_and_handles_negation(client):
    c=client.post('/api/cases',json={}).json();base=f"/api/cases/{c['id']}"
    c=client.post(base+'/messages',json={'text':'A Telegram scammer contacted me. I have not sent money.'}).json()
    assert c['route']['urgent'] is False
    c=client.post(base+'/messages',json={'text':'I paid Rs 25000 yesterday.'}).json()
    assert c['route']['urgent'] is True
    assert c['facts']['amount']==25000
    c=client.post(base+'/messages',json={'text':'TEST123456789'}).json()
    assert c['facts']['transaction_reference']=='TEST123456789'
    assert c['route']['urgent'] is True

def test_local_voice_without_ai_consent(client,monkeypatch):
    c=client.post('/api/cases',json={'ai_consent':False}).json()
    monkeypatch.setattr(main.local_media,'status',lambda:{'local_voice':True,'local_ocr':True})
    monkeypatch.setattr(main.local_media,'transcribe',lambda raw,language:'My withdrawal is delayed.')
    r=client.post(f"/api/cases/{c['id']}/transcribe",files={'file':('voice.mp4',b'test mocked audio','audio/mp4')})
    assert r.status_code==200,r.text
    assert r.json()['provider']=='local_whisper'
    assert not client.get(f"/api/cases/{c['id']}").json()['messages']  # transcript must be reviewed

def test_local_ocr_survives_cloud_failure(client,monkeypatch):
    from PIL import Image
    image=io.BytesIO();Image.new('RGB',(100,100),'white').save(image,format='PNG')
    c=client.post('/api/cases',json={}).json()
    monkeypatch.setattr(main.local_media,'status',lambda:{'local_voice':True,'local_ocr':True})
    monkeypatch.setattr(main.local_media,'ocr_image',lambda raw:'Amount: INR 5000\nTransaction reference: TEST111222333\nDate: 2026-09-29')
    r=client.post(f"/api/cases/{c['id']}/evidence",files={'file':('receipt.png',image.getvalue(),'image/png')})
    assert r.status_code==200,r.text
    assert r.json()['facts']['transaction_reference']=='TEST111222333'
    assert r.json()['evidence'][0]['ocr_provider']=='local_rapidocr'

def test_response_survives_ai_outage(client,monkeypatch):
    c=submit(client,demo(client))
    base=f"/api/cases/{c['id']}"
    client.patch(base+'/preferences',json={'language':'en','ai_consent':True,'preferred_channel':'in_app'})
    monkeypatch.setenv('AI_MODE','live')
    original=main.ai.explain_response
    def flaky(case,text):
        if case['ai_consent']: raise RuntimeError('provider unavailable')
        return original(case,text)
    monkeypatch.setattr(main.ai,'explain_response',flaky)
    r=client.post(base+'/responses',json={'text':'Your payout remains pending while we investigate.','source':'entity','received_at':datetime.now(timezone.utc).isoformat()})
    assert r.status_code==200,r.text
    assert r.json()['responses'][-1]['provider']=='local_summary'


def chat(client, case, text):
    r=client.post(f"/api/cases/{case['id']}/messages",json={'text':text})
    assert r.status_code==200,r.text
    return r.json()


def test_chat_fills_complaint_and_finishes(client):
    c=client.post('/api/cases',json={}).json()
    steps=[('My broker has delayed my withdrawal.','entity_name'),
           ('Example Securities','incident_date'),('1 October 2026','amount'),
           ('5000','entity_contacted'),('no','desired_resolution'),
           ('Release my withdrawal','evidence'),('no evidence',None)]
    for answer,expected in steps:
        c=chat(client,c,answer)
        assert c['intake']['pending']==expected,c['messages'][-1]['text']
    assert c['facts']['amount']==5000
    assert c['facts']['incident_date']=='2026-10-01'
    assert c['facts']['desired_resolution']=='Release my withdrawal'
    assert c['facts']['description']=='My broker has delayed my withdrawal.'
    assert c['intake']['stage']=='review'
    c=chat(client,c,'confirm details')
    assert c['facts_confirmed'] and c['intake']['stage']=='complete'
    assert 'Release my withdrawal' in c['draft']
    assert 'Example Securities' in c['draft']
    saved_draft=c['draft']
    c=chat(client,c,'thanks')
    assert c['facts_confirmed'] and c['draft']==saved_draft
    c=chat(client,c,'organisation: Corrected Securities')
    assert c['facts']['entity_name']=='Corrected Securities'
    assert not c['facts_confirmed'] and c['draft'] is None


def test_suspicious_chat_asks_payment_and_skips_without_inventing(client):
    c=client.post('/api/cases',json={}).json()
    c=chat(client,c,'Someone sent me a suspicious investment message.')
    assert c['intake']['pending']=='money_transferred'
    c=chat(client,c,'no')
    assert c['facts']['money_transferred'] is False
    assert c['intake']['pending']=='entity_name'
    c=chat(client,c,"I don't know")
    assert c['facts']['entity_name'] is None
    assert c['intake']['pending']=='incident_date'
    c=chat(client,c,'yesterday')
    c=chat(client,c,'skip')  # sender / recipient
    c=chat(client,c,'Investigate this message')
    c=chat(client,c,'no')  # no evidence
    assert c['intake']['stage']=='review'
    assert c['facts']['amount'] is None
    assert 'confirm details' in c['messages'][-1]['text']


def test_uninterpretable_answer_does_not_loop_or_confirm_missing_facts(client):
    c=client.post('/api/cases',json={}).json()
    c=chat(client,c,'My broker has delayed my withdrawal.')
    c=chat(client,c,'Example Broker')
    c=chat(client,c,'sometime')
    assert c['intake']['pending']=='incident_date'
    c=chat(client,c,'still unsure')
    assert c['intake']['pending']=='amount'
    assert c['facts']['incident_date'] is None
    for answer in ('skip','no','Release the payment','no evidence'):
        c=chat(client,c,answer)
    assert c['intake']['stage']=='review'
    assert 'Still required' in c['messages'][-1]['text']
    r=client.post(f"/api/cases/{c['id']}/messages",json={'text':'confirm details'})
    assert r.status_code==422
    c=chat(client,c,'incident date: 2026-10-01')
    c=chat(client,c,'confirm details')
    assert c['facts_confirmed']
