'use client';
import {useState} from 'react';
type Evidence={id:string;name:string;mime?:string};
export default function EvidencePreview({caseId,evidence}:{caseId:string;evidence:Evidence[]}){
 return <div className="evidence-previews">{evidence.map(file=><Preview key={file.id} caseId={caseId} file={file}/>)}</div>;
}
function Preview({caseId,file}:{caseId:string;file:Evidence}){
 const [failed,setFailed]=useState(false);
 const url=`/api/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(file.id)}?preview=true`;
 const image=file.mime?.startsWith('image/')||/\.(png|jpe?g|webp)$/i.test(file.name);
 return <figure className="attachment-preview">{image&&!failed?<a href={url} target="_blank" rel="noreferrer"><img src={url} alt={`Uploaded evidence: ${file.name}`} loading="lazy" onError={()=>setFailed(true)}/></a>:<p>{failed?'Preview unavailable. Open the original below.':'Document attachment'}</p>}<figcaption><a href={url} target="_blank" rel="noreferrer">{file.name} · Open original</a></figcaption></figure>;
}
