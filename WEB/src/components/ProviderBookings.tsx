import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle, Clock, RefreshCw, XCircle } from 'lucide-react';
import { backendApi } from '../config/api';
import type { InteractionDto } from '../config/api';
import { requireFirebaseApiToken } from '../config/firebaseApiToken';

type BookingAction = 'accept' | 'reject' | 'complete' | 'cancel';

const bookingEventTypes = new Set([
  'booking_requested', 'booking_accepted', 'booking_rejected',
  'booking_completed', 'booking_cancelled'
]);

const statusLabels: Record<string, string> = {
  booking_requested: 'Awaiting your response',
  booking_accepted: 'Accepted',
  booking_rejected: 'Rejected',
  booking_completed: 'Completed',
  booking_cancelled: 'Cancelled'
};

const bookingKey = (item: InteractionDto) => `${item.request_id}:${item.provider_id}`;

export const ProviderBookings: React.FC = () => {
  const [events, setEvents] = useState<InteractionDto[]>([]);
  const [error, setError] = useState('');
  const [busyBooking, setBusyBooking] = useState('');

  const load = useCallback(async () => {
    try {
      const token = await requireFirebaseApiToken();
      setEvents(await backendApi.listProviderInteractions(token));
      setError('');
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  const bookings = useMemo(() => {
    const latestByKey = new Map<string, InteractionDto>();
    const requests = events.filter(item => item.interaction_type === 'booking_requested');
    events.filter(item => bookingEventTypes.has(item.interaction_type)).forEach(item => {
      const key = bookingKey(item);
      const current = latestByKey.get(key);
      if (!current || new Date(item.timestamp).getTime() > new Date(current.timestamp).getTime()) {
        latestByKey.set(key, item);
      }
    });
    return requests
      .map(request => ({ request, latest: latestByKey.get(bookingKey(request)) ?? request }))
      .sort((a, b) => new Date(b.request.timestamp).getTime() - new Date(a.request.timestamp).getTime());
  }, [events]);

  const transition = async (booking: InteractionDto, action: BookingAction) => {
    setError('');
    setBusyBooking(booking.interaction_id);
    try {
      const token = await requireFirebaseApiToken();
      if (action === 'accept') await backendApi.acceptBooking(token, booking.interaction_id);
      if (action === 'reject') await backendApi.rejectBooking(token, booking.interaction_id);
      if (action === 'complete') await backendApi.completeBooking(token, booking.interaction_id);
      if (action === 'cancel') await backendApi.cancelBooking(token, booking.interaction_id);
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusyBooking('');
    }
  };

  return <section className="glass-panel" style={{ padding: 22, marginBottom: 28, borderLeft: '6px solid #22c55e' }}>
    <h2 style={{ marginTop: 0 }}><Clock size={20} /> Incoming pipeline bookings</h2>
    <p style={{ marginTop: -6, color: '#64748b' }}>New requests refresh automatically every five seconds.</p>
    {error && <p style={{ color: '#991b1b' }}>{error}</p>}
    {bookings.length === 0 ? <p>No incoming bookings.</p> : bookings.map(({ request, latest }) => {
      const pending = latest.interaction_type === 'booking_requested';
      const accepted = latest.interaction_type === 'booking_accepted';
      const busy = busyBooking === request.interaction_id;
      const details = request.request_details;
      return <article key={request.interaction_id} style={{ padding: 14, borderBottom: '1px solid #cbd5e1' }}>
        <div><strong>{request.category}</strong> · request {request.request_id}</div>
        <div style={{ marginTop: 4, color: '#64748b' }}>Customer ID: {request.user_id} · {new Date(request.timestamp).toLocaleString()}</div>
        {details && <div style={{ marginTop: 8, padding: 10, borderRadius: 8, background: 'rgba(148,163,184,.12)' }}>
          {details.request_text && <p style={{ marginTop: 0 }}>{details.request_text}</p>}
          <div>{details.city}, {details.district} · {details.service_date} · {details.service_time?.start_time}–{details.service_time?.end_time}</div>
          <div>{details.location_type} · urgency: {details.urgency}</div>
        </div>}
        <p style={{ margin: '8px 0' }}>
          {latest.interaction_type === 'booking_completed' ? <CheckCircle size={15} /> :
            latest.interaction_type === 'booking_rejected' || latest.interaction_type === 'booking_cancelled' ? <XCircle size={15} /> :
              <RefreshCw size={15} />}{' '}
          <strong>{statusLabels[latest.interaction_type] ?? latest.interaction_type}</strong>
        </p>
        {pending && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <button className="btn btn-primary" disabled={busy} onClick={() => transition(request, 'accept')}><CheckCircle size={15} /> Accept</button>
          <button className="btn btn-outline" disabled={busy} onClick={() => transition(request, 'reject')}><XCircle size={15} /> Reject</button>
        </div>}
        {accepted && <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <button className="btn btn-primary" disabled={busy} onClick={() => transition(request, 'complete')}><CheckCircle size={15} /> Mark completed</button>
          <button className="btn btn-outline" disabled={busy} onClick={() => transition(request, 'cancel')}><XCircle size={15} /> Cancel accepted booking</button>
        </div>}
      </article>;
    })}
  </section>;
};
