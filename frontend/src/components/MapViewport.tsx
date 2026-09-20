import { useEffect, useRef } from 'react';
import { DomEvent, latLngBounds } from 'leaflet';
import { useMap } from 'react-leaflet';

// Shared by the starting map and route map. Keep this outside their render functions:
// remounting a fitting component would undo the driver's zoom on every data update.
export function MapViewport({ points, routeKey }: { points: [number, number][]; routeKey: string }) {
  const map = useMap();
  const latest = useRef(points);
  latest.current = points;
  const fitted = useRef('');
  const button = useRef<HTMLButtonElement>(null);
  const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fit = (animate = true) => {
    if (!latest.current.length) return;
    const box = map.getContainer().getBoundingClientRect();
    const workspace = map.getContainer().closest('.runs-workspace');
    let left = 24, top = 24, bottom = 24;
    workspace?.querySelectorAll('.workspace-panel, .workspace-collapsed, .workspace-map .map-mode, .workspace-map .map-legend, .workspace-map .map-notice').forEach(el => {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      if (el.matches('.workspace-panel')) left = Math.max(left, r.right - box.left + 20);
      else if (el.matches('.workspace-collapsed, .map-legend')) bottom = Math.max(bottom, box.bottom - r.top + 32);
      else top = Math.max(top, r.bottom - box.top + 32);
    });
    // Leave a usable fitting area even in short landscape windows.
    left = Math.min(left, box.width * .55);
    top = Math.min(top, box.height * .25);
    bottom = Math.min(bottom, box.height * .45);
    map.fitBounds(latLngBounds(latest.current), {
      paddingTopLeft: [left, top], paddingBottomRight: [110, bottom],
      maxZoom: 9, animate: animate && !reduced(),
    });
  };
  useEffect(() => {
    if (fitted.current === routeKey || !points.length) return;
    const frame = requestAnimationFrame(() => { fit(false); fitted.current = routeKey; });
    return () => cancelAnimationFrame(frame);
  }, [map, routeKey]);
  useEffect(() => {
    if (button.current) { DomEvent.disableClickPropagation(button.current); DomEvent.disableScrollPropagation(button.current); }
    const container = map.getContainer();
    const workspace = container.closest('.runs-workspace') as HTMLElement | null;
    let frame = 0;
    let width = container.clientWidth, height = container.clientHeight;
    const resize = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (width !== container.clientWidth || height !== container.clientHeight) {
          const center = map.getCenter(), zoom = map.getZoom();
          map.invalidateSize({ pan: false, animate: false });
          map.setView(center, zoom, { animate: false });
          width = container.clientWidth; height = container.clientHeight;
        }
        const summary = workspace?.querySelector('.workspace-collapsed')?.getBoundingClientRect();
        workspace?.style.setProperty('--summary-height', `${summary?.height || 0}px`);
        const disclosureHeight = document.querySelector('.runs-screen .demo-strip')?.getBoundingClientRect().height || 0;
        workspace?.style.setProperty('--disclosure-height', `${disclosureHeight}px`);
      });
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    const disclosure = document.querySelector(".runs-screen .demo-strip");
    if (disclosure) observer.observe(disclosure);
    workspace?.querySelectorAll('.workspace-panel, .workspace-collapsed').forEach(el => observer.observe(el));
    resize();
    return () => { observer.disconnect(); cancelAnimationFrame(frame); };
  }, [map]);
  return <button ref={button} className="map-fit" type="button" disabled={!points.length} onClick={() => fit()} aria-label="Fit route to map">Fit route</button>;
}

export const mapInteractionOptions = () => ({
  scrollWheelZoom: true, touchZoom: true, keyboard: true,
  zoomSnap: .25, zoomDelta: .5, wheelPxPerZoomLevel: 100,
  zoomAnimation: !matchMedia('(prefers-reduced-motion: reduce)').matches,
  markerZoomAnimation: !matchMedia('(prefers-reduced-motion: reduce)').matches,
});
