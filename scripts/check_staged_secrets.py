"""Fail closed if staged paths or text look like local secrets / case data."""
import re, subprocess, sys
paths=subprocess.check_output(['git','diff','--cached','--name-only','-z']).decode().split('\0')
bad=[]
for path in filter(None,paths):
    if path.startswith(('data/','.venv/','output/','tmp/','node_modules/')) or (path.startswith('.env') and path!='.env.example'):
        bad.append(path);continue
    content=subprocess.check_output(['git','show',':'+path])
    if re.search(rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|sk_(?:test|live)_[A-Za-z0-9]{20,}|mongodb(?:\+srv)?://[^\s:/]+:[^\s@]{8,}@|gh[pousr]_[A-Za-z0-9]{25,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',content):
        bad.append(path)
if bad:
    print('Blocked staged files: '+', '.join(bad));sys.exit(1)
print('Staged source scan passed. No local secrets or case-storage paths detected.')
