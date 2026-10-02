"""Persisted intake progress shared by local and cloud extraction."""
import re
from .engine import missing
from .local_intake import QUESTIONS

QUESTIONS.update({
    'money_transferred': ('Did you actually send any money? Please answer yes or no.', 'क्या आपने पैसे भेजे थे? हाँ या नहीं बताइए।'),
    'payment_method': ('How did you pay: UPI, bank transfer, card or another method?', 'भुगतान कैसे किया: UPI, बैंक ट्रांसफर, कार्ड या कोई और तरीका?'),
    'entity_contacted': ('Have you already complained to the organisation? Please answer yes or no.', 'क्या आपने संस्था से पहले शिकायत की है? हाँ या नहीं बताइए।'),
    'entity_complaint_reference': ('What was your earlier complaint reference? Say skip if you do not have it.', 'पहली शिकायत का रेफरेंस क्या है? नहीं है तो skip लिखें।'),
    'desired_resolution': ('What would you like them to do—for example, refund the payment, release the withdrawal or correct the account?', 'आप क्या समाधान चाहते हैं—पैसे वापस, निकासी जारी करना या खाते में सुधार?'),
    'evidence': ('Do you have a receipt, screenshot or correspondence? Upload it with the paperclip, or say no evidence to continue.', 'क्या आपके पास रसीद, स्क्रीनशॉट या पत्र है? पेपरक्लिप से अपलोड करें या no evidence लिखें।'),
})

def skipped(text):
    return bool(re.fullmatch(r"(?:skip|skip for now|i (?:do not|don't|dont) know|not sure|unknown|not available|not applicable|n/?a|no evidence|none|पता नहीं|नहीं पता)[.! ]*", text.strip().lower()))

def fields(f):
    if f['category']=='unknown': return ['description' if not f['description'] else 'category']
    order=[]
    if f['category'] in ('cyber_fraud','suspicious_content'): order.append('money_transferred')
    order += missing(f)
    if f['category'] in ('cyber_fraud','suspicious_content'): order += ['entity_name','incident_date','recipient']
    if f['category'] in ('payout','broker','unauthorized_trade','mutual_fund'): order += ['amount']
    if f.get('money_transferred'): order += ['payment_method']
    if f['category'] not in ('cyber_fraud','suspicious_content'): order += ['entity_contacted']
    if f.get('entity_contacted'): order += ['entity_complaint_reference']
    return list(dict.fromkeys(order+['desired_resolution','evidence']))

def guide(case, extraction, text):
    if extraction.out_of_scope: return extraction
    state=case.setdefault('intake',{'pending':None,'skipped':[],'answered':[],'attempts':{},'stage':'collecting'})
    previous=state.get('pending')
    f=extraction.facts.model_dump(mode='json')
    if previous and skipped(text):
        if previous not in state['skipped']: state['skipped'].append(previous)
        if previous in f:
            f[previous]=case['facts'][previous]
            setattr(extraction.facts,previous,case['facts'][previous])
    if previous=='entity_contacted' and re.fullmatch(r'(yes|no|yes i did|yes i have|no i did not|no i have not|हाँ|हां|नहीं)[.! ]*',text.strip().lower()):
        state['answered'].append(previous)
    if previous=='evidence' and text.strip().lower().rstrip('.!') in ('no','नहीं'):
        state['skipped'].append('evidence')
    if case.get('evidence') and 'evidence' not in state['answered']: state['answered'].append('evidence')
    def needed(field):
        if field in state['skipped'] or field in state['answered']: return False
        if field=='evidence': return not case.get('evidence')
        if field=='entity_contacted': return not f.get(field)
        return f.get(field) in (None,'','unknown')
    remaining=[field for field in fields(f) if needed(field)]
    field=remaining[0] if remaining else None
    deferred=False
    if field and previous==field and state['attempts'].get(field,0)>=1:
        state['skipped'].append(field)
        remaining=remaining[1:]
        field=remaining[0] if remaining else None
        deferred=True
    hi=case['language']=='hi'
    if field:
        state['stage']='collecting'
        repeated=previous==field
        attempts=state['attempts'].get(field,0)+(1 if repeated else 0)
        state['attempts'][field]=attempts
        prefix=('यह उत्तर समझ नहीं आया। ' if hi else 'I could not interpret that answer. ') if repeated else ('जानकारी अपडेट हो गई। ' if hi else 'I’ve updated the form. ')
        question=QUESTIONS[field][1 if hi else 0]
        if field=='entity_name' and f['category'] in ('cyber_fraud','suspicious_content'):
            question='किस व्यक्ति या संस्था ने संपर्क किया था?' if hi else 'What name did the person or organisation use when contacting you?'
        extraction.reply=prefix+question+(' पता नहीं तो skip लिखें; मैं आगे बढ़ूँगा।' if hi else ' If you don’t know, say skip and I’ll move on.')
        if deferred: extraction.reply='I’ll leave that detail for review rather than keep asking. '+question+' You can say skip.'
    else:
        state['stage']='review'
        labels={'category':'Issue','entity_name':'Organisation / sender','amount':'Amount (INR)','incident_date':'Incident date','money_transferred':'Money sent','payment_method':'Payment method','transaction_reference':'Transaction reference','recipient':'Recipient','holding_type':'Holding type','entity_contacted':'Earlier complaint','entity_complaint_reference':'Earlier reference','desired_resolution':'Requested resolution'}
        def display(value):
            if isinstance(value,bool): return 'Yes' if value else 'No'
            return str(value).replace('_',' ')
        summary='\n'.join(f"{label}: {display(f[key])}" for key,label in labels.items() if f.get(key) not in (None,'','unknown'))
        summary+='\nEvidence files: '+str(len(case.get('evidence',[])))+'\nYour account: '+f['description']
        unresolved=missing(f)
        if unresolved:
            extraction.reply='Here is the information collected so far:\n'+summary+'\nStill required before preparing the complaint: '+', '.join(unresolved)+'. You can supply these later in chat (for example, incident date: 2026-10-01). I won’t keep asking the same question.'
        else:
            extraction.reply=('जानकारी भर दी गई है। जाँचें:\n' if hi else 'I’ve filled your case and complaint details. Please check:\n')+summary+('\nसही है तो “confirm details” लिखें। सुधार के लिए फ़ील्ड और सही जानकारी लिखें।' if hi else '\nIf correct, reply “confirm details” to prepare the complaint and prefill the next form. To correct something, tell me the field and its new value. Nothing will be submitted externally.')
    state['pending']=field
    if f['category']=='cyber_fraud' and f.get('money_transferred') and not state.get('urgent_shown'):
        extraction.reply='Call 1930 and contact your bank now; do not wait for this intake.\n'+extraction.reply
        state['urgent_shown']=True
    return extraction
