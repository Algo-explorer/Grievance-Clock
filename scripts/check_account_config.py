"""Check service configuration without printing credentials or copying case data."""
from pathlib import Path
from dotenv import load_dotenv
import os
load_dotenv(Path(__file__).resolve().parents[1]/'.env.local')
required=['MONGODB_URI','NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY','CLERK_SECRET_KEY','CLERK_ISSUER_URL','DATA_ENCRYPTION_KEY']
missing=[key for key in required if not os.getenv(key)]
if missing:raise SystemExit('Missing settings: '+', '.join(missing))
from backend.authentication import issuer,key_client
from pymongo import MongoClient
from cryptography.fernet import Fernet
try:
    Fernet(os.environ['DATA_ENCRYPTION_KEY'])
    key_client(issuer()).get_jwk_set()
    with MongoClient(os.environ['MONGODB_URI'],serverSelectionTimeoutMS=5000) as client:
        client[os.getenv('MONGODB_DATABASE','grievance_clock')].command('ping')
except Exception as exc:
    raise SystemExit('Connection check failed ('+type(exc).__name__+'). Check provider settings and Atlas IP access; credentials were not displayed.') from None
print('Clerk signing keys and MongoDB connectivity verified. No case data was copied.')
