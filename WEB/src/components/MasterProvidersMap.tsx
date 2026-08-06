import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Provider } from '../config/firebase';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface MasterProvidersMapProps {
  providers: Provider[];
}

export const MasterProvidersMap: React.FC<MasterProvidersMapProps> = ({ providers }) => {
  // Center of Sri Lanka
  const centerSriLanka: [number, number] = [7.8731, 80.7718];

  return (
    <div style={{ height: '420px', width: '100%', borderRadius: '16px', overflow: 'hidden', border: '1px solid rgba(16, 185, 129, 0.4)', boxShadow: '0 6px 20px rgba(0,0,0,0.3)', marginBottom: '24px' }}>
      <MapContainer
        center={centerSriLanka}
        zoom={7}
        scrollWheelZoom={true}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {providers.map((p) => {
          if (!p.location || !p.location.latitude || !p.location.longitude) return null;
          const pos: [number, number] = [p.location.latitude, p.location.longitude];
          return (
            <Marker key={p.id || p.email} position={pos}>
              <Popup>
                <div style={{ textAlign: 'center', color: '#0f172a', padding: '4px', minWidth: '150px' }}>
                  <img
                    src={p.providerImage || (p as any).customerImage || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + p.fullName}
                    alt={p.fullName}
                    style={{ width: '40px', height: '40px', borderRadius: '50%', objectFit: 'cover', border: '2px solid #059669', marginBottom: '4px', flexShrink: 0, aspectRatio: '1 / 1' }}
                  />
                  <strong style={{ fontSize: '0.92rem', display: 'block' }}>{p.fullName}</strong>
                  <span style={{ fontSize: '0.78rem', color: '#059669', background: 'rgba(16,185,129,0.15)', padding: '2px 8px', borderRadius: '6px', fontWeight: 600, display: 'inline-block', margin: '3px 0' }}>
                    {p.category || 'Provider'}
                  </span>
                  <div style={{ fontSize: '0.78rem', color: '#475569' }}>
                    📍 {p.city}, {p.district}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#0284c7', fontWeight: 600, marginTop: '4px' }}>
                    📞 {p.phone}
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
};
