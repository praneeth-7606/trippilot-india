import {useState} from 'react';
import type {FormEvent} from 'react';
import {api} from './types';

type Msg = {role:'user'|'assistant';content:string};

export default function ChatPanel({onBuild}:{onBuild:(request:unknown)=>void}){
  const [messages,setMessages]=useState<Msg[]>([{role:'assistant',content:'Tell me your vacation idea — where from, which places do you want to cover, how many days and people? I will turn it into a routed plan with stays.'}]);
  const [input,setInput]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [draft,setDraft]=useState<Record<string,unknown>|null>(null),[notes,setNotes]=useState<string[]>([]);
  async function send(e:FormEvent){
    e.preventDefault();const text=input.trim();if(!text||busy)return;
    const next=[...messages,{role:'user',content:text} as Msg];
    setMessages(next);setInput('');setBusy(true);setError('');setDraft(null);
    try{
      const r=await api<{reply:string;request:unknown|null;clarifications:string[]}>('/trips/converse','POST',{messages:next});
      setMessages([...next,{role:'assistant',content:r.reply}]);
      setDraft((r.request as Record<string,unknown>|null)||null);setNotes(r.clarifications||[]);
    }catch(err){setError(err instanceof Error?err.message:'Request failed');}finally{setBusy(false);}
  }
  function build(){if(draft)onBuild(draft);}
  return <div className="chat-panel" aria-label="Vacation chat agent">
    <div className="section-heading"><span className="eyebrow pill">VACATION AGENT</span><h2>Describe the trip in words.</h2><p>Multi-stop holidays: the agent routes your cities in order and plans stays. It cannot invent prices or bookings.</p></div>
    <div className="chat-log" role="log" aria-live="polite">{messages.map((m,i)=><p key={i} className={'msg '+m.role}>{m.content}</p>)}{busy&&<p className="msg assistant thinking">Thinking…</p>}</div>
    {notes.length>0&&<div className="clarifications" role="status"><strong>Still needed:</strong>{notes.map((n,i)=><p key={i}>{n}</p>)}</div>}
    {error&&<div className="error" role="alert">{error}</div>}
    {draft&&<div className="draft-card"><strong>Draft ready — route and stays mapped.</strong><button className="primary" disabled={busy} onClick={build}>Build this trip →</button></div>}
    <form onSubmit={send} className="chat-input">
      <label>Message the agent<input aria-label="Message the agent" value={input} onChange={e=>setInput(e.target.value)} maxLength={4000} placeholder="Hyderabad family, cover Kerala and Tamil Nadu sights in 10 days…"/></label>
      <button className="pill-btn" disabled={busy||!input.trim()}>{busy?'Sending…':'Send'}</button>
    </form>
  </div>;
}
