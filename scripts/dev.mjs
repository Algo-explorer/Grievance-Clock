// One-command local app: start/reuse the API, then start Next.js.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const win=process.platform==='win32';
const localPython=path.join(root,'.venv',win?'Scripts/python.exe':'bin/python');
let backend, frontend, stopping=false;
async function healthy(){try{const r=await fetch('http://127.0.0.1:8000/api/health',{signal:AbortSignal.timeout(1500)});return r.ok&&(await r.json()).service==='grievance-clock';}catch{return false;}}
function launch(exe,args){return spawn(exe,args,{cwd:root,stdio:'inherit',windowsHide:true});}
function stop(code=0){if(stopping)return;stopping=true;frontend?.kill();backend?.kill();process.exitCode=code;}
process.on('SIGINT',()=>stop());process.on('SIGTERM',()=>stop());
if(!await healthy()){
 if(!existsSync(localPython)){console.error('Backend environment is missing. Create .venv and install backend/requirements.lock.txt first.');process.exit(1);}
 backend=launch(localPython,['-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000']);
 backend.on('error',e=>{console.error('Backend could not start:',e.message);stop(1);});
 backend.on('exit',code=>{if(!stopping){console.error('Backend stopped. Check the error above.');stop(code||1);}});
 for(let i=0;i<40&&!await healthy()&&!stopping;i++)await new Promise(r=>setTimeout(r,500));
 if(!await healthy()){console.error('Backend did not become ready on port 8000.');stop(1);}
}else console.log('Using the existing Grievance Clock backend on port 8000.');
if(!stopping){
 frontend=launch(process.execPath,[path.join(root,'node_modules/next/dist/bin/next'),'dev','--webpack','--hostname','127.0.0.1',...process.argv.slice(2)]);
 frontend.on('error',e=>{console.error(e.message);stop(1);});frontend.on('exit',code=>stop(code||0));
}
