export type Point = {lat:number;lng:number};
export type Evidence = {url:string|null;title:string|null;engine:string|null;retrieved_at:string;note:string|null;kind:string};
export type Activity = {id:string;type:string;name:string;day:string;planned_start:string;planned_end:string;status:string;explanation:string|null;place:{location:Point|null;name:string}|null;sources:Evidence[]};
export type Route = {label:string;total_distance_km:number;total_duration_min:number;legs:{navigation_url:string|null;steps:{gps_coordinates:Point|null}[]}[]};
export type Plan = {version:number;status:string;days:{day:string;activities:Activity[]}[];route:Route|null;route_alternatives:Route[];issues:{code:string;severity:string;message:string}[];excluded:{name:string;reason:string}[];notes:string[];budget:{total_inr:number;per_person_inr:number;lines:{category:string;amount_inr:number;basis:string}[]}|null;weather:{day:string;summary:string|null}[];advisories:{text:string;url:string|null}[]};
export async function api<T>(path:string, method='GET', body?:unknown):Promise<T> {
  const response = await fetch('/api'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  const data = await response.json();
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||'Request failed'));
  return data;
}
