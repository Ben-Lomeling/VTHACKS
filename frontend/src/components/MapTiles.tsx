import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { TileLayer, useMap } from 'react-leaflet';

export function MapTiles({ offline: controlledOffline, onOffline }: { offline?: boolean; onOffline?: () => void } = {}) {
  const map = useMap();
  const [localOffline, setLocalOffline] = useState(!navigator.onLine);
  const offline = controlledOffline ?? localOffline;
  const setOffline = (value: boolean) => { setLocalOffline(value); if (value) onOffline?.(); };
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const disconnected = () => { setOffline(true); setLoading(false); };
    window.addEventListener('offline', disconnected);
    return () => window.removeEventListener('offline', disconnected);
  }, []);
  const retry = () => { setFailed(false); setLoading(true); setOffline(false); setAttempt(n => n + 1); };
  return <>
    {controlledOffline === undefined && createPortal(<div className="map-mode" onClick={e => e.stopPropagation()} onDoubleClick={e => e.stopPropagation()} onWheel={e => e.stopPropagation()}>
      <span role="status">{offline ? 'Offline map · estimates remain available' : failed ? 'Some map tiles unavailable' : loading ? 'Loading map…' : 'Map ready · estimated connections'}</span>
      {(offline || failed) && <button type="button" onClick={retry}>Retry map tiles</button>}
      {!offline && <button type="button" onClick={() => { setOffline(true); setLoading(false); }}>Use offline map</button>}
    </div>, map.getContainer().parentElement!)}
    {!offline && <TileLayer key={attempt}
      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      eventHandlers={{ loading: () => setLoading(true), load: () => setLoading(false), tileerror: () => setFailed(true) }}
    />}
  </>;
}
