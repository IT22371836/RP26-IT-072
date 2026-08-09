import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle, Clock, RefreshCw, Search, Star } from 'lucide-react';
import { backendApi } from '../config/api';
import type { InteractionDto, PipelineCreateDto, PipelineRunDto } from '../config/api';
import { requireFirebaseApiToken } from '../config/firebaseApiToken';
import type { Customer } from '../config/firebase';
import { SERVICE_CATEGORIES } from '../data/categories';
import { SRI_LANKA_DISTRICTS } from '../data/sriLankaData';

const ACTIVE = new Set(['initializing', 'created', 'component1_running', 'component1_completed', 'component2_running', 'component2_completed', 'component4_running', 'retry_pending']);
const STORAGE_KEY = 'weda_active_pipeline_run';

function isoDate(offset = 0): string {
  const value = new Date();
  value.setDate(value.getDate() + offset);
  return value.toISOString().slice(0, 10);
}

export const PipelineWorkspace: React.FC<{ currentUser: Customer }> = ({ currentUser }) => {
  const initialDistrict = currentUser.district || 'Colombo';
  const district = SRI_LANKA_DISTRICTS.find(item => item.name === initialDistrict) || SRI_LANKA_DISTRICTS[0];
  const [form, setForm] = useState<PipelineCreateDto>({
    request_text: '', category: SERVICE_CATEGORIES[0], district: district.name,
    city: currentUser.city || district.cities[0], urgency: 'normal', service_date: isoDate(1),
    service_time: { start_time: '09:00', end_time: '11:00' }, location_type: 'indoor'
  });
  const [confirmed, setConfirmed] = useState(false);
  const [run, setRun] = useState<PipelineRunDto | null>(null);
  const [history, setHistory] = useState<PipelineRunDto[]>([]);
  const [interactions, setInteractions] = useState<InteractionDto[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [review, setReview] = useState<Record<string, { rating: number; text: string }>>({});
  const cities = useMemo(
    () => SRI_LANKA_DISTRICTS.find(item => item.name === form.district)?.cities || [],
    [form.district]
  );
  const activeRunId = run?.run_id;
  const activeRunStatus = run?.status;

  const reloadHistory = async () => {
    const token = await requireFirebaseApiToken();
    const [runs, events] = await Promise.all([
      backendApi.listPipelines(token), backendApi.listCustomerInteractions(token)
    ]);
    setHistory(runs); setInteractions(events);
  };

  useEffect(() => {
    reloadHistory().catch(err => setError(err.message));
    const runId = localStorage.getItem(STORAGE_KEY);
    if (runId) requireFirebaseApiToken()
      .then(token => backendApi.getPipeline(token, runId))
      .then(setRun)
      .catch(() => localStorage.removeItem(STORAGE_KEY));
  }, []);

  useEffect(() => {
    if (!activeRunId || !activeRunStatus || !ACTIVE.has(activeRunStatus)) return;
    let stopped = false; let polls = 0;
    const poll = async () => {
      try {
        const next = await backendApi.getPipeline(await requireFirebaseApiToken(), activeRunId);
        if (stopped) return;
        setRun(next); polls += 1;
        if (ACTIVE.has(next.status)) window.setTimeout(poll, polls < 15 ? 2000 : 5000);
        else { localStorage.removeItem(STORAGE_KEY); reloadHistory().catch(() => undefined); }
      } catch (err: any) { if (!stopped) setError(err.message); }
    };
    const timer = window.setTimeout(poll, 2000);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [activeRunId, activeRunStatus]);

  const start = async (event: React.FormEvent) => {
    event.preventDefault(); setError('');
    if (!confirmed || !currentUser.location) { setError('Confirm your saved service location before continuing.'); return; }
    setBusy(true);
    try {
      const idempotencyKey = crypto.randomUUID();
      const token = await requireFirebaseApiToken();
      const started = await backendApi.startPipeline(token, form, idempotencyKey);
      localStorage.setItem(STORAGE_KEY, started.run_id);
      setRun(await backendApi.getPipeline(token, started.run_id));
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };

  const selectProvider = async (providerId: string) => {
    if (!run) return; setBusy(true); setError('');
    try {
      const token = await requireFirebaseApiToken();
      await backendApi.selectPipelineProvider(token, run.run_id, providerId);
      setRun(await backendApi.getPipeline(token, run.run_id));
      await reloadHistory();
    } catch (err: any) { setError(err.message); } finally { setBusy(false); }
  };

  const retry = async () => {
    if (!run) return;
    setRun(await backendApi.retryPipeline(await requireFirebaseApiToken(), run.run_id));
  };

  const completed = interactions.filter(item => item.interaction_type === 'booking_completed');
  const ratedKeys = new Set(interactions.filter(item => item.interaction_type === 'rated').map(item => `${item.request_id}:${item.provider_id}`));
  const bookings = interactions.filter(item => ['booking_requested', 'booking_completed', 'booking_cancelled'].includes(item.interaction_type));

  return <section className="glass-panel" style={{ padding: 24, marginBottom: 32, borderLeft: '6px solid #0ea5e9' }}>
    <h2 style={{ marginTop: 0 }}><Search size={21} /> Request a service: Component 1 → 2 → 4</h2>
    {error && <div style={{ padding: 12, background: '#fee2e2', color: '#991b1b', borderRadius: 8, marginBottom: 14 }}>{error}</div>}
    <form onSubmit={start} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: 12 }}>
      <textarea required minLength={10} placeholder="Describe the maintenance problem" value={form.request_text} onChange={e => setForm({ ...form, request_text: e.target.value })} style={{ gridColumn: '1/-1', minHeight: 80 }} />
      <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>{SERVICE_CATEGORIES.map(item => <option key={item}>{item}</option>)}</select>
      <select value={form.district} onChange={e => { const next = SRI_LANKA_DISTRICTS.find(item => item.name === e.target.value)!; setForm({ ...form, district: next.name, city: next.cities[0] }); }}>{SRI_LANKA_DISTRICTS.map(item => <option key={item.name}>{item.name}</option>)}</select>
      <select value={form.city} onChange={e => setForm({ ...form, city: e.target.value })}>{cities.map(item => <option key={item}>{item}</option>)}</select>
      <select value={form.urgency} onChange={e => setForm({ ...form, urgency: e.target.value as PipelineCreateDto['urgency'] })}><option value="normal">Normal</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option></select>
      <input type="date" min={isoDate()} max={isoDate(6)} required value={form.service_date} onChange={e => setForm({ ...form, service_date: e.target.value })} />
      <input type="time" min="08:00" max="17:59" required value={form.service_time.start_time} onChange={e => setForm({ ...form, service_time: { ...form.service_time, start_time: e.target.value } })} />
      <input type="time" min="08:01" max="18:00" required value={form.service_time.end_time} onChange={e => setForm({ ...form, service_time: { ...form.service_time, end_time: e.target.value } })} />
      <select value={form.location_type} onChange={e => setForm({ ...form, location_type: e.target.value as PipelineCreateDto['location_type'] })}><option value="indoor">Indoor</option><option value="outdoor">Outdoor</option><option value="indoor and outdoor">Indoor and outdoor</option></select>
      <label style={{ gridColumn: '1/-1' }}><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Confirm saved location ({currentUser.location?.latitude}, {currentUser.location?.longitude})</label>
      <button className="btn btn-primary" disabled={busy || !confirmed} style={{ gridColumn: '1/-1' }}>{busy ? 'Starting…' : 'Run provider pipeline'}</button>
    </form>

    {run && <div style={{ marginTop: 24 }}>
      <h3>Pipeline progress <small>{run.run_id}</small></h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>{[
        ['Component 1 Top-20', !!run.component1], ['Component 2 filtering', !!run.component2], ['Component 4 Top-5', !!run.component4], ['Completed', run.status === 'completed']
      ].map(([label, done]) => <span key={String(label)} style={{ padding: '7px 10px', borderRadius: 16, background: done ? '#dcfce7' : '#e2e8f0' }}>{done ? <CheckCircle size={14} /> : <Clock size={14} />} {label}</span>)}</div>
      {ACTIVE.has(run.status) && <p><RefreshCw size={15} /> Worker is processing this request. Refresh-safe polling is active.</p>}
      {run.status === 'failed' && <div style={{ color: '#991b1b' }}><strong>{run.error?.code}</strong>: {run.error?.message} {run.error?.retryable && <button onClick={retry}>Retry</button>}</div>}
      {run.fallback?.used && <div style={{ margin: '14px 0', padding: 14, background: '#fef3c7', color: '#92400e', borderRadius: 8 }}><AlertTriangle size={18} /> Availability filtering returned no providers. These results are a disclosed relevance/trust fallback from Component 1; availability is not confirmed.</div>}
      {run.component4 && <div>
        <h3>Final Top-5</h3>
        <div style={{ display: 'grid', gap: 12 }}>{run.component4.providers.map(provider => {
          const c1 = run.component1?.providers.find(item => item.provider_id === provider.provider_id);
          const c2 = run.component2?.all_evaluated_providers.find(item => item.provider_id === provider.provider_id);
          return <article key={provider.provider_id} style={{ border: '1px solid #cbd5e1', borderRadius: 10, padding: 14 }}>
            <strong>#{provider.rank} {provider.provider_name}</strong> · {provider.category} · {provider.city}
            <p>C1 hybrid: {c1?.hybrid_score?.toFixed(3) ?? 'n/a'} · C2 distance: {c2?.distance_km ?? 'n/a'} km · availability: {c2?.is_available ? 'available' : 'fallback/not available'} · weather: {c2?.weather_risk ?? run.component2?.output_results.weather_risk}</p>
            <p>C4 final: {provider.final_score?.toFixed(3)} · credibility: {provider.mean_credibility?.toFixed(3)} · evidence: {provider.evidence_status}</p>
            <button className="btn btn-primary" disabled={busy || !!run.selected_provider_id} onClick={() => selectProvider(provider.provider_id)}>{run.selected_provider_id === provider.provider_id ? 'Booking requested' : 'Select & request booking'}</button>
          </article>;
        })}</div>
        <details style={{ marginTop: 14 }}><summary>Top-20 → Top-10 → Top-5 audit and rejection reasons</summary>
          <p>C1: {run.component1?.providers.length || 0}; C2: {run.component2?.output_results.provider_ids?.length || 0}; C4: {run.component4.providers.length}</p>
          <ul>{run.component2?.all_evaluated_providers.map(item => <li key={item.provider_id}>{item.provider_id}: {item.working_hours_status}; distance {item.distance_km ?? 'unknown'} km; weather {item.weather_risk}</li>)}</ul>
        </details>
      </div>}
    </div>}

    <details style={{ marginTop: 24 }} open><summary><strong>Bookings and ratings</strong></summary>
      {bookings.length === 0 ? <p>No pipeline bookings yet.</p> : bookings.map(item => <div key={item.interaction_id} style={{ padding: 8, borderBottom: '1px solid #e2e8f0' }}>{item.provider_name || item.provider_id}: {item.interaction_type.replaceAll('_', ' ')}</div>)}
      {completed.filter(item => !ratedKeys.has(`${item.request_id}:${item.provider_id}`)).map(item => {
        const value = review[item.interaction_id] || { rating: 5, text: '' };
        return <div key={item.interaction_id} style={{ padding: 10 }}><Star size={16} /> Rate {item.provider_name}
          <select value={value.rating} onChange={e => setReview({ ...review, [item.interaction_id]: { ...value, rating: Number(e.target.value) } })}>{[5,4,3,2,1].map(n => <option key={n} value={n}>{n}</option>)}</select>
          <input placeholder="Review" value={value.text} onChange={e => setReview({ ...review, [item.interaction_id]: { ...value, text: e.target.value } })} />
          <button onClick={async () => { await backendApi.rateBooking(await requireFirebaseApiToken(), item.interaction_id, value.rating, value.text); await reloadHistory(); }}>Submit rating</button>
        </div>;
      })}
    </details>
    <details style={{ marginTop: 16 }}><summary><strong>Request history ({history.length})</strong></summary>{history.map(item => <button key={item.run_id} onClick={() => setRun(item)} style={{ display: 'block', margin: 6 }}>{new Date(item.created_at).toLocaleString()} · {item.request.category} · {item.status}</button>)}</details>
  </section>;
};
