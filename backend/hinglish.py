"""Targeted Roman-Hindi understanding; original statements and identifiers stay intact."""
import re

QUESTIONS={
 'category':'Yeh fraud, broker payout, demat ya shares transfer ka issue hai?',
 'description':'Apne shabdon mein batayein, kya hua tha?',
 'money_transferred':'Kya aapne paise bheje the? Haan ya nahi batayein.',
 'amount':'Kitne paise ka mamla hai? Jaise 25000 ya pachis hazaar.',
 'entity_name':'Broker, company ya DP ka naam kya hai?',
 'incident_date':'Yeh kis tareekh ko hua tha? Jaise 1 October 2026 ya aaj. Kal se matlab beeta hua kal hai?',
 'transaction_reference':'Transaction ka UTR ya reference number kya hai? Receipt bhi upload kar sakte hain.',
 'recipient':'Paise kisko bheje? Receipt par diya naam ya UPI ID batayein.',
 'holding_type':'Shares demat mein hain ya physical kagaz ke certificates hain?',
 'payment_method':'Payment kaise kiya: UPI, bank transfer, card ya koi aur tareeka?',
 'entity_contacted':'Kya aapne company se pehle shikayat ki hai? Haan ya nahi batayein.',
 'entity_complaint_reference':'Pehli shikayat ka reference number kya hai? Nahi pata toh skip likhein.',
 'desired_resolution':'Aap kya samadhan chahte hain? Jaise paise wapas, withdrawal release ya account mein sudhar.',
 'evidence':'Receipt, screenshot ya email hai? Paperclip se upload karein, ya saboot nahi hai likhein.'}

def detect(text):
    return bool(re.search(r'\b(?:mera|mere|meri|maine|mene|mujhe|paise|paisa|nahi|nahin|nhi|haan|hanji|shikayat|dhokha|hua|huya|chahiye|bheje|bheja|hai|hain|pata)\b',text.lower()))

def active(case):
    return case['language']=='hi-Latn' or case.get('chat_style')=='hinglish'

def boolean(text):
    # Read polarity in conversational replies, not only exact whole-string matches.
    t=normalize(text).strip()
    if re.search(r'\b(?:shayad|maybe|not sure|pata nahi|malum nahi)\b',t): return None
    negative=bool(re.search(r"\b(?:nahi|no|never|not|didn't|haven't)\b|नहीं",t))
    affirmative=bool(re.search(r'\b(?:h+a+n*|hanji|yes|yep|yeah|bilkul|zaroor|ji)\b|हाँ|हां',t))
    if negative: return False
    if affirmative: return True
    if re.search(r'\b(?:kar di|kar diya|ki hai|ki thi|kiya tha|bhej diye|bheje the)\b',t): return True
    return None

def normalize(text):
    t=text.lower()
    for pattern,value in [(r'\b(?:nhi|nahin|nai|nahee|nahii|nahiii)\b','nahi'),(r'\b(?:hazar|hazaar|hajaar|hajar)\b','thousand'),(r'\b(?:lac|lacs|lakhs)\b','lakh'),(r'\b(?:rupay|rupaye|rupaiye|rupe)\b','rupees')]:
        t=re.sub(pattern,value,t)
    numbers={'ek':1,'do':2,'teen':3,'char':4,'chaar':4,'paanch':5,'panch':5,'che':6,'chhe':6,'saat':7,'aath':8,'nau':9,'das':10,'dus':10,'bees':20,'bis':20,'pachis':25,'pachchis':25,'pachees':25,'tees':30,'pachas':50,'pachaas':50,'sau':100,'dedh':1.5,'dhai':2.5}
    for word,number in numbers.items():
        t=re.sub(r'\b'+word+r'(?=\s+(?:thousand|lakh|rupees)\b)',str(number),t)
    return t

def payment(text):
    t=normalize(text)
    # Negation can precede or follow the verb in Roman Hindi.
    has_money=bool(re.search(r'\b(?:paise|paisa|payment|rupees|thousand|lakh|money|funds)\b|₹|\d',t))
    transfer=bool(re.search(r'\b(?:bhej\w*|transfer\w*|pay\w*)\b|\b(?:paise|paisa|rupees)\b.{0,20}\b(?:diye|diya)\b',t))
    if has_money and transfer:
        if re.search(r'\bnahi\b',t): return False
        if re.search(r'\b(?:bheje|bheja|diye|diya|kiya|kiye|paid|transferred)\b',t): return True
    return None
