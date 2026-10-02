"""Conservative local intake. Proposes facts; always requires user review."""
import re
from datetime import datetime, timedelta
from .engine import IST, missing
from .models import Facts, Extraction

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
    previous=pending(f)
    lower=text.lower().strip()
    advice=bool(re.search(r'(?:should i|shall i|recommend|tip|predict).{0,50}(?:buy|sell|stock|share|price)|\bstock tips?\b|khar[ie]ed',lower))
    if not advice:
        combined=(f['description']+' '+text).lower()
        paid=bool(re.search(r'\b(?:paid|sent|transferred|bhej|diye|dedie|diya)\b|भेज|दिए|दिया|ट्रांसफर',combined))
        not_paid=bool(re.search(r'(?:not|never|haven.t|didn.t|nahi).{0,12}(?:paid|pay|sent|send|transfer|bhej)|पैसे नहीं भेजे|भुगतान नहीं',lower))
        if any(x in combined for x in ['scam','fraud','telegram','ठगी','धोखा','फ्रॉड']):
            f['category']='cyber_fraud' if (paid or f.get('money_transferred')) and not not_paid else 'suspicious_content'
            if not_paid: f['money_transferred']=False
            elif paid: f['money_transferred']=True
        elif any(x in combined for x in ['death','passed away','transmission','मृत्यु','निधन']): f['category']='transmission'
        elif any(x in combined for x in ['withdraw','payout','निकासी','पैसे निकाल']): f['category']='payout'
        elif 'kyc' in combined or 'signature' in combined: f['category']='kyc'
        elif any(x in combined for x in ['unauthorized','without permission','बिना अनुमति']): f['category']='unauthorized_trade'
        elif 'broker' in combined or 'ब्रोकर' in combined: f['category']='broker'
        elif 'demat' in combined or 'डीमैट' in combined: f['category']='demat'
        amount=re.search(r'(?:₹|rs\.?\s*|inr\s*|(?:paid|sent|transferred)\s+)([\d,]+(?:\.\d+)?)\s*(thousand|lakh|lakhs|k\b|हज़ार|हजार|लाख)?',lower)
        if not amount: amount=re.search(r'([\d,]+(?:\.\d+)?)\s*(thousand|lakh|lakhs|k\b|हज़ार|हजार|लाख|rupees|rupaye|रुपये|रुपए)',lower)
        if not amount and previous=='amount': amount=re.fullmatch(r'\s*([\d,]+(?:\.\d+)?)\s*(k|thousand|lakh)?\s*',lower)
        if amount:
            scale=amount.group(2) if len(amount.groups())>1 else None
            value=float(amount.group(1).replace(',',''))*(100000 if scale in ('lakh','lakhs','लाख') else 1000 if scale in ('thousand','k','हज़ार','हजार') else 1)
            if value<=1e12: f['amount']=value
        dt=re.search(r'\b(20\d{2}-\d{2}-\d{2})\b',text)
        if dt:
            try: f['incident_date']=datetime.strptime(dt.group(1),'%Y-%m-%d').date().isoformat()
            except ValueError: pass
        elif re.search(r'\btoday\b|\baaj\b|आज',lower): f['incident_date']=datetime.now(IST).date().isoformat()
        elif re.search(r'\byesterday\b|\bkal\b|कल',lower): f['incident_date']=(datetime.now(IST).date()-timedelta(days=1)).isoformat()
        ref=re.search(r'(?i)(?:UTR|transaction\s*(?:id|reference)|reference\s*(?:number|id)?)\s*(?:is|hai|:|#)?\s*([a-z0-9-]{6,60})',text)
        if ref: f['transaction_reference']=ref.group(1)
        elif previous=='transaction_reference' and re.fullmatch(r'[A-Za-z0-9-]{6,60}',text.strip()): f['transaction_reference']=text.strip()
        vpa=re.search(r'\b[\w.-]+@[\w.-]+\b',text)
        if vpa: f['recipient']=vpa.group()
        elif previous=='recipient' and len(text.strip())<=150 and '\n' not in text: f['recipient']=text.strip()
        if 'upi' in lower: f['payment_method']='UPI'
        entity=re.search(r'(?im)^(?:broker|company|entity|organisation|organization)(?: name)?\s*(?:is|:|=)\s*([^\n.!?]{2,150})',text)
        if entity: f['entity_name']=entity.group(1).strip()
        elif previous=='entity_name' and len(text.strip())<=150 and not re.search(r'\b(?:don.t know|not sure|unknown|what|how)\b',lower): f['entity_name']=text.strip()
        if re.search(r'\b(?:physical|paper certificate)\b|कागज़',lower): f['holding_type']='physical'
        elif 'demat' in lower or 'डीमैट' in lower: f['holding_type']='demat'
        if re.search(r'(?:already|पहले).{0,30}(?:complain|contact|email|शिकायत)',lower): f['entity_contacted']=True
        if not evidence: f['description']=(f['description']+'\n'+text).strip()[:12000]
        elif not f['description']: f['description']='Uploaded evidence:\n'+text[:11000]
    hi=case['language']=='hi'
    if advice:
        reply='मैं निवेश की सलाह नहीं देता। शिकायत या संदिग्ध संदेश में मदद कर सकता हूँ।' if hi else 'I can help with a grievance or suspicious message, but cannot give investment recommendations.'
    else:
        field=pending(f)
        reply=('आपकी जानकारी सुरक्षित कर ली है। ' if hi else 'I’ve saved that detail. ')+(QUESTIONS[field][1 if hi else 0] if field else ('अब जानकारी जाँचकर शिकायत तैयार करें।' if hi else 'The essential details are ready. Review the facts to prepare your complaint.'))
        if f['category']=='cyber_fraud' and f.get('money_transferred'):
            reply=('अभी 1930 पर कॉल करें और अपने बैंक को सूचित करें। रिपोर्ट पूरी होने का इंतज़ार न करें। ' if hi else 'Call 1930 and contact your bank now. Do not wait for the report. ')+reply
    return Extraction(facts=Facts(**f),normalized_text=text,reply=reply,out_of_scope=advice),'local_rules'
