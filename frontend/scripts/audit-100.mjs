import {request} from 'playwright';
import assert from 'node:assert/strict';

const baseUrl=process.env.AUDIT_API_URL||'http://127.0.0.1:8001';
const client=await request.newContext({baseURL:baseUrl,extraHTTPHeaders:{'content-type':'application/json'}});
const results=[];
const baseTrip={origin:'Coimbatore',destinations:['Munnar'],start_date:'2026-11-10',return_date:'2026-11-11',departure_time:'06:00',return_deadline:'18:30',timezone:'Asia/Kolkata',transport_mode:'motorcycle',group:{adults:6,group_type:'friends'},vehicles:[{mode:'motorcycle',count:3,mileage_km_per_litre:40,tank_litres:12}],budget:{per_person_inr:5000},accommodation:{rooms:2,budget_per_night_inr:2000},road:{avoid_night_riding:true,max_daily_drive_minutes:420,break_every_minutes:120},food:{vegetarian:true},must_visit:[],pace:'balanced'};

async function check(name,fn){
  try{const detail=await fn();results.push({name,status:'PASS',detail:detail||''});}
  catch(error){results.push({name,status:'FAIL',detail:String(error.message||error).slice(0,220)});}
}
async function createTrip(trip=baseTrip){
  const response=await client.post('/trips',{data:trip});
  assert.equal(response.status(),201,`create status ${response.status()}`);
  return (await response.json()).id;
}
async function planTrip(trip=baseTrip){
  const id=await createTrip(trip);
  const response=await client.post(`/trips/${id}/plan`);
  assert.equal(response.status(),200,`plan status ${response.status()}`);
  return {id,body:await response.json()};
}
async function expectValidation(name,mutate){
  await check(name,async()=>{
    const trip=structuredClone(baseTrip);mutate(trip);
    const response=await client.post('/trips',{data:trip});
    assert.equal(response.status(),422,`expected 422, received ${response.status()}`);
  });
}

// 1–20: valid fixture-backed plans across mode, party, date, pace, budget, and safety constraints.
for(let i=0;i<20;i++){
  const trip=structuredClone(baseTrip);
  trip.transport_mode=i%2?'car':'motorcycle';
  trip.vehicles=[{mode:trip.transport_mode,count:1+(i%5),mileage_km_per_litre:i%2?12:35,tank_litres:i%2?45:14}];
  trip.group={adults:1+(i%12),children:i%4,elderly:i%3,group_type:['friends','family','mixed','solo'][i%4]};
  trip.start_date=`2026-11-${String(1+i).padStart(2,'0')}`;
  trip.return_date=`2026-11-${String(1+i+(i%4)).padStart(2,'0')}`;
  trip.departure_time=`${String(5+(i%4)).padStart(2,'0')}:${i%2?'30':'00'}`;
  trip.return_deadline=`${String(16+(i%4)).padStart(2,'0')}:30`;
  trip.road={avoid_night_riding:i%2===0,max_daily_drive_minutes:360+(i%5)*60,break_every_minutes:60+(i%4)*30};
  trip.food={vegetarian:i%2===0,vegan:i%5===0};
  trip.budget={per_person_inr:3000+i*250,tolls_inr:i*50,activities_inr:i*100,local_transport_inr:i*75};
  trip.accommodation={rooms:1+(i%4),budget_per_night_inr:1500+i*100};
  trip.pace=['relaxed','balanced','packed'][i%3];
  await check(`VALID-${String(i+1).padStart(2,'0')} ${trip.transport_mode} party=${trip.group.adults} date-offset=${i}`,async()=>{
    const {body}=await planTrip(trip);const version=body.version;
    assert(version&&['ready','partial'].includes(version.status),`unexpected plan status ${version?.status}`);
    assert(version.route?.total_distance_km>0,'missing route distance');
    assert(version.days.length>=1,'missing scheduled days');
    assert(body.search_budget_used>=0,'missing search budget usage');
    const issueCodes=[...new Set(version.issues.map(issue=>issue.code))].sort();
    return `${version.status}; ${version.days.length} day(s); ${issueCodes.join(',')||'no issues'}`;
  });
}

