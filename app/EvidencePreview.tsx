'use client';
import {useState} from 'react';
type Evidence={id:string;name:string;mime?:string};
type Actions={onRemove?:(id:string)=>void;onReplace?:(id:string)=>void;busy?:boolean};
export default function EvidencePreview({caseId,evidence,...actions}:{caseId:string;evidence:Evidence[]}&Actions){
 return <div className="evidence-previews">{evidence.map(file=><Preview key={file.id} caseId={caseId} file={file} {...actions}/>)}</div>;
}
function Preview({caseId,file,onRemove,onReplace,busy}:{caseId:string;file:Evidence}&Actions){
 const [failed,setFailed]=useState(false);
 const url=`/api/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(file.id)}?preview=true`;
 const image=file.mime?.startsWith('image/')||/\.(png|jpe?g|webp)$/i.test(file.name);
 return <figure className="attachment-preview">{image&&!failed?<a href={url} target="_blank" rel="noreferrer"><img src={url} alt={`Uploaded evidence: ${file.name}`} loading="lazy" onError={()=>setFailed(true)}/></a>:<p>{failed?'Preview unavailable. Open the original below.':'Document attachment'}</p>}<figcaption><a href={url} target="_blank" rel="noreferrer">{file.name} · Open original</a></figcaption>{onRemove&&<div className="card-actions"><button type="button" className="text-button" disabled={busy} onClick={()=>onReplace?.(file.id)}>Replace</button><button type="button" className="text-button danger" disabled={busy} onClick={()=>onRemove(file.id)}>Remove</button></div>}</figure>;
}
