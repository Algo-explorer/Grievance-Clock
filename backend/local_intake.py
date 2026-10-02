"""Conservative local intake. Proposes facts; always requires user review."""
import re
from datetime import datetime, timedelta
from .engine import IST, missing
from .models import Facts, Extraction
from . import hinglish

QUESTIONS={
 'category':('Is this a scam, a broker payout issue, a demat issue or a share-transmission request?','यह ठगी, ब्रोकर से पैसे निकालने, डीमैट या शेयर ट्रांसफर की समस्या है?'),
 'description':('Tell me what happened in a sentence or two.','एक-दो वाक्यों में बताइए क्या हुआ।'),
 'amount':('How much money was involved? For example, ₹25,000.','कितने रुपये का मामला है? जैसे ₹25,000।'),
 'entity_name':('What is the name of the broker, company or depository participant?','ब्रोकर, कंपनी या डीपी का नाम क्या है?'),
 'incident_date':('On what date did this happen? You can say today, yesterday, or enter YYYY-MM-DD.','यह किस तारीख को हुआ? आज, कल या YYYY-MM-DD में तारीख बता सकते हैं।'),
 'transaction_reference':('What is the transaction reference or UTR? You can upload the receipt instead.','लेनदेन का UTR या रेफरेंस क्या है? रसीद भी अपलोड कर सकते हैं।'),
 'recipient':('Who received the payment? Enter the recipient name or UPI ID shown on the receipt.','पैसा किसे भेजा? रसीद में दिया नाम या UPI ID बताइए।'),
 'holding_type':('Are these demat shares or physical share certificates?','शेयर डीमैट में हैं या कागज़ के प्रमाणपत्र हैं?')}

def pending(facts):
    if facts['category']=='unknown': return 'category' if facts['description'] else 'description'
    fields=missing(facts)
    return fields[0] if fields else None