// 21–45: invalid request boundaries. These intentionally catch validation gaps.
const invalid=[
  ['missing origin',t=>delete t.origin],['missing group',t=>delete t.group],['empty destinations',t=>t.destinations=[]],
  ['five destinations over the four-stop limit',t=>t.destinations=['Munnar','Thekkady','Kochi','Madurai','Ooty']],['return before start',t=>t.return_date='2026-11-09'],
  ['trip longer than 16 days',t=>t.return_date='2026-11-27'],['unsupported timezone',t=>t.timezone='UTC'],
  ['train unsupported in current Phase 1',t=>t.transport_mode='train'],['flight unsupported in current Phase 1',t=>t.transport_mode='flight'],
  ['zero adults',t=>t.group.adults=0],['over maximum adults',t=>t.group.adults=41],['negative children',t=>t.group.children=-1],
  ['zero vehicles',t=>t.vehicles[0].count=0],['over maximum vehicles',t=>t.vehicles[0].count=21],
  ['zero mileage',t=>t.vehicles[0].mileage_km_per_litre=0],['reserve fraction at forbidden boundary',t=>t.vehicles[0].reserve_fraction=.5],
  ['daily drive below minimum',t=>t.road.max_daily_drive_minutes=29],['daily drive above maximum',t=>t.road.max_daily_drive_minutes=901],
  ['break interval below minimum',t=>t.road.break_every_minutes=29],['break interval above maximum',t=>t.road.break_every_minutes=241],
  ['negative budget',t=>t.budget.per_person_inr=-1],['invalid pace enum',t=>t.pace='extreme'],
  ['malformed start date',t=>t.start_date='not-a-date'],['empty origin',t=>t.origin=''],['blank destination',t=>t.destinations=['   ']],
];
for(const [name,mutate] of invalid)await expectValidation(`VALIDATION ${name}`,mutate);

// 46–60: edit, delay, version, and share behaviors.
for(let i=0;i<15;i++)await check(`STATE-${String(i+1).padStart(2,'0')} edit/replan/share sequence`,async()=>{
  const {id,body}=await planTrip();const first=body.version;
  const activity=first.days.flatMap(day=>day.activities).find(item=>item.type!=='drive');
  assert(activity,'fixture did not provide an editable activity');
  const mode=i%5;
  if(mode===0){
    let r=await client.patch(`/trips/${id}/activities/${activity.id}`,{data:{status:'locked'}});assert.equal(r.status(),200);
    r=await client.patch(`/trips/${id}/activities/${activity.id}`,{data:{status:'planned'}});assert.equal(r.status(),200);
  }else if(mode===1){
    let r=await client.patch(`/trips/${id}/activities/${activity.id}`,{data:{status:'skipped'}});assert.equal(r.status(),200);
    r=await client.patch(`/trips/${id}/activities/${activity.id}`,{data:{status:'planned'}});assert.equal(r.status(),200);
  }else if(mode===2){
    const r=await client.post(`/trips/${id}/replan`,{data:{delay_minutes:i*10}});assert.equal(r.status(),200);assert.equal((await r.json()).version.version,2);
  }else if(mode===3){
    const r=await client.post(`/trips/${id}/replan`,{data:{delay_minutes:15,from_activity_id:activity.id}});assert.equal(r.status(),200);
  }else{
    const r=await client.post(`/trips/${id}/share`);assert.equal(r.status(),200);const shared=await r.json();
    const read=await client.get(shared.share_url);assert.equal(read.status(),200);const payload=await read.json();
    assert.equal(payload.read_only,true);assert.equal('id' in payload,false);assert(payload.current);
  }
  const stored=await (await client.get(`/trips/${id}`)).json();
  assert(stored.versions.length>=(mode===4?1:2),'new version was not stored');
  assert.equal(stored.versions.at(-1),stored.versions.length,'version sequence has a gap/duplicate');
  return `${stored.versions.length} sequential version(s)`;
});

// 61–75: simultaneous plan completion; assert no duplicate version numbers.
for(let i=0;i<15;i++)await check(`CONCURRENCY-${String(i+1).padStart(2,'0')} simultaneous plans`,async()=>{
  const id=await createTrip();const count=2+(i%6);
  const responses=await Promise.all(Array.from({length:count},()=>client.post(`/trips/${id}/plan`)));
  for(const response of responses)assert.equal(response.status(),200);
  const stored=await (await client.get(`/trips/${id}`)).json();
  assert.deepEqual(stored.versions,[...Array(count)].map((_,index)=>index+1),'duplicate or missing plan versions');
  return `${count} unique versions`;
});

