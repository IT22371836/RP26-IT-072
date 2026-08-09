import React, { useEffect, useState } from 'react';
import { CheckCircle, Clock, XCircle } from 'lucide-react';
import { backendApi } from '../config/api';
import type { InteractionDto } from '../config/api';
import { requireFirebaseApiToken } from '../config/firebaseApiToken';

export const ProviderBookings: React.FC = () => {
  const [events, setEvents] = useState<InteractionDto[]>([]);
  const [error, setError] = useState('');
  const load = () => requireFirebaseApiToken().then(token => backendApi.listProviderInteractions(token)).then(setEvents).catch(err => setError(err.message));
  useEffect(() => { void load(); }, []);
  const closed = new Set(
    events.filter(item => ['booking_completed', 'booking_cancelled'].includes(item.interaction_type))
      .map(item => `${item.request_id}:${item.provider_id}`)
  );
  const incoming = events.filter(item => item.interaction_type === 'booking_requested');
  const transition = async (id: string, action: 'complete' | 'cancel') => {
    setError('');
    try {
      const token = await requireFirebaseApiToken();
      if (action === 'complete') await backendApi.completeBooking(token, id);
      else await backendApi.cancelBooking(token, id);
      await load();
    } catch (err: any) { setError(err.message); }
  };
  return <section className="glass-panel" style={{ padding: 22, marginBottom: 28, borderLeft: '6px solid #22c55e' }}>
    <h2 style={{ marginTop: 0 }}><Clock size={20} /> Incoming pipeline bookings</h2>
    {error && <p style={{ color: '#991b1b' }}>{error}</p>}
    {incoming.length === 0 ? <p>No incoming bookings.</p> : incoming.map(item => {
      const isClosed = closed.has(`${item.request_id}:${item.provider_id}`);
      return <article key={item.interaction_id} style={{ padding: 12, borderBottom: '1px solid #cbd5e1' }}>
        <strong>{item.category}</strong> · request {item.request_id} · {new Date(item.timestamp).toLocaleString()}
        {isClosed ? <p><CheckCircle size={15} /> Booking closed</p> : <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button className="btn btn-primary" onClick={() => transition(item.interaction_id, 'complete')}><CheckCircle size={15} /> Complete</button>
          <button className="btn btn-outline" onClick={() => transition(item.interaction_id, 'cancel')}><XCircle size={15} /> Cancel</button>
        </div>}
      </article>;
    })}
  </section>;
};
