'use client';
import {useCallback,useEffect,useRef,useState} from 'react';

// Playback belongs to the current case. Abort fetches and revoke private audio
// when the user stops, records, navigates away, or requests another message.
export function useReadAloud(caseId:string|null, language:string, onError:(message:string)=>void){
 const [speaking,setSpeaking]=useState<string|null>(null);
 const audio=useRef<HTMLAudioElement|null>(null),url=useRef<string|null>(null),request=useRef<AbortController|null>(null),version=useRef(0);
 const stop=useCallback(()=>{
  version.current++;request.current?.abort();request.current=null;
  audio.current?.pause();audio.current=null;
  if(url.current)URL.revokeObjectURL(url.current);url.current=null;
  window.speechSynthesis?.cancel();setSpeaking(null);
 },[]);
 useEffect(()=>{return stop;},[caseId,language,stop]);
 async function speak(text:string,id:string){
  if(speaking===id){stop();return;}
  stop();onError('');setSpeaking(id);const current=version.current;
  try{
   // Detect the actual script; English responses in Hindi chat need English voices.
   const hindi=/[\u0900-\u097f]/.test(text)&&language!=='mr';
   if(hindi){
    if(!caseId)throw Error('Open a case before listening.');
    const controller=new AbortController();request.current=controller;
    const timer=setTimeout(()=>controller.abort(),120000);
    let response:Response;
    try{response=await fetch(`/api/cases/${caseId}/speech`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text}),signal:controller.signal});}
    finally{clearTimeout(timer);}
    if(!response.ok){const problem=await response.json().catch(()=>({}));throw Error(problem.detail||'Hindi read-aloud is unavailable. Please try again.');}
    const blob=await response.blob();if(current!==version.current)return;
    url.current=URL.createObjectURL(blob);const player=new Audio(url.current);audio.current=player;
    player.onended=()=>{if(current===version.current)stop();};
    player.onerror=()=>{if(current===version.current){stop();onError('Audio playback failed. Please try again.');}};
    await player.play();
   }else{
    if(!window.speechSynthesis)throw Error('Read-aloud is unavailable in this browser.');
    const synth=window.speechSynthesis;
    let voices=synth.getVoices();
    if(!voices.length)voices=await new Promise<SpeechSynthesisVoice[]>(resolve=>{
     const done=()=>{clearTimeout(timer);synth.removeEventListener('voiceschanged',done);resolve(synth.getVoices());};
     const timer=setTimeout(done,1500);synth.addEventListener('voiceschanged',done);
    });
    if(current!==version.current)return;
    const lang=/[\u0980-\u09ff]/.test(text)?'bn':/[\u0b80-\u0bff]/.test(text)?'ta':/[\u0c00-\u0c7f]/.test(text)?'te':/[\u0900-\u097f]/.test(text)?'mr':'en';
    const voice=voices.find(v=>v.lang.toLowerCase()===`${lang}-in`)||voices.find(v=>v.lang.split(/[-_]/)[0]===lang);
    if(!voice)throw Error('No matching voice is installed for this language. Please use a browser with that voice available.');
    const message=new SpeechSynthesisUtterance(text);message.voice=voice;message.lang=voice.lang;message.rate=0.95;
    message.onend=()=>{if(current===version.current)stop();};
    message.onerror=e=>{if(current===version.current&&e.error!=='canceled'&&e.error!=='interrupted'){stop();onError('Read-aloud failed. Please try again.');}};
    synth.speak(message);
   }
  }catch(e){if(current!==version.current)return;stop();onError((e as Error).name==='AbortError'?'Audio preparation timed out. Please try again.':(e as Error).message);}
 }
 return {speak,stop,speaking};
}