// 76–90: error/status boundaries and unactionable states.
const boundaryCases=[
  ['unknown trip GET',()=>client.get('/trips/no-such-trip'),404],
  ['unknown trip plan',()=>client.post('/trips/no-such-trip/plan'),404],
  ['unknown trip PATCH',()=>client.patch('/trips/no-such-trip/activities/x',{data:{status:'locked'}}),404],
  ['unknown activity after plan',async()=>{const {id}=await planTrip();return client.patch(`/trips/${id}/activities/no-such-activity`,{data:{status:'locked'}})},404],
  ['edit before first plan',async()=>{const id=await createTrip();return client.patch(`/trips/${id}/activities/x`,{data:{status:'locked'}})},409],
  ['replan unknown trip',()=>client.post('/trips/no-such-trip/replan',{data:{delay_minutes:10}}),404],
  ['replan before first plan',async()=>{const id=await createTrip();return client.post(`/trips/${id}/replan`,{data:{delay_minutes:10}})},409],
  ['negative delay rejected',async()=>{const {id}=await planTrip();return client.post(`/trips/${id}/replan`,{data:{delay_minutes:-1}})},422],
  ['delay over one day rejected',async()=>{const {id}=await planTrip();return client.post(`/trips/${id}/replan`,{data:{delay_minutes:1441}})},422],
  ['zero delay creates new version',async()=>{const {id}=await planTrip();return client.post(`/trips/${id}/replan`,{data:{delay_minutes:0}})},200],
  ['invalid activity status rejected',async()=>{const {id,body}=await planTrip();const a=body.version.days[0].activities[0];return client.patch(`/trips/${id}/activities/${a.id}`,{data:{status:'teleport'}})},422],
  ['unknown trip events',()=>client.get('/trips/no-such-trip/events'),404],
  ['unknown share token',()=>client.get('/trips/shared/not-a-token'),404],
  ['sharing before plan is rejected with 409',async()=>{const id=await createTrip();return client.post(`/trips/${id}/share`)},409],
  ['unsupported method',()=>client.put('/health'),405],
];
for(const [index,[name,call,expected]] of boundaryCases.entries())await check(`BOUNDARY-${String(index+1).padStart(2,'0')} ${name}`,async()=>{
  const response=await call();assert.equal(response.status(),expected,`received ${response.status()}, expected ${expected}`);
});

// 91–100: city pairs spanning regions; fixture mode must fail explicitly, not fabricate a route.
const geo=[['Srinagar','Jammu'],['Leh','Manali'],['Delhi','Agra'],['Jaipur','Delhi'],['Ahmedabad','Udaipur'],['Mumbai','Pune'],['Goa','Mangaluru'],['Bengaluru','Mysuru'],['Chennai','Bengaluru'],['Kolkata','Digha']];
for(const [origin,destination] of geo)await check(`GEO ${origin} to ${destination}: fixture miss is explicit`,async()=>{
  const trip=structuredClone(baseTrip);trip.origin=origin;trip.destinations=[destination];
  const {body}=await planTrip(trip);
  assert.equal(body.version.status,'failed','non-fixture geography was falsely represented as a successful live route');
  assert(body.version.issues.some(issue=>issue.code==='provider_unavailable'),'missing explicit provider-unavailable issue');
  return 'correctly reports no fixture; live-provider coverage not implied';
});

const counts=Object.fromEntries(['PASS','FAIL'].map(status=>[status,results.filter(item=>item.status===status).length]));
const report={mode:'fixture-backed Playwright API audit; no SerpApi/Mistral requests',baseUrl,total:results.length,counts,results};
const reportPath=process.env.AUDIT_REPORT_PATH;
if(reportPath){const {writeFile}=await import('node:fs/promises');await writeFile(reportPath,JSON.stringify(report,null,2));}
console.log(JSON.stringify({...report,results:undefined,failures:results.filter(item=>item.status==='FAIL')},null,2));
await client.dispose();
if(results.length!==100||counts.FAIL)process.exitCode=1;
