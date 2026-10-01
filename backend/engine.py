import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

RULES = json.loads(Path(__file__).with_name('rules.json').read_text())
IST = timezone(timedelta(hours=5, minutes=30))

def now():
    return datetime.now(timezone.utc).isoformat()

def event(case, kind, metadata=None, occurred_at=None):
    ev = {'id': uuid.uuid4().hex, 'type': kind, 'occurred_at': occurred_at or now(), 'metadata': metadata or {}}
    case['events'].append(ev)
    case['updated_at'] = now()
    return ev

def missing(facts):
    cat = facts['category']
    fields = RULES['required'].get(cat, RULES['required']['securities'])
    return [f for f in fields if facts.get(f) is None or facts.get(f) == '' or (f == 'holding_type' and facts[f] == 'unknown')]

def route(case):
    f = case['facts']
    category = f['category']
    urgent = category == 'cyber_fraud' and f.get('money_transferred') is True
    if category == 'cyber_fraud':
        r = {'id':'NCRP','title':'Cybercrime reporting + your bank','url':RULES['sources']['cybercrime'], 'steps':['Call 1930 now if you transferred money. Do not wait for a complete evidence pack.','Contact your bank through its official app or the number on your card.','Review the report, then complete the official portal authentication yourself.'], 'mode':'assisted_online'}
    elif category == 'suspicious_content':
        r = {'id':'NCRP','title':'Report suspicious content','url':RULES['sources']['cybercrime'],'steps':['Do not send money or share OTPs.','Preserve the message and sender details.','Use the official portal to report the suspicious activity.'],'mode':'assisted_online'}
    elif category in ('transmission', 'kyc'):
        r = {'id':'offline','title':'Your DP / registrar assistance','url':RULES['sources']['dp'],'steps':['Confirm whether the holding is in demat or physical form.','Contact your own DP or registrar for the current applicable form and checklist.','Take the printed action pack; obtain a dated acknowledgement.'],'mode':'physical_action'}
    elif category == 'unknown':
        r = {'id':'clarify','title':'Tell us a little more','url':None,'steps':['Explain what happened and which organisation is involved.'],'mode':'collect_information'}
    else:
        contacted = f.get('entity_contacted', False)
        r = {'id':'SCORES' if contacted else 'entity','title':'SEBI SCORES' if contacted else 'Entity grievance officer','url':RULES['sources']['scores'] if contacted else None,'steps':(['Keep the earlier entity complaint and reply.','Check that the entity and grievance are eligible on SCORES.','Prepare your complaint and complete official authentication.'] if contacted else ['First raise the complaint with the entity grievance officer.','Keep a copy and the acknowledgement.','If unresolved, prepare a SCORES complaint.']), 'mode':'assisted_online'}
    r['urgent'] = urgent
    r['rule_version'] = RULES['version']
    return r

def add_clock(case, trigger, occurred_at, simulated=False, event_id=None):
    rule = RULES['clocks'].get(trigger)
    if not rule:
        return
    if any(d['trigger_event_id'] == event_id and d['type'] == rule['type'] for d in case['deadlines']):
        return
    # Calendar dates in India; due date is inclusive, ending at midnight IST.
    day = datetime.fromisoformat(occurred_at).astimezone(IST).date() + timedelta(days=rule['days'])
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), IST)
    case['deadlines'].append({'id':uuid.uuid4().hex,'trigger':trigger,'trigger_event_id':event_id,
        'type':rule['type'],'label':rule['label'],'due_date':day.isoformat(),'expires_at':end.isoformat(),
        'status':'open','next_action':rule['action'],'regulatory':rule['regulatory'],'simulated':simulated,
        'source':RULES['sources']['scores'] if rule['regulatory'] else None})

def refresh(case):
    case['route'] = route(case)
    case['missing_fields'] = missing(case['facts'])
    if case['status'] in ('collecting_information','ready_for_review','ready_to_submit'):
        case['status'] = 'ready_to_submit' if case['facts_confirmed'] else ('collecting_information' if case['missing_fields'] else 'ready_for_review')
    return case

def reminders(case, at=None):
    if case['status'] == 'resolved':
        return False
    at = at or datetime.now(timezone.utc)
    changed = False
    for d in case['deadlines']:
        if d['status'] != 'open':
            continue
        expires = datetime.fromisoformat(d['expires_at'])
        remaining = (expires - at).total_seconds()
        phase = 'overdue' if remaining <= 0 else 'soon' if remaining <= 3*86400 else None
        key = f"{d['id']}:{phase}"
        if phase and not any(n['key'] == key for n in case['notifications']):
            case['notifications'].append({'key':key,'created_at':now(),'read':False,'channel':case['preferred_channel'],
                'text':f"{'Demo: ' if d['simulated'] else ''}{d['label']} {'has passed' if phase == 'overdue' else 'is approaching'}. {d['next_action']}"})
            changed = True
    return changed

def next_escalation(case):
    f = case['filings'][-1] if case['filings'] else None
    if not f:
        return None
    if f['portal'] == 'entity':
        return {'portal':'SCORES','title':'Prepare a SCORES complaint','available':True,'url':RULES['sources']['scores']}
    for d in reversed(case['deadlines']):
        if d['type'] in ('review_1','review_2') and d['status'] == 'open':
            open_window = datetime.now(timezone.utc) < datetime.fromisoformat(d['expires_at'])
            return {'portal':d['type'],'title':d['label'],'available':open_window,'url':RULES['sources']['scores'], 'reason':None if open_window else 'Recorded review window has passed. Check the official portal for available options.'}
    if f['portal'] in ('SCORES','review_1','review_2'):
        return {'portal':'ODR','title':'Explore SMART ODR eligibility','available':False,'url':RULES['sources']['odr'],'reason':'Check dispute eligibility, applicable fees and the official process. No automatic filing.'}
    return None