def understand(case, text, evidence=False):
    f=Facts.model_validate(case['facts']).model_dump(mode='json')
    previous=None if evidence else (case.get('intake',{}).get('pending') or pending(f))
    lower=hinglish.normalize(text).strip()
    advice=bool(re.search(r'(?:should i|shall i|recommend|tip|predict).{0,50}(?:buy|sell|stock|share|price)|\bstock tips?\b',lower))
    from .conversation import skipped
    skip=skipped(text)
    answer=re.sub(r'[.!]+$', '', lower).strip()
    yes=hinglish.boolean(text) is True
    no=hinglish.boolean(text) is False
    if not advice and not skip:
        if previous=='money_transferred' and (yes or no): f['money_transferred']=yes
        if previous=='entity_contacted' and (yes or no): f['entity_contacted']=yes
        if previous=='desired_resolution' and len(text.strip())>=3: f['desired_resolution']=text.strip()[:1000]
        if previous=='payment_method' and len(text.strip())<=80: f['payment_method']=text.strip()
        if previous=='entity_complaint_reference' and len(text.strip())<=100: f['entity_complaint_reference']=text.strip()
        resolution=re.search(r'(?i)(?:desired resolution|requested resolution|resolution)\s*(?:is|:|=)\s*(.+)',text)
        if resolution: f['desired_resolution']=resolution.group(1)[:1000]
        combined=hinglish.normalize(f['description']+' '+text)
        paid=bool(re.search(r'\bpaid\b|\b(?:sent|transferred)\s+(?:(?:the|some|my)\s+)?(?:money|funds|payment|rs\b|inr\b|₹|[0-9])|पैसे भेजे|भुगतान किया',lower))
        not_paid=bool(re.search(r'(?:not|never|haven.t|didn.t|nahi).{0,12}(?:paid|pay|sent|send|transfer|bhej)|पैसे नहीं भेजे|भुगतान नहीं',lower))
        roman_payment=hinglish.payment(text)
        if roman_payment is not None: f['money_transferred']=roman_payment
        if roman_payment is False: not_paid=True
        if any(x in combined for x in ['scam','fraud','telegram','suspicious','dhokha','thagi','ठगी','धोखा','फ्रॉड']):
            if not_paid: f['money_transferred']=False
            elif paid: f['money_transferred']=True
            f['category']='cyber_fraud' if f.get('money_transferred') else 'suspicious_content'
        elif any(x in combined for x in ['death','passed away','transmission','dehant','nidhan','guzar gaye','मृत्यु','निधन']): f['category']='transmission'
        elif any(x in combined for x in ['withdraw','payout','paise atak','paisa atak','paise nahi mil','paise nikal','paisa nahi mil','निकासी','पैसे निकाल']): f['category']='payout'
        elif 'kyc' in combined or 'signature' in combined: f['category']='kyc'
        elif any(x in combined for x in ['unauthorized','without permission','bina puche','bina pooche','bina ijazat','बिना अनुमति']): f['category']='unauthorized_trade'
        elif 'mutual fund' in combined: f['category']='mutual_fund'
        elif 'listed company' in combined or 'dividend' in combined: f['category']='listed_company'
        elif 'broker' in combined or 'ब्रोकर' in combined: f['category']='broker'
        elif 'demat' in combined or 'डीमैट' in combined: f['category']='demat'
        amount=re.search(r'(?:₹|rs\.?\s*|inr\s*|(?:paid|sent|transferred)\s+)(\d[\d,]*(?:\.\d+)?)\s*(thousand|lakh|lakhs|k\b|हज़ार|हजार|लाख)?',lower)
        if not amount: amount=re.search(r'(\d[\d,]*(?:\.\d+)?)\s*(thousand|lakh|lakhs|k\b|हज़ार|हजार|लाख|rupees|rupaye|paise|paisa|रुपये|रुपए)',lower)
        if not amount and previous=='amount': amount=re.fullmatch(r'\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakh)?\s*',lower)
        if amount:
            scale=amount.group(2) if len(amount.groups())>1 else None
            value=float(amount.group(1).replace(',',''))*(100000 if scale in ('lakh','lakhs','लाख') else 1000 if scale in ('thousand','k','हज़ार','हजार') else 1)
            if value<=1e12: f['amount']=value
        dt=re.search(r'\b(20\d{2}-\d{2}-\d{2})\b',text)
        if dt:
            try: f['incident_date']=datetime.strptime(dt.group(1),'%Y-%m-%d').date().isoformat()
            except ValueError: pass
        elif re.search(r'\btoday\b|\baaj\b|आज',lower): f['incident_date']=datetime.now(IST).date().isoformat()
        elif re.search(r'\byesterday\b|\bbeet[ae] (?:hua )?kal\b|\bkal\b.*\b(?:tha|thi|the|hua|hui)\b',lower): f['incident_date']=(datetime.now(IST).date()-timedelta(days=1)).isoformat()
        if not dt and previous=='incident_date' and not re.search(r'today|yesterday|aaj|kal|आज|कल',lower):
            date_text=re.sub(r'(\d+)(st|nd|rd|th)\b',r'\1',text.strip(),flags=re.I)
            for fmt in ('%d/%m/%Y','%d-%m-%Y','%d %B %Y','%d %b %Y','%B %d, %Y','%B %d %Y','%d %B','%d %b'):
                try:
                    parsed=datetime.strptime(date_text,fmt)
                    if '%Y' not in fmt: parsed=parsed.replace(year=datetime.now(IST).year)
                    f['incident_date']=parsed.date().isoformat();break
                except ValueError: pass
        ref=re.search(r'(?i)(?:UTR|transaction\s*(?:id|reference)|reference\s*(?:number|id)?)\s*(?:is|hai|:|#)?\s*([a-z0-9-]{6,60})',text)
        if ref: f['transaction_reference']=ref.group(1)
        elif previous=='transaction_reference' and re.fullmatch(r'[A-Za-z0-9-]{6,60}',text.strip()): f['transaction_reference']=text.strip()
        vpa=re.search(r'\b[\w.-]+@[\w.-]+\b',text)
        if vpa: f['recipient']=vpa.group()
        elif previous=='recipient' and len(text.strip())<=150 and '\n' not in text: f['recipient']=text.strip()
        if 'upi' in lower: f['payment_method']='UPI'
        entity=re.search(r'(?im)^(?:broker|company|entity|organisation|organization)(?: name)?\s*(?:is|:|=)\s*([^\n.!?]{2,150})',text)
        roman_entity=re.search(r'(?i)(?:broker|company|dp)(?: ka)? naam\s+(.+?)(?:\s+hai)?[.!]*$',text.strip())
        if roman_entity: f['entity_name']=roman_entity.group(1).strip()[:200]
        if entity: f['entity_name']=entity.group(1).strip()
        elif not roman_entity and previous=='entity_name' and len(text.strip())<=150 and not re.search(r'\b(?:don.t know|not sure|unknown|what|how)\b',lower): f['entity_name']=text.strip()
        if re.search(r'\b(?:physical|paper certificate|kagaz|kaagaz)\b|कागज़',lower): f['holding_type']='physical'
        elif 'demat' in lower or 'डीमैट' in lower: f['holding_type']='demat'
        if re.search(r'(?:already|पहले).{0,30}(?:complain|contact|email|शिकायत)',lower): f['entity_contacted']=True
        if re.search(r'\b(?:pehle|pahle)\b.*\b(?:shikayat|complaint)\b',lower):
            f['entity_contacted']='nahi' not in lower
        # Explicit field corrections also work after the conversational review.
        aliases={'organisation':'entity_name','organization':'entity_name','entity name':'entity_name','broker':'entity_name','company':'entity_name','recipient':'recipient','payment method':'payment_method','transaction reference':'transaction_reference','utr':'transaction_reference','requested resolution':'desired_resolution','description':'description','earlier reference':'entity_complaint_reference'}
        correction=re.fullmatch(r'([^:\n]+):\s*(.+)',text.strip())
        if correction and correction.group(1).strip().lower() in aliases:
            key=aliases[correction.group(1).strip().lower()]
            limit={'entity_name':200,'recipient':200,'payment_method':80,'transaction_reference':100,'desired_resolution':1000,'description':12000,'entity_complaint_reference':100}[key]
            f[key]=correction.group(2).strip()[:limit]
        if not evidence and (not f['description'] or previous in ('description','category')): f['description']=(f['description']+'\n'+text).strip()[:12000]
        elif evidence and not f['description']: f['description']='Uploaded evidence:\n'+text[:11000]
    hi=case['language']=='hi'
    if advice:
        reply='मैं निवेश की सलाह नहीं देता। शिकायत या संदिग्ध संदेश में मदद कर सकता हूँ।' if hi else 'I can help with a grievance or suspicious message, but cannot give investment recommendations.'
    else:
        field=pending(f)
        reply=('आपकी जानकारी सुरक्षित कर ली है। ' if hi else 'I’ve saved that detail. ')+(QUESTIONS[field][1 if hi else 0] if field else ('अब जानकारी जाँचकर शिकायत तैयार करें।' if hi else 'The essential details are ready. Review the facts to prepare your complaint.'))
        if f['category']=='cyber_fraud' and f.get('money_transferred'):
            reply=('अभी 1930 पर कॉल करें और अपने बैंक को सूचित करें। रिपोर्ट पूरी होने का इंतज़ार न करें। ' if hi else 'Call 1930 and contact your bank now. Do not wait for the report. ')+reply
    return Extraction(facts=Facts(**f),normalized_text=hinglish.normalize(text) if hinglish.detect(text) else text,reply=reply,out_of_scope=advice),'local_rules'
