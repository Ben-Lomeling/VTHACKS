import React from 'react';
import ReactDOM from 'react-dom/client';
import { MapsPreview } from './MapsPreview';
import 'leaflet/dist/leaflet.css';
import './preview.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><MapsPreview /></React.StrictMode>);
