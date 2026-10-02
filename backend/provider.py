"""Bounded provider calls with safe diagnostics and a short failure cooldown."""
import time
from threading import Lock

_lock = Lock()
_until = 0.0
_issue = None

def classify(exc):
    status = getattr(exc, 'status_code', None)
    body = getattr(exc, 'body', {})
    nested = body.get('error', body) if isinstance(body, dict) else {}
    content = str(nested).lower()
    if status == 429 and any(w in content for w in ('quota', 'credit', 'billing', 'balance', 'spend')):
        return {'code':'quota','message':'Cloud AI is unavailable because the API project has a billing or quota restriction. Local intake is active.'}
    if status == 429:
        return {'code':'rate_limit','message':'Cloud AI is temporarily rate-limited. Local intake is active.'}
    if status in (401,403):
        return {'code':'credentials','message':'Cloud AI credentials or permissions need attention. Local intake is active.'}
    if status == 400:
        return {'code':'request','message':'Cloud AI rejected this request. Local intake is active.'}
    return {'code':'unavailable','message':'Cloud AI could not be reached. Local intake is active.'}

def problem():
    with _lock:
        return dict(_issue) if _issue and time.monotonic() < _until else None

def failed(exc):
    global _until, _issue
    issue = classify(exc)
    with _lock:
        _issue = issue
        _until = time.monotonic() + (300 if issue['code'] in ('quota','credentials') else 60)
    return issue

def reset():
    global _until, _issue
    with _lock:
        _until = 0.0
        _issue = None
