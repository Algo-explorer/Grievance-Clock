import asyncio
import hashlib
import io
import json
import os
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from collections import defaultdict, deque
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import JSONResponse
from PIL import Image
from pypdf import PdfReader
from .models import *
from .storage import Store
from .engine import now, event, refresh, add_clock, reminders, next_escalation, RULES
from . import intelligence as ai
from . import documents

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env.local')
store = Store(Path(os.getenv('DATA_DIR', str(ROOT / 'data'))))
allowed_origins = set(os.getenv('ALLOWED_ORIGINS','http://127.0.0.1:3000,http://localhost:3000').split(','))
rate_buckets = defaultdict(deque)
rate_lock = Lock()

async def scheduler():
    while True:
        await asyncio.sleep(60)
        def tick():
            for owner, case in store.all_cases():
                if reminders(case):
                    try: store.save(owner, case)
                    except HTTPException: pass
        await asyncio.to_thread(tick)

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(scheduler())
    yield
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass

app = FastAPI(title='Grievance Clock', version='1.0.0', lifespan=lifespan)

@app.middleware('http')
async def protect(request: Request, call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin = request.headers.get('origin')
        if origin and origin not in allowed_origins:
            return JSONResponse({'detail':'Origin not allowed'}, status_code=403)
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail':'Cross-site request blocked'}, status_code=403)
        try: size=int(request.headers.get('content-length','0'))
        except ValueError: size=0
        if size > 13*1024*1024:
            return JSONResponse({'detail':'Maximum upload is 10 MB (audio: 12 MB).'},status_code=413)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

def owner(request: Request):
    result=store.session(request.cookies.get('gc_session'))
    if not result: raise HTTPException(401,'Start a private session first')
    return result

def limited(who):
    with rate_lock:
        q=rate_buckets[who]
        while q and q[0] < time.monotonic()-60: q.popleft()
        if len(q)>=15: raise HTTPException(429,'Please wait a moment before trying again.')
        q.append(time.monotonic())

def mutable(case):
    if case['status']=='resolved': raise HTTPException(409,'This case is resolved. Create a new case for a new issue.')

def public(case):
    refresh(case)
    case['escalation']=next_escalation(case)
    return case

@app.get('/api/health')
def health():
    return {'ok':True,'ai_mode':os.getenv('AI_MODE','live'),'ai_configured':bool(os.getenv('OPENAI_API_KEY')),'filing_mode':'simulation_and_assisted','rules_version':RULES['version']}

@app.post('/api/session')
def session(request: Request, response: Response):
    if not store.session(request.cookies.get('gc_session')):
        token,_=store.new_session()
        response.set_cookie('gc_session',token,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE','false')=='true',max_age=30*86400,path='/')
    return {'ok':True}

@app.get('/api/cases')
def list_cases(who=Depends(owner)):
    return [public(c) for c in store.list(who)]

@app.post('/api/cases',status_code=201)
def create_case(body: NewCase, who=Depends(owner)):
    limited(who)
    case={'id':'GC-'+uuid.uuid4().hex[:10].upper(),'created_at':now(),'updated_at':now(),'status':'collecting_information',
          **body.model_dump(),'facts':Facts().model_dump(mode='json'),'facts_confirmed':False,'messages':[], 'evidence':[],
          'filings':[],'events':[],'deadlines':[],'notifications':[],'responses':[],'fraud_analysis':None,'draft':None,'pending_portal':None}
    event(case,'CASE_CREATED')
    return public(store.create(who,case))

@app.get('/api/cases/{case_id}')
def get_case(case_id: str, who=Depends(owner)):
    case=store.get(who,case_id)
    if reminders(case): store.save(who,case)
    return public(case)

@app.delete('/api/cases/{case_id}')
def delete_case(case_id: str, who=Depends(owner)):
    store.delete(who,case_id)
    return {'deleted':True}

@app.patch('/api/cases/{case_id}/preferences')
def preferences(case_id: str, body: Preferences, who=Depends(owner)):
    c=store.get(who,case_id)
    c.update(body.model_dump())
    event(c,'PREFERENCES_UPDATED')
    return public(store.save(who,c))

@app.post('/api/cases/{case_id}/messages')
def message(case_id: str, body: MessageIn, who=Depends(owner)):
    limited(who)
    c=store.get(who,case_id); mutable(c)
    if ai.sensitive(body.text): raise HTTPException(422,'Remove OTPs, PINs or passwords before sending. We do not need them.')
    try: extraction, provider=ai.extract(c,body.text)
    except Exception:
        raise HTTPException(503,'The AI service is unavailable. Your message was not saved. Retry, or switch off AI sharing to use local intake and manual facts.')
    c['messages'].append({'id':uuid.uuid4().hex,'role':'user','text':body.text,'normalized_text':extraction.normalized_text,'at':now()})
    c['messages'].append({'id':uuid.uuid4().hex,'role':'assistant','text':extraction.reply,'provider':provider,'at':now()})
    if not extraction.out_of_scope:
        c['facts']=extraction.facts.model_dump(mode='json'); c['facts_confirmed']=False; c['draft']=None
        if c['status']=='ready_to_submit': c['status']='ready_for_review'
        event(c,'FACTS_EXTRACTED',{'provider':provider})
    return public(store.save(who,c))

@app.put('/api/cases/{case_id}/facts')
def confirm(case_id: str, body: ConfirmFacts, who=Depends(owner)):
    c=store.get(who,case_id); mutable(c)
    if body.revision != c['revision']: raise HTTPException(409,'Case changed. Refresh before confirming.')
    c['facts']=body.facts.model_dump(mode='json'); refresh(c)
    if c['missing_fields'] or c['facts']['category']=='unknown':
        raise HTTPException(422,'Please complete required fields and choose a category: '+', '.join(c['missing_fields']))
    if ai.sensitive(c['facts']['description']): raise HTTPException(422,'Remove OTPs, PINs or passwords.')
    c['facts_confirmed']=True
    for ev in c['evidence']: ev['verified']=True
    c['draft']=documents.complaint(c)
    event(c,'FACTS_CONFIRMED')
    return public(store.save(who,c))

@app.post('/api/cases/{case_id}/evidence')
def evidence(case_id: str, file: UploadFile=File(...), who=Depends(owner)):
    limited(who)
    c=store.get(who,case_id); mutable(c)
    if len(c['evidence'])>=20: raise HTTPException(422,'Maximum 20 evidence files per case.')
    raw=file.file.read(10*1024*1024+1)
    if not raw or len(raw)>10*1024*1024: raise HTTPException(413,'Choose a non-empty file up to 10 MB.')
    name=Path(file.filename or 'evidence').name[:160]
    suffix=Path(name).suffix.lower()
    text=''; image=None; mime='text/plain'
    try:
        if suffix in ('.png','.jpg','.jpeg','.webp'):
            im=Image.open(io.BytesIO(raw)); im.verify()
            if im.width*im.height>25_000_000: raise ValueError('Image too large')
            mime={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(im.format)
            if not mime: raise ValueError('Invalid image')
            image=(mime,raw)
        elif suffix=='.pdf':
            if not raw.startswith(b'%PDF-'): raise ValueError('Invalid PDF')
            reader=PdfReader(io.BytesIO(raw))
            if reader.is_encrypted or len(reader.pages)>50: raise ValueError('Encrypted or long PDF')
            text='\n'.join((p.extract_text() or '') for p in reader.pages[:20])[:16000]
            mime='application/pdf'
        elif suffix=='.txt': text=raw.decode('utf-8')[:16000]
        else: raise ValueError('Unsupported file')
    except Exception: raise HTTPException(422,'Use a readable PNG, JPG, WebP, UTF-8 TXT or unencrypted PDF (up to 50 pages).')
    if ai.sensitive(text): raise HTTPException(422,'This document appears to contain a secret. Upload a redacted copy.')
    ev={'id':uuid.uuid4().hex,'name':name,'mime':mime,'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'verified':False,'created_at':now(),'extraction_status':'needs_manual_review'}
    if (text or image) and ai.mode(c)=='live':
        try:
            extraction,_=ai.extract(c,'Extract facts from this evidence. '+text,image)
            ev['proposed_facts']=extraction.facts.model_dump(mode='json')
            ev['extraction_status']='extracted_unverified'
            c['facts']=extraction.facts.model_dump(mode='json')
        except Exception: ev['extraction_status']='service_unavailable_manual_review'
    elif text:
        extraction,_=ai.fallback(c,text)
        ev['proposed_facts']=extraction.facts.model_dump(mode='json'); c['facts']=extraction.facts.model_dump(mode='json')
        ev['extraction_status']='local_rules_unverified'
    ev['extracted_text']=text
    store.write_evidence(ev['id'],raw)
    c['evidence'].append(ev); c['facts_confirmed']=False; c['draft']=None
    if c['status']=='ready_to_submit': c['status']='ready_for_review'
    event(c,'EVIDENCE_ADDED',{'name':name,'sha256':ev['sha256']})
    try: return public(store.save(who,c))
    except Exception:
        (store.root/'evidence'/ev['id']).unlink(missing_ok=True)
        raise

@app.get('/api/cases/{case_id}/evidence/{evidence_id}')
def download_evidence(case_id: str,evidence_id: str,who=Depends(owner)):
    c=store.get(who,case_id)
    ev=next((e for e in c['evidence'] if e['id']==evidence_id),None)
    if not ev: raise HTTPException(404,'Evidence not found')
    return Response(store.read_evidence(ev['id']),media_type=ev['mime'],headers={'Content-Disposition':f'attachment; filename="evidence-{ev["id"]}{Path(ev["name"]).suffix}"'})

@app.post('/api/cases/{case_id}/transcribe')
def transcribe(case_id: str,file: UploadFile=File(...),who=Depends(owner)):
    limited(who)
    c=store.get(who,case_id)
    if ai.mode(c)!='live': raise HTTPException(422,'Enable AI sharing for voice transcription, or type your message.')
    raw=file.file.read(12*1024*1024+1)
    if not raw or len(raw)>12*1024*1024: raise HTTPException(413,'Audio must be under 12 MB.')
    try: text=ai.transcribe(raw,'voice.webm',c['language'])
    except Exception: raise HTTPException(503,'Voice transcription is unavailable. Please type your message or retry.')
    return {'text':text,'notice':'Review the transcript before sending. Audio was not stored.'}

@app.post('/api/cases/{case_id}/fraud-analysis')
def fraud_analysis(case_id: str,who=Depends(owner)):
    limited(who)
    c=store.get(who,case_id)
    url=os.getenv('FRAUD_API_URL')
    if not url: raise HTTPException(503,'Your team’s fraud-model URL is not configured. This case can continue without it.')
    try:
        with httpx.Client(timeout=10,follow_redirects=False) as client:
            result=client.post(url,json={'text':c['facts']['description'],'evidence_ids':[e['id'] for e in c['evidence']]},headers={'Authorization':'Bearer '+os.getenv('FRAUD_API_TOKEN','')})
            result.raise_for_status()
            parsed=FraudResult.model_validate(result.json())
    except Exception: raise HTTPException(503,'Fraud analysis is unavailable. No route or deadline was changed.')
    c['fraud_analysis']={'source':'team_fraud_model',**parsed.model_dump(),'at':now()}
    event(c,'FRAUD_ANALYSIS_RECEIVED')
    return public(store.save(who,c))

def ready(c):
    mutable(c)
    if not c['facts_confirmed'] or not c['draft']: raise HTTPException(422,'Review and confirm facts before preparing a submission.')

@app.post('/api/cases/{case_id}/simulate')
def simulate(case_id: str, body: Submission, who=Depends(owner)):
    c=store.get(who,case_id)
    prior=next((f for f in c['filings'] if f.get('idempotency_key')==body.idempotency_key),None)
    if prior: return public(c)
    ready(c)
    if not body.approved: raise HTTPException(422,'Explicit approval is required.')
    if body.revision!=c['revision']: raise HTTPException(409,'Case changed. Review the new draft.')
    if c['filings'] and not c['pending_portal']: raise HTTPException(409,'A filing is already recorded. Use the response and escalation workflow.')
    portal=c['pending_portal'] or c['route']['id']
    if portal=='clarify': raise HTTPException(422,'Confirm the route first.')
    filed={'portal':portal,'reference_number':'DEMO-'+uuid.uuid4().hex[:10].upper(),'submitted_at':now(),'simulated':True,'idempotency_key':body.idempotency_key}
    c['filings'].append(filed); c['status']='awaiting_response'; c['pending_portal']=None
    ev=event(c,'SIMULATED_SUBMISSION',filed)
    trigger={'SCORES':'SCORES_RECEIVED','entity':'ENTITY_SUBMITTED','offline':'OFFLINE_SUBMITTED','NCRP':'NCRP_SUBMITTED'}.get(portal)
    add_clock(c,trigger,filed['submitted_at'],True,ev['id'])
    for d in c['deadlines']:
        if d['type']==portal: d['status']='completed'
    return public(store.save(who,c))

@app.post('/api/cases/{case_id}/acknowledgements')
def acknowledge(case_id: str,body: Acknowledgement,who=Depends(owner)):
    c=store.get(who,case_id); ready(c)
    if not body.confirmed: raise HTTPException(422,'Confirm that you received this acknowledgement.')
    if body.occurred_at.tzinfo is None or body.occurred_at>datetime.now(timezone.utc): raise HTTPException(422,'Use an actual past acknowledgement time with timezone.')
    if body.reference_number.upper().startswith('DEMO-'): raise HTTPException(422,'A demo reference cannot be recorded as a real acknowledgement.')
    if any(f['reference_number']==body.reference_number and not f['simulated'] for f in c['filings']): return public(c)
    expected=c['pending_portal'] or c['route']['id']
    if body.portal!=expected: raise HTTPException(422,'Acknowledgement must match the prepared route: '+expected)
    for d in c['deadlines']:
        if d['simulated'] or d['type']==body.portal: d['status']='superseded'
    f={'portal':body.portal,'reference_number':body.reference_number,'submitted_at':body.occurred_at.isoformat(),'simulated':False,'verification':'user_reported'}
    c['filings'].append(f); c['status']='awaiting_response'; c['pending_portal']=None
    ev=event(c,'ACKNOWLEDGEMENT_RECORDED',f,body.occurred_at.isoformat())
    trigger={'SCORES':'SCORES_RECEIVED','entity':'ENTITY_SUBMITTED','offline':'OFFLINE_SUBMITTED','NCRP':'NCRP_SUBMITTED'}.get(body.portal)
    add_clock(c,trigger,body.occurred_at.isoformat(),False,ev['id'])
    return public(store.save(who,c))

@app.post('/api/cases/{case_id}/responses')
def official_response(case_id: str,body: ResponseIn,who=Depends(owner)):
    limited(who)
    c=store.get(who,case_id); mutable(c)
    if not c['filings']: raise HTTPException(422,'Record an acknowledgement or a demo filing first.')
    if c['status']!='awaiting_response': raise HTTPException(409,'A response is already recorded for this stage. Complete the next step before recording another.')
    if body.received_at.tzinfo is None or body.received_at>datetime.now(timezone.utc): raise HTTPException(422,'Use the actual response time, including timezone.')
    latest=c['filings'][-1]
    if body.received_at < datetime.fromisoformat(latest['submitted_at']): raise HTTPException(422,'Response cannot predate the recorded filing.')
    expected={'SCORES':'SCORES_ENTITY_ATR','review_1':'SCORES_REVIEW_1_ATR'}.get(latest['portal'],'entity')
    if body.source!=expected: raise HTTPException(422,'Choose the response source for the latest filing: '+expected)
    if ai.sensitive(body.text): raise HTTPException(422,'Remove secret credentials before sending.')
    try: explanation=ai.explain_response(c,body.text)
    except Exception: raise HTTPException(503,'Response explanation is unavailable. Please retry.')
    for d in c['deadlines']:
        if d['status']=='open': d['status']='completed'
    r={**body.model_dump(mode='json'),'explanation':explanation,'id':uuid.uuid4().hex}
    c['responses'].append(r); c['status']='response_received'
    ev=event(c,'RESPONSE_RECEIVED',{'source':body.source},body.received_at.isoformat())
    add_clock(c,body.source,body.received_at.isoformat(),latest['simulated'],ev['id'])
    return public(store.save(who,c))

@app.post('/api/cases/{case_id}/decision')
def decision(case_id: str,body: Decision,who=Depends(owner)):
    c=store.get(who,case_id); mutable(c)
    if not c['responses']: raise HTTPException(422,'Record a response first.')
    c['status']='resolved' if body.satisfied else 'escalation_ready'
    event(c,'CASE_RESOLVED' if body.satisfied else 'USER_NOT_SATISFIED')
    if body.satisfied:
        for d in c['deadlines']:
            if d['status']=='open': d['status']='completed'
    return public(store.save(who,c))

@app.post('/api/cases/{case_id}/escalate')
def escalate(case_id: str,who=Depends(owner)):
    c=store.get(who,case_id); ready(c)
    esc=next_escalation(c)
    if not esc or not esc['available']: raise HTTPException(422,'No automatic escalation is available. Check official options.')
    if c['pending_portal']: return public(c)
    c['pending_portal']=esc['portal']; c['status']='ready_to_submit'
    previous=c['filings'][-1]
    c['draft']=documents.complaint(c)+'\n\nEscalation to: '+esc['title']+'\nPrevious acknowledgement: '+previous['reference_number']
    if c['responses']: c['draft']+='\nPrevious response:\n'+c['responses'][-1]['text']
    event(c,'ESCALATION_PREPARED',{'portal':esc['portal']})
    return public(store.save(who,c))

@app.get('/api/cases/{case_id}/documents/{kind}')
def document(case_id: str,kind: str,who=Depends(owner)):
    c=store.get(who,case_id)
    if not c['facts_confirmed']: raise HTTPException(422,'Confirm the facts before downloading your documents.')
    if kind in ('complaint.pdf','offline.pdf'):
        return Response(documents.pdf(c,kind=='offline.pdf'),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{c["id"]}-{kind}"'})
    if kind=='dossier.zip':
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('complaint.pdf',documents.pdf(c))
            z.writestr('case-record.json',json.dumps(c,ensure_ascii=False,indent=2))
            for e in c['evidence']:
                z.writestr('originals/'+e['id']+Path(e['name']).suffix,store.read_evidence(e['id']))
        return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="{c["id"]}-dossier.zip"'})
    raise HTTPException(404,'Unknown document')

@app.post('/api/cases/{case_id}/notifications/read')
def read_notifications(case_id: str,who=Depends(owner)):
    c=store.get(who,case_id)
    for n in c['notifications']: n['read']=True
    return public(store.save(who,c))

@app.get('/api/resources')
def resources():
    return {'sources':RULES['sources'],'rules_version':RULES['version'],'directory_notice':'Use your own DP / registrar. Addresses and official forms must be confirmed with that institution.','contact':[{'label':'Urgent financial cyber fraud','phone':'1930','url':'https://cybercrime.gov.in/'}]}

@app.post('/api/demo/{scenario}')
def demo(scenario: Literal['scam','broker','offline'],who=Depends(owner)):
    c=create_case(NewCase(ai_consent=False),who)
    examples={
        'scam':Facts(category='cyber_fraud',description='A person in a Telegram group claimed to arrange an IPO allocation. I paid INR 25000 by UPI. They stopped responding after receiving payment. All names and identifiers in this case are synthetic.',amount=25000,incident_date=datetime.now().date(),payment_method='UPI',transaction_reference='DEMO-UTR-250001',recipient='demo-suspect@example',money_transferred=True,desired_resolution='Please investigate the reported transfer and advise on the available recovery process.'),
        'broker':Facts(category='payout',description='My withdrawal request has not been processed for ten days. I request an explanation and release of the pending payout. This is a synthetic demonstration case.',entity_name='Example Securities (fictional)',amount=18000,incident_date=datetime.now().date(),desired_resolution='Process my pending withdrawal and provide a written explanation.'),
        'offline':Facts(category='transmission',description='After my husband passed away, I need help transferring the shares held in his demat account. This is a synthetic demonstration case.',entity_name='Example Depository Participant (fictional)',holding_type='demat',desired_resolution='Please provide the applicable transmission form and document requirements.')}
    c['facts']=examples[scenario].model_dump(mode='json'); c['is_demo']=True
    text=c['facts']['description']
    c['messages']=[{'id':uuid.uuid4().hex,'role':'user','text':text,'at':now()},{'id':uuid.uuid4().hex,'role':'assistant','text':'This is a fictional demo case. '+('Call 1930 and your bank immediately for a real transferred-money scam. ' if scenario=='scam' else '')+'Review the facts, generate your documents and try the clearly marked filing simulation.','provider':'demo','at':now()}]
    return public(store.save(who,c))
