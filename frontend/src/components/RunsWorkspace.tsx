import { useEffect, useRef, useState, type ReactNode } from 'react';
import { MapContainer, Marker, Popup } from 'react-leaflet';
import { divIcon } from 'leaflet';
import type { TruckProfile, Load, Chain, CashflowCheck } from '../types';
import { RouteMap } from './RouteMap';
import { MapTiles } from './MapTiles';
import { AdvanceOffer } from './AdvanceOffer';
import { CapitalOneMark } from './CapitalOneMark';
import { RunTimeline } from './RunTimeline';
const money = (n: number) => n.toLocaleString('en-US', {style:'currency',currency:'USD'});
export function RunsWorkspace({profile, loads, chains, selected, cash, busy, planned, includeBoard, boardCount, offerCount, onBoard, onPlan, onSelect, onAdvance, children}: {
  profile?: TruckProfile; loads: Load[]; chains: Chain[]; selected: number; cash?: CashflowCheck; busy: boolean; planned: boolean;
  includeBoard: boolean; boardCount: number; offerCount: number; onBoard:(value:boolean)=>void; onPlan:()=>void; onSelect:(index:number)=>void; onAdvance:(id:string)=>void; children:ReactNode;
}) {
  const [cashDetails,setCashDetails] = useState(false);
  const [offline,setOffline] = useState(!navigator.onLine);
  const [expanded,setExpanded] = useState(false);
  const [mobile,setMobile] = useState(()=>matchMedia('(max-width:700px)').matches);
  const dialog = useRef<HTMLDialogElement>(null);
  const expand = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef<HTMLElement|null>(null);
  const chain = chains[selected];
  useEffect(()=>setCashDetails(false),[mobile,expanded]);
  useEffect(()=>{const q=matchMedia('(max-width:700px)');const change=()=>{setMobile(q.matches);if(!q.matches)setExpanded(false);};q.addEventListener('change',change);return()=>q.removeEventListener('change',change);},[]);
  useEffect(()=>{if(expanded&&mobile&&!dialog.current?.open){returnFocus.current=document.activeElement as HTMLElement;dialog.current?.showModal();}else if(!expanded&&dialog.current?.open){dialog.current.close();(returnFocus.current?.isConnected?returnFocus.current:expand.current)?.focus();}},[expanded,mobile]);
  const content = <>
    <p className="eyebrow">{profile?.current_location.city || 'Current location'}</p>
    <h1>{chain ? 'Good miles. All the way home.' : 'Find a run worth taking.'}</h1>
    <p className="workspace-muted">{chain ? 'Your next moves, and whether your balance can handle them.' : `${boardCount} simulated loads · ${offerCount} confirmed offers`}</p>
    {!chain && <><label className="checkbox"><input type="checkbox" checked={includeBoard} disabled={busy} onChange={e=>onBoard(e.target.checked)}/>Include simulated load board</label><button className="primary workspace-full" disabled={busy||!profile||(!includeBoard&&!offerCount)} onClick={onPlan}>Plan run</button>{planned&&<p role="status">No matching runs. Include the board or adjust truck settings.</p>}</>}
    {chain && <>
      <div className="workspace-runs" role="group" aria-label="Select a run">{chains.map((c,i)=><button key={c.loads.join()} disabled={busy} aria-pressed={i===selected} onClick={()=>onSelect(i)}><span>{i===0?'Best net':`Run ${i+1}`}</span><strong>{money(c.total_net_profit)}</strong></button>)}</div>
      <section className="workspace-profit"><span>Net profit</span><strong>{money(chain.total_net_profit)}</strong><p>{chain.days.toFixed(1)} days · {chain.total_miles.toFixed(0)} miles · {money(chain.net_per_day)}/day</p></section>
      {chain.losing && <p className="notice">{chain.losing_reason || 'This run does not earn a profit.'}</p>}
      <section className={`workspace-funding ${cash?.shortfall?'shortfall':'covered'}`} aria-live="polite"><h2>{cash ? cash.shortfall?'! Cash shortfall':'✓ Run covered':'Cash flow'}</h2>{cash ? <><strong>{money(cash.lowest_balance)}</strong><p>Lowest projected balance · {cash.lowest_balance_date}</p><CapitalOneMark label="Balance and bills from" /></>:<p>Waiting for cash-flow data. Use Refresh cash flow below to retry.</p>}</section>
      <AdvanceOffer key={chain.loads.join()} cash={cash} busy={busy} onAdvance={onAdvance}/>
      <h2>Route</h2><ol className="workspace-stops">{chain.loads.map(id=>{const load=loads.find(l=>l.id===id);return <li key={id}><strong>{load?`${load.origin.city} to ${load.destination.city}`:id}</strong><small>{load?.broker || id}</small></li>;})}</ol>
      <details><summary>Schedule and assumptions</summary><RunTimeline chain={chain} route={cash?.route}/>{chain.feasible_notes.map((note,i)=><p key={i}>{note}</p>)}<p>Estimated connections, not road directions. Simplified hours of service.</p></details>
      <details onToggle={e=>setCashDetails(e.currentTarget.open)}><summary>Cash-flow chart and events</summary>{cashDetails && children}</details>
      <button className="text-button workspace-full" disabled={busy} onClick={onPlan}>Replan run</button>
    </>}
    <p className="workspace-disclosure">Simulated load board · <CapitalOneMark label="bank data by" /> Nessie sandbox</p>
  </>;
  const loc=profile?.current_location;
  return <section className="runs-workspace" aria-label="Runs workspace" aria-busy={busy}>
    <div className="workspace-map">{chain&&profile ? <RouteMap chain={chain} loads={loads} profile={profile} cash={cash}/> : loc?.lat!=null&&loc.lng!=null ? <><MapContainer center={[loc.lat,loc.lng]} zoom={8} scrollWheelZoom={false} zoomAnimation={false} fadeAnimation={false}><MapTiles offline={offline} onOffline={()=>setOffline(true)}/><Marker position={[loc.lat,loc.lng]} icon={divIcon({className:'workspace-home',html:'<span>H</span>',iconSize:[44,44]})}><Popup>{loc.city}</Popup></Marker></MapContainer>{offline&&<p className="workspace-offline">Offline map · {loc.city}</p>}</> : <p className="workspace-offline">Save a city in Truck settings to place it on the map.</p>}</div>
    {!mobile&&<div className="workspace-panel">{content}</div>}
    {mobile&&<div className="workspace-collapsed"><div><span>{chain?'Net profit': 'Starting from'}</span><h1>{chain?money(chain.total_net_profit):loc?.city||'LoadCheck'}</h1><p>{chain?`${chain.days.toFixed(1)} days · ${cash?cash.shortfall?'Cash shortfall':'Run covered':'Cash flow loading'}`:`${boardCount} simulated loads available`}</p></div><button ref={expand} aria-haspopup="dialog" aria-expanded={expanded} onClick={()=>setExpanded(true)}>Expand</button>{!chain&&<button className="primary workspace-full" disabled={busy||!profile} onClick={()=>{onPlan();setExpanded(true);}}>Plan run</button>}</div>}
    <dialog ref={dialog} className="workspace-sheet" aria-label="Run details" onCancel={e=>{e.preventDefault();setExpanded(false);}}><button className="workspace-collapse" autoFocus onClick={()=>setExpanded(false)}>Collapse to map</button>{mobile && expanded ? content : null}</dialog>
  </section>;
}
