import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';
import { MapPin, Navigation, Target } from 'lucide-react';

// Fix Leaflet default icon paths in React Vite
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
});

// Custom styled pin marker icon
const customMapPin = new L.DivIcon({
  className: 'custom-map-marker',
  html: `<div style="
    background: linear-gradient(135deg, #276221 0%, #327a2a 100%);
    width: 34px;
    height: 34px;
    border-radius: 50% 50% 50% 0;
    transform: rotate(-45deg);
    display: flex;
    align-items: center;
    justify-content: center;
    border: 3px solid #ffffff;
    box-shadow: 0 4px 14px rgba(39,98,33,0.4), 0 0 15px rgba(39,98,33,0.5);
  ">
    <div style="
      width: 12px;
      height: 12px;
      background: #ffffff;
      border-radius: 50%;
    "></div>
  </div>`,
  iconSize: [34, 34],
  iconAnchor: [17, 34],
});

interface LocationMapPickerProps {
  location: { latitude: number; longitude: number };
  onChange: (loc: { latitude: number; longitude: number }) => void;
  centerLat?: number;
  centerLng?: number;
  selectedCityName?: string;
}

// MapController component to handle map clicks & smooth city focus panning
function MapController({ 
  onChange, 
  centerLat, 
  centerLng 
}: { 
  onChange: (loc: { latitude: number; longitude: number }) => void;
  centerLat?: number;
  centerLng?: number;
}) {
  const map = useMap();

  useMapEvents({
    click(e) {
      onChange({
        latitude: parseFloat(e.latlng.lat.toFixed(6)),
        longitude: parseFloat(e.latlng.lng.toFixed(6)),
      });
    },
  });

  useEffect(() => {
    if (centerLat !== undefined && centerLng !== undefined && !isNaN(centerLat) && !isNaN(centerLng)) {
      // Invalidate container size to ensure clean Leaflet render
      map.invalidateSize();
      // Smoothly pan & zoom to city (Zoom 14 for detailed town view)
      map.setView([centerLat, centerLng], 14, {
        animate: true
      });
    }
  }, [centerLat, centerLng, map]);

  return null;
}

export const LocationMapPicker: React.FC<LocationMapPickerProps> = ({
  location,
  onChange,
  centerLat,
  centerLng,
  selectedCityName
}) => {
  const targetLat = centerLat !== undefined ? centerLat : location.latitude || 6.7730;
  const targetLng = centerLng !== undefined ? centerLng : location.longitude || 79.8816;
  const position: [number, number] = [location.latitude || targetLat, location.longitude || targetLng];

  const markerHandlers = useMemo(
    () => ({
      dragend(e: any) {
        const marker = e.target;
        if (marker != null) {
          const latLng = marker.getLatLng();
          onChange({
            latitude: parseFloat(latLng.lat.toFixed(6)),
            longitude: parseFloat(latLng.lng.toFixed(6)),
          });
        }
      },
    }),
    [onChange]
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
        <span className="form-label" style={{ margin: 0 }}>
          <MapPin size={16} color="var(--primary)" />
          Pin Exact Map Location:
        </span>
        
        {selectedCityName && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: '#276221', background: 'rgba(39, 98, 33, 0.12)', padding: '4px 10px', borderRadius: '12px', border: '1px solid rgba(39, 98, 33, 0.3)' }}>
            <Target size={13} />
            Focused on: <strong>{selectedCityName}</strong>
          </div>
        )}

        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <Navigation size={12} />
          Click or drag pin to adjust
        </span>
      </div>

      <div className="map-picker-container">
        <MapContainer
          center={position}
          zoom={14}
          scrollWheelZoom={true}
          style={{ width: '100%', height: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <Marker
            position={position}
            draggable={true}
            eventHandlers={markerHandlers}
            icon={customMapPin}
          />
          <MapController 
            onChange={onChange} 
            centerLat={targetLat} 
            centerLng={targetLng} 
          />
        </MapContainer>
      </div>

      {/* Lat / Long Display & Quick Edit Inputs */}
      <div className="grid-2" style={{ marginTop: '10px' }}>
        <div style={{ background: '#f8faf8', padding: '8px 12px', borderRadius: '10px', border: '1px solid #cbd5e1', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>LAT:</span>
          <input
            type="number"
            step="0.0001"
            value={location.latitude}
            onChange={(e) => onChange({ ...location, latitude: parseFloat(e.target.value) || 0 })}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-main)', fontSize: '0.85rem', width: '100%', outline: 'none' }}
          />
        </div>
        <div style={{ background: '#f8faf8', padding: '8px 12px', borderRadius: '10px', border: '1px solid #cbd5e1', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>LNG:</span>
          <input
            type="number"
            step="0.0001"
            value={location.longitude}
            onChange={(e) => onChange({ ...location, longitude: parseFloat(e.target.value) || 0 })}
            style={{ background: 'transparent', border: 'none', color: 'var(--text-main)', fontSize: '0.85rem', width: '100%', outline: 'none' }}
          />
        </div>
      </div>
    </div>
  );
};
