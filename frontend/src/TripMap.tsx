import {useEffect,useRef} from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type {Activity,Plan} from './types';

export default function TripMap({plan,onSelect}:{plan:Plan;onSelect:(id:string)=>void}){
  const host=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!host.current)return;
    const map=L.map(host.current,{zoomAnimation:false,fadeAnimation:false,markerZoomAnimation:false}).setView([10.58,77.1],9);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',maxZoom:18}).addTo(map);
    const points:L.LatLngTuple[]=[];
    for(const leg of plan.route?.legs||[]){
      for(const s of leg.steps)if(s.gps_coordinates)points.push([s.gps_coordinates.lat,s.gps_coordinates.lng]);
    }
    if(points.length>1)L.polyline(points,{color:'#3f5a3c',weight:3.5,dashArray:'7 7',className:'animated-route'}).addTo(map);
    const seen=new Set<string>();
    for(const a of plan.days.flatMap(d=>d.activities).filter((a:Activity)=>a.place?.location)){
      if(seen.has(a.place!.name))continue;seen.add(a.place!.name);
      const p=a.place!.location!;
      const label=document.createElement('span');label.textContent=a.name;
      L.circleMarker([p.lat,p.lng],{radius:7,color:'#253a2b',fillColor:'#e4a450',fillOpacity:1}).bindTooltip(label).on('click',()=>onSelect(a.id)).addTo(map);
      points.push([p.lat,p.lng]);
    }
    if(points.length)map.fitBounds(L.latLngBounds(points),{padding:[25,25],animate:false});
    let disposed=false;
    const resize=new ResizeObserver(()=>{if(!disposed)map.invalidateSize({animate:false,pan:false});});resize.observe(host.current);
    return()=>{disposed=true;resize.disconnect();map.stop();map.remove();};
  },[plan,onSelect]);
  return <div ref={host} className="trip-map" role="region" aria-label="Trip map. Dashed line joins route waypoints; it is not a road-accurate navigation route."/>;
}
