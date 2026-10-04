import {useState} from 'react';
import type {FormEvent} from 'react';

export default function TripForm({busy,onPlan}:{busy:boolean;onPlan:(request:unknown)=>void}){
  const [must,setMust]=useState('Tea Museum, Mattupetty Dam');
  function submit(e:FormEvent<HTMLFormElement>){
    e.preventDefault();const form=new FormData(e.currentTarget);const text=(key:string)=>String(form.get(key)||'');const num=(key:string)=>Number(form.get(key));
    onPlan({origin:text('origin'),destinations:[text('destination')],start_date:text('start'),return_date:text('return'),departure_time:text('depart'),return_deadline:text('deadline'),timezone:'Asia/Kolkata',transport_mode:text('mode'),group:{adults:num('people'),group_type:'friends'},vehicles:[{mode:text('mode'),count:num('vehicles'),mileage_km_per_litre:num('mileage'),tank_litres:num('tank')}],budget:{per_person_inr:num('budget')},road:{avoid_night_riding:form.has('daylight'),max_daily_drive_minutes:num('limit')*60,break_every_minutes:120},food:{vegetarian:form.has('veg')},must_visit:must.split(',').map(s=>s.trim()).filter(Boolean),pace:text('pace')});
  }
  return <form onSubmit={submit} className="planner-form">
    <div className="section-heading"><span className="eyebrow">01 / YOUR TRIP</span><h2>Start with the essentials.</h2><p>Trip duration includes the journey out and back. All times are India Standard Time.</p></div>
    <div className="fields">
      <label>Starting point<input name="origin" required defaultValue="Coimbatore" maxLength={120}/></label>
      <label>Destination<input name="destination" required defaultValue="Munnar" maxLength={120}/></label>
      <label>Departure date<input type="date" name="start" required defaultValue="2026-10-10"/></label>
      <label>Return date<input type="date" name="return" required defaultValue="2026-10-11"/></label>
      <label>Leave at<input type="time" name="depart" required defaultValue="06:00"/></label>
      <label>Be home by<input type="time" name="deadline" required defaultValue="18:30"/></label>
      <label>Travel mode<select name="mode" defaultValue="motorcycle"><option value="motorcycle">Motorcycle</option><option value="car">Car</option></select></label>
      <label>Adults<input name="people" type="number" required min={1} max={40} defaultValue={6}/></label>
      <label>Vehicles<input name="vehicles" type="number" required min={1} max={20} defaultValue={3}/></label>
      <label>Budget / person (₹)<input name="budget" type="number" required min={1} defaultValue={5000}/></label>
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
