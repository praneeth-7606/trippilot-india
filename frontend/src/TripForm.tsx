import {useState} from 'react';
import type {FormEvent} from 'react';

export default function TripForm({busy,onPlan,onIntake,clarifications}:{busy:boolean;onPlan:(request:unknown)=>void;onIntake:(message:string)=>void;clarifications:string[]}){
  const [must,setMust]=useState('Tea Museum, Mattupetty Dam');
  const [description,setDescription]=useState('');
  function submit(e:FormEvent<HTMLFormElement>){
    e.preventDefault();const form=new FormData(e.currentTarget);const text=(key:string)=>String(form.get(key)||'');const num=(key:string)=>Number(form.get(key));const optionalNum=(key:string)=>{const value=text(key);return value===''?undefined:Number(value)};
    onPlan({origin:text('origin'),destinations:text('destination').split(',').map(s=>s.trim()).filter(Boolean),start_date:text('start'),return_date:text('return'),departure_time:text('depart'),return_deadline:text('deadline'),timezone:'Asia/Kolkata',transport_mode:text('mode'),group:{adults:num('people'),group_type:'friends'},vehicles:[{mode:text('mode'),count:num('vehicles'),mileage_km_per_litre:num('mileage'),tank_litres:num('tank')}],budget:{per_person_inr:num('budget'),tolls_inr:optionalNum('tolls'),activities_inr:optionalNum('tickets'),local_transport_inr:optionalNum('local')},accommodation:{rooms:num('rooms'),budget_per_night_inr:optionalNum('stay')},road:{avoid_night_riding:form.has('daylight'),max_daily_drive_minutes:num('limit')*60,break_every_minutes:120},food:{vegetarian:form.has('veg')},must_visit:must.split(',').map(s=>s.trim()).filter(Boolean),pace:text('pace')});
  }
  return <form onSubmit={submit} className="planner-form" aria-label="Trip planner">
    <div className="section-heading"><span className="eyebrow pill">01 / YOUR TRIP</span><h2>Start with the essentials.</h2><p>Trip duration includes the journey out and back. All times are India Standard Time.</p></div>
    <div className="copilot"><div className="copilot-head"><span className="copilot-badge">TRIP COPILOT</span><span>Natural language → structured draft</span></div><label>Describe your road trip<textarea value={description} onChange={e=>setDescription(e.target.value)} minLength={10} maxLength={4000} placeholder="Six friends on three bikes from Coimbatore to Munnar, October 10–11, back by 6:30 PM…"/></label><button type="button" className="pill-btn" disabled={busy||description.trim().length<10} onClick={()=>onIntake(description)}>{busy?'Checking details…':'Use Trip Copilot'}</button><small>Mistral extracts a draft and asks only for missing details. It cannot invent routes, costs or bookings.</small>{clarifications.length>0&&<div className="clarifications" role="status"><strong>Before planning:</strong>{clarifications.map((item,index)=><p key={index}>{item}</p>)}</div>}</div>
    <div className="form-divider" aria-hidden="true"><span>or fill the form</span></div>
    <div className="fields">
      <label>Starting point<input name="origin" required defaultValue="Coimbatore" maxLength={120}/></label>
      <label>Destination(s), up to 4 in visit order<input name="destination" required defaultValue="Munnar" maxLength={240} placeholder="Munnar, Thekkady"/></label>
      <label>Departure date<input type="date" name="start" required defaultValue="2026-10-10"/></label>
      <label>Return date<input type="date" name="return" required defaultValue="2026-10-11"/></label>
      <label>Leave at<input type="time" name="depart" required defaultValue="06:00"/></label>
      <label>Be home by<input type="time" name="deadline" required defaultValue="18:30"/></label>
      <label>Travel mode<select name="mode" defaultValue="motorcycle"><option value="motorcycle">Motorcycle</option><option value="car">Car</option></select></label>
      <label>Adults<input name="people" type="number" required min={1} max={40} defaultValue={6}/></label>
      <label>Vehicles<input name="vehicles" type="number" required min={1} max={20} defaultValue={3}/></label>
      <label>Budget / person (₹)<input name="budget" type="number" required min={1} defaultValue={5000}/></label>
      <label>Rooms<input name="rooms" type="number" required min={1} max={20} defaultValue={2}/></label>
      <label>Stay / room / night (₹)<input name="stay" type="number" min={0} placeholder="Estimate"/></label>
      <label>Tolls, group (₹)<input name="tolls" type="number" min={0} placeholder="Estimate"/></label>
      <label>Tickets, group (₹)<input name="tickets" type="number" min={0} placeholder="Estimate"/></label>
      <label>Local travel, group (₹)<input name="local" type="number" min={0} placeholder="Estimate"/></label>
      <label>Vehicle mileage (km/L)<input name="mileage" type="number" required min={1} defaultValue={40}/></label>
      <label>Tank capacity (litres)<input name="tank" type="number" required min={1} defaultValue={12}/></label>
      <label>Max driving / day (hours)<input name="limit" type="number" required min={1} max={15} defaultValue={7}/></label>
      <label>Travel pace<select name="pace" defaultValue="balanced"><option>relaxed</option><option>balanced</option><option>packed</option></select></label>
      <label className="wide">Must-visit places<input value={must} onChange={e=>setMust(e.target.value)} placeholder="Separate places with commas" maxLength={500}/></label>
    </div>
    <div className="checks"><label><input name="daylight" type="checkbox" defaultChecked/> Avoid driving after 6:30 PM</label><label><input name="veg" type="checkbox" defaultChecked/> Vegetarian food</label></div>
    <button className="primary" disabled={busy}>{busy?'Building your itinerary…':'Build my road trip →'}</button>
  </form>;
}
