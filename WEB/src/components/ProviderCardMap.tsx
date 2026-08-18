import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default marker icon paths in Vite
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface ProviderCardMapProps {
  latitude: number;
  longitude: number;
  providerName: string;
  category?: string;
  cityName: string;
  districtName: string;
}

export const ProviderCardMap: React.FC<ProviderCardMapProps> = ({
  latitude,
  longitude,
  providerName,
  category,
  cityName,
  districtName
}) => {
  const position: [number, number] = [latitude || 6.9271, longitude || 79.8612];

  return (
    <div style={{ marginTop: '12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
        <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
          🗺️ Provider Pinpoint Location ({cityName}):
        </span>
      </div>
      
      <div style={{ height: '170px', width: '100%', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(16, 185, 129, 0.3)', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
        <MapContainer
          center={position}
          zoom={13}
          scrollWheelZoom={false}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; OpenStreetMap'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <Marker position={position}>
            <Popup>
              <div style={{ textAlign: 'center', color: '#0f172a', padding: '2px' }}>
                <strong style={{ fontSize: '0.9rem', display: 'block', marginBottom: '2px' }}>{providerName}</strong>
                <span style={{ fontSize: '0.78rem', color: '#059669', background: 'rgba(16,185,129,0.15)', padding: '2px 6px', borderRadius: '4px', display: 'inline-block', marginBottom: '4px' }}>
                  {category || 'Service Provider'}
                </span>
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  📍 {cityName}, {districtName}
                </div>
              </div>
            </Popup>
          </Marker>
        </MapContainer>
      </div>
    </div>
  );
};
