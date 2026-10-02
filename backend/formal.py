"""Formal summaries from known facts; original wording remains in the case record."""
import re
from . import hinglish

def fields(case):
    f=dict(case['facts'])
    source=f['description']
    roman=hinglish.detect(source) or bool(re.search(r'[\u0900-\u097f]',source))
    if roman:
        summaries={
            'payout':'I wish to raise a grievance concerning a delayed withdrawal or payout.',
            'broker':'I wish to raise a grievance concerning the services provided by my broker.',
            'cyber_fraud':'I wish to report suspected financial fraud involving a payment I made.',
            'suspicious_content':'I wish to report a suspicious investment communication.',
            'demat':'I wish to raise a grievance concerning my demat account.',
            'unauthorized_trade':'I wish to report trading activity that I did not authorise.',
            'transmission':'I request assistance with the transmission of securities following the death of the holder.',
            'kyc':'I request assistance with a KYC or account-record issue.',
            'mutual_fund':'I wish to raise a grievance concerning my mutual fund investment.',
            'listed_company':'I wish to raise a grievance concerning a listed company.'}
        f['description']=summaries.get(f['category'],'I request assistance with the investment-related issue described in my case record.')
        if f.get('entity_name'): f['description']+=' The organisation identified in my account is '+f['entity_name']+'.'
        if f.get('incident_date'): f['description']+=' The reported incident date is '+f['incident_date']+'.'
        if f.get('entity_contacted'): f['description']+=' I have already raised this matter with the organisation.'
    resolution=f.get('desired_resolution') or ''
    if hinglish.detect(resolution) or re.search(r'[\u0900-\u097f]',resolution):
        t=hinglish.normalize(resolution)
        if re.search(r'wap[ai]s|refund|वापस',t):
            f['desired_resolution']='Please investigate this matter and arrange the return of the funds due to me.'
        elif re.search(r'withdraw|release|nikal|निकासी',t):
            f['desired_resolution']='Please investigate the delay and release my pending withdrawal.'
        elif re.search(r'sudhar|theek|sahi|correct|सुधार',t):
            f['desired_resolution']='Please investigate and correct the relevant account records.'
        else:
            f['desired_resolution']='Please investigate this matter, provide a written explanation and advise me of the available redressal steps.'
    return f

def preview(case):
    f=fields(case)
    changed=any(f.get(k)!=case['facts'].get(k) for k in ('description','desired_resolution'))
    return {'facts':f,'notice':'This formal summary uses the collected facts, not a word-for-word translation. Check that all important details and your requested remedy are included before confirming.' if changed else None}
