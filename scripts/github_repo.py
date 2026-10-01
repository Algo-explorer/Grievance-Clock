"""Create the requested public GitHub repository using existing Git Credential Manager auth.
Never writes or prints the credential. Run with --create only after code review.
"""
import json, os, subprocess, sys, urllib.request, urllib.error

def main():
    env={**os.environ,'GCM_INTERACTIVE':'never','GIT_TERMINAL_PROMPT':'0'}
    result=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',capture_output=True,text=True,env=env)
    fields=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    token=fields.get('password')
    if not token:
        print('GitHub authentication is unavailable. Sign in to GitHub through Git Credential Manager.'); return 2
    def api(path,body=None):
        req=urllib.request.Request('https://api.github.com'+path,data=json.dumps(body).encode() if body else None,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'GrievanceClock-Setup','Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
    try:
        user=api('/user')['login']; print('Authenticated GitHub account: '+user)
        if '--create' in sys.argv:
            repo=api('/user/repos',{'name':'grievance-clock','private':False,'description':'SANGYAN investor grievance assistant: multilingual intake, evidence, deterministic routing, assisted filing and event-driven deadlines.'})
            print('Repository: '+repo['html_url'])
    except urllib.error.HTTPError as e:
        print('GitHub API returned HTTP '+str(e.code)); return 3
    except urllib.error.URLError:
        print('GitHub network access failed.'); return 4
    return 0

if __name__=='__main__': sys.exit(main())
