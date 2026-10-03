"""Copy legacy local settings into service-specific ignored files, without printing secrets."""
from pathlib import Path
from dotenv import dotenv_values,set_key

root=Path(__file__).resolve().parents[1]
legacy=dotenv_values(root/'.env.local')
front_keys={'NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY','CLERK_SECRET_KEY','BACKEND_URL','AUTH_MODE','APP_ENV'}
for service in ('frontend','backend'):
    path=root/service/'.env.local'
    existing=dotenv_values(path)
    for name,value in legacy.items():
        wanted=name in front_keys if service=='frontend' else name not in {'NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY','CLERK_SECRET_KEY','BACKEND_URL'}
        if wanted and value is not None and not existing.get(name):set_key(str(path),name,value)
print('Service-specific local configuration prepared. Existing service values were preserved.')
