import { useEffect } from 'react';
import { TileLayer } from 'react-leaflet';

// Remove the entire tile layer after a failure, keeping route overlays usable.
export function MapTiles({ offline, onOffline }: { offline: boolean; onOffline: () => void }) {
  useEffect(() => {
    const disconnected = () => onOffline();
    window.addEventListener('offline', disconnected);
    if (!navigator.onLine) onOffline();
    return () => window.removeEventListener('offline', disconnected);
  }, [onOffline]);
  return offline ? null : <TileLayer
    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    eventHandlers={{ tileerror: onOffline }}
  />;
}
