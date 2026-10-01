"""Synthetic-only live AI smoke check. Does not print credential or raw provider errors."""
from dotenv import load_dotenv
load_dotenv('.env.local')
from backend.intelligence import extract
from backend.models import Facts

case={'language':'hi','ai_consent':True,'facts':Facts().model_dump(mode='json')}
try:
    result,provider=extract(case,'This is a fictional test. Maine Telegram scam mein UPI se Rs 25000 bhej diye. Transaction reference TEST250001. Date 2026-09-29. Recipient demo@example.')
    assert result.facts.category=='cyber_fraud'
    assert result.facts.amount==25000
    assert result.facts.money_transferred is True
    print('Live structured extraction passed: category, amount and payment status. Provider: '+provider)
except Exception as exc:
    print('Live AI check failed: '+type(exc).__name__)
    code=getattr(exc,'status_code',None)
    if code: print('HTTP status: '+str(code))
    error_code=getattr(exc,'code',None)
    if error_code in ('insufficient_quota','rate_limit_exceeded','billing_hard_limit_reached'):
        print('Provider error code: '+error_code)
    raise SystemExit(1)
