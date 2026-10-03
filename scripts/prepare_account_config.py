"""Add missing configuration slots and an encryption key without printing secrets."""
from dotenv import dotenv_values,set_key
from cryptography.fernet import Fernet
from pathlib import Path

root=Path(__file__).resolve().parents[1]
path=root/'.env.local'
config=dotenv_values(path)
for name,value in {'AUTH_MODE':'clerk','APP_ENV':'development','MONGODB_URI':'',
                   'MONGODB_DATABASE':'grievance_clock','NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY':'',
                   'CLERK_SECRET_KEY':'','CLERK_ISSUER_URL':''}.items():
    if name not in config:set_key(str(path),name,value)
if not config.get('DATA_ENCRYPTION_KEY'):
    old_key=root/'data'/'encryption.key'
    key=old_key.read_bytes() if old_key.exists() else Fernet.generate_key()
    Fernet(key)  # validate before saving
    set_key(str(path),'DATA_ENCRYPTION_KEY',key.decode())
print('Configuration slots prepared. Encryption key saved privately; keep a secure backup.')
