import React, { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle, Clock, Cpu, Filter, RefreshCw, Search, ShieldCheck, Star } from 'lucide-react';
import { backendApi } from '../config/api';
import type { Component2EvaluatedProviderDto, InteractionDto, PipelineCreateDto, PipelineProviderDto, PipelineRunDto } from '../config/api';
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

type AuditState = 'waiting' | 'running' | 'completed' | 'failed';

function auditState(run: PipelineRunDto, stage: 'component1' | 'component2' | 'component4'): AuditState {
  if (run[stage]) return 'completed';
  if (run.status === `${stage}_running`) return 'running';
  if (run.status === 'failed') {
    if (stage === 'component1' && !run.component1) return 'failed';
    if (stage === 'component2' && run.component1 && !run.component2) return 'failed';
    if (stage === 'component4' && run.component2 && !run.component4) return 'failed';
  }
  return 'waiting';
}

function formatDuration(value?: number): string {
  if (value === undefined || !Number.isFinite(value)) return 'Pending';
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value.toFixed(1)} ms`;
}

function formatScore(value?: number, digits = 3): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : 'n/a';
}

const tableCellStyle: React.CSSProperties = {
  borderBottom: '1px solid #cbd5e1', padding: '8px 9px', textAlign: 'left', verticalAlign: 'top'
};

function strongestC1Signal(provider: PipelineProviderDto): string {
  const scores = [
    ['TF-IDF', provider.tfidf_score],
    ['semantic', provider.bert_score],
    ['collaborative preference', provider.cf_score]
  ] as const;
  const available: Array<readonly [string, number]> = [];
  scores.forEach(([label, value]) => {
    if (typeof value === 'number') available.push([label, value]);
  });
  return available.length ? available.reduce((best, item) => item[1] > best[1] ? item : best)[0] : 'unknown';
}

function c1SelectionReason(provider: PipelineProviderDto): string {
  if (provider.selection_reason) return provider.selection_reason;
  return `Selected at hybrid rank #${provider.rank} with score ${formatScore(provider.hybrid_score, 4)}. `
    + `${strongestC1Signal(provider)} was the strongest stored normalized signal. `
    + 'The exact match tier was not persisted for this older run.';
}

function c2DecisionReason(provider: Component2EvaluatedProviderDto, selectedRank?: number): string {
  if (provider.decision_reason) return provider.decision_reason;
  if (selectedRank !== undefined) {
    return `Passed the requested working-hours availability check and was distance-ranked #${selectedRank} `
      + `among available providers (${provider.distance_km ?? 'unknown'} km). Weather is advisory.`;
  }
  if (provider.is_available) return 'Passed availability but fell outside the nearest Top-10 distance cutoff.';
  return provider.working_hours_status || 'Rejected because the provider did not pass the availability requirements.';
}

function c4RankingReason(provider: PipelineProviderDto): string {
  if (provider.ranking_reason) return provider.ranking_reason;
  return `Ranked #${provider.rank} by final CATF trust score ${formatScore(provider.final_score, 4)}; `
    + `effective review count (${formatScore(provider.effective_review_count, 2)}) and credibility `
    + `(${formatScore(provider.mean_credibility, 4)}) are tie-breakers. Evidence source: `
    + `${provider.score_source ?? 'not stored'}; status: ${provider.evidence_status ?? 'not stored'}.`;
}

function AuditTable({ children, minWidth = 900 }: { children: React.ReactNode; minWidth?: number }) {
  return <div style={{ overflowX: 'auto', marginTop: 10 }}>
    <table style={{ width: '100%', minWidth, borderCollapse: 'collapse', fontSize: 13 }}>{children}</table>
  </div>;
}

function Component1ProviderEvidence({ run }: { run: PipelineRunDto }) {
  const providers = run.component1?.providers ?? [];
  if (!providers.length) return <p>Component 1 provider records are not available yet.</p>;
  return <details style={{ marginTop: 10 }}>
    <summary style={{ cursor: 'pointer', fontWeight: 700 }}>View actual Component 1 Top-{providers.length} providers and selection reasons</summary>
    <AuditTable minWidth={1080}>
      <thead><tr>{['Rank', 'Provider', 'Category / location', 'Hybrid', 'TF-IDF', 'Semantic', 'Preference', 'Why selected'].map(label => <th key={label} style={tableCellStyle}>{label}</th>)}</tr></thead>
      <tbody>{providers.map(provider => <tr key={provider.provider_id}>
        <td style={tableCellStyle}>#{provider.rank}</td>
        <td style={tableCellStyle}><strong>{provider.provider_name}</strong><br/><code>{provider.provider_id}</code></td>
        <td style={tableCellStyle}>{provider.category}<br/>{provider.city}, {provider.district}</td>
        <td style={tableCellStyle}>{formatScore(provider.hybrid_score)}</td>
        <td style={tableCellStyle}>{formatScore(provider.tfidf_score)}</td>
        <td style={tableCellStyle}>{formatScore(provider.bert_score)}</td>
        <td style={tableCellStyle}>{formatScore(provider.cf_score)}</td>
        <td style={{ ...tableCellStyle, minWidth: 330 }}>{c1SelectionReason(provider)}</td>
      </tr>)}</tbody>
    </AuditTable>
  </details>;
}

function Component2ProviderEvidence({ run }: { run: PipelineRunDto }) {
  const evaluated = run.component2?.all_evaluated_providers ?? [];
  const selectedIds = (run.component2?.output_results.provider_ids ?? []) as string[];
  const byId = new Map(evaluated.map(provider => [provider.provider_id, provider]));
  const selected = selectedIds.map((providerId, index) => ({
    provider: byId.get(providerId) ?? { provider_id: providerId }, rank: index + 1
  }));
  const selectedSet = new Set(selectedIds);
  const rejected = evaluated.filter(provider => !selectedSet.has(provider.provider_id));
  if (!evaluated.length && !selected.length) return <p>Component 2 provider records are not available yet.</p>;
  return <details style={{ marginTop: 10 }}>
    <summary style={{ cursor: 'pointer', fontWeight: 700 }}>View actual Component 2 selected Top-{selected.length} and {rejected.length} non-selected providers</summary>
    <h5 style={{ marginBottom: 4 }}>Selected providers, in the exact backend output order</h5>
    <AuditTable minWidth={930}>
      <thead><tr>{['Rank', 'Provider', 'Distance', 'Availability evidence', 'Weather', 'Why selected'].map(label => <th key={label} style={tableCellStyle}>{label}</th>)}</tr></thead>
      <tbody>{selected.map(({ provider, rank }) => <tr key={provider.provider_id}>
        <td style={tableCellStyle}>#{rank}</td>
        <td style={tableCellStyle}><strong>{provider.provider_name ?? provider.provider_id}</strong><br/><code>{provider.provider_id}</code></td>
        <td style={tableCellStyle}>{provider.distance_km ?? 'unknown'} km</td>
        <td style={tableCellStyle}>{provider.working_hours_status ?? 'Available'}</td>
        <td style={tableCellStyle}>{provider.weather_risk ?? run.component2?.output_results.weather_risk ?? 'unknown'}</td>
        <td style={{ ...tableCellStyle, minWidth: 330 }}>{c2DecisionReason(provider, rank)}</td>
      </tr>)}</tbody>
    </AuditTable>
    {rejected.length > 0 && <details style={{ marginTop: 8 }}>
      <summary style={{ cursor: 'pointer' }}>View rejected / outside-cutoff providers and reasons ({rejected.length})</summary>
      <AuditTable minWidth={800}>
        <thead><tr>{['C1 provider', 'Distance', 'Decision', 'Reason'].map(label => <th key={label} style={tableCellStyle}>{label}</th>)}</tr></thead>
        <tbody>{rejected.map(provider => <tr key={provider.provider_id}>
          <td style={tableCellStyle}><strong>{provider.provider_name ?? provider.provider_id}</strong><br/><code>{provider.provider_id}</code></td>
          <td style={tableCellStyle}>{provider.distance_km ?? 'unknown'} km</td>
          <td style={tableCellStyle}>{provider.is_available ? 'Eligible, outside Top-10' : 'Rejected'}</td>
          <td style={{ ...tableCellStyle, minWidth: 360 }}>{c2DecisionReason(provider)}</td>
        </tr>)}</tbody>
      </AuditTable>
    </details>}
  </details>;
}

function Component4ProviderEvidence({ run }: { run: PipelineRunDto }) {
  const providers = run.component4?.providers ?? [];
  if (!providers.length) return <p>Component 4 provider records are not available yet.</p>;
  return <details style={{ marginTop: 10 }}>
    <summary style={{ cursor: 'pointer', fontWeight: 700 }}>View actual Component 4 Top-{providers.length} providers and ranking reasons</summary>
    <AuditTable minWidth={1100}>
      <thead><tr>{['Rank', 'Provider', 'Final CATF', 'Credibility', 'Reliability', 'Evidence', 'Aspect scores', 'Why selected'].map(label => <th key={label} style={tableCellStyle}>{label}</th>)}</tr></thead>
      <tbody>{providers.map(provider => <tr key={provider.provider_id}>
        <td style={tableCellStyle}>#{provider.rank}</td>
        <td style={tableCellStyle}><strong>{provider.provider_name}</strong><br/><code>{provider.provider_id}</code></td>
        <td style={tableCellStyle}>{formatScore(provider.final_score)}</td>
        <td style={tableCellStyle}>{formatScore(provider.mean_credibility)}</td>
        <td style={tableCellStyle}>{formatScore(provider.reliability_factor)}</td>
        <td style={tableCellStyle}>{provider.evidence_status ?? 'n/a'}<br/><small>{provider.score_source ?? 'source not stored'}</small></td>
        <td style={tableCellStyle}>{provider.aspect_scores ? Object.entries(provider.aspect_scores).map(([aspect, score]) => <div key={aspect}>{aspect}: {formatScore(score)}</div>) : 'n/a'}</td>
        <td style={{ ...tableCellStyle, minWidth: 350 }}>{c4RankingReason(provider)}</td>
      </tr>)}</tbody>
    </AuditTable>
  </details>;
}

function PipelineExecutionAudit({ run }: { run: PipelineRunDto }) {
  const c1State = auditState(run, 'component1');
  const c2State = auditState(run, 'component2');
  const c4State = auditState(run, 'component4');
  const c1Count = run.component1?.providers.length ?? 0;
  const c2Count = run.component2?.output_results.provider_ids?.length ?? 0;
  const c2Evaluated = run.component2?.all_evaluated_providers.length ?? c1Count;
  const c4Count = run.component4?.providers.length ?? 0;
  const stateStyle: Record<AuditState, { color: string; background: string; label: string }> = {
    waiting: { color: '#64748b', background: '#f1f5f9', label: 'Waiting' },
    running: { color: '#0369a1', background: '#e0f2fe', label: 'Running' },
    completed: { color: '#166534', background: '#dcfce7', label: 'Completed' },
    failed: { color: '#991b1b', background: '#fee2e2', label: 'Failed' }
  };
  const stages = [
    {
      key: 'component1', title: 'Component 1 · Hybrid recommendation', icon: <Cpu size={18} />,
      state: c1State,
      description: 'Runs the trained TF-IDF vectorizer, multilingual semantic embedding model, and collaborative preference score across the artifact plus verified live providers.',
      facts: [
        `Engine: ${run.component1?.engine ?? 'hybrid_tfidf_semantic_cf'}`,
        `Artifact/model loaded: ${run.component1?.model_loaded === true ? 'Yes' : c1State === 'completed' ? 'Yes' : 'Pending'}`,
        `Version: ${run.component1?.component_version ?? 'Pending'} / ${run.component1?.model_version ?? 'Pending'}`,
        `Candidates: ${run.component1?.candidate_pool_count ?? run.component1?.artifact_provider_count ?? '10,000'} → ${c1Count || 'Top-20 pending'}`,
        `Pool: ${run.component1?.artifact_provider_count ?? '10,000'} artifact + ${run.component1?.additional_verified_provider_count ?? 'Pending'} verified live`,
        `Verified Firebase profiles read: ${run.component1?.verified_firebase_provider_count ?? 'Pending'}`,
        `Preference signals: ${run.component1?.preference_signal_count ?? 'Pending'}`,
        `Runtime: ${formatDuration(run.component1?.processing_time_ms)}`
      ]
    },
    {
      key: 'component2', title: 'Component 2 · Availability filter', icon: <Filter size={18} />,
      state: c2State,
      description: 'Deterministic Firebase filter—not a trained ML model. Checks working-hours availability, ranks passing C1 providers by distance, and reports weather as advisory context.',
      facts: [
        `Engine: ${run.component2?.engine ?? 'deterministic_distance_hours_weather_filter'}`,
        `Version: ${run.component2?.component_version ?? 'Pending'} / ${run.component2?.model_version ?? 'Pending'}`,
        `Candidates: ${c2Evaluated || 'Top-20 pending'} → ${run.component2 ? c2Count : 'Top-10 pending'}`,
        `Rejected: ${run.component2 ? Math.max(0, c2Evaluated - c2Count) : 'Pending'}`,
        `Weather: ${run.component2?.output_results.weather_risk ?? 'Pending'}`,
        `Runtime: ${formatDuration(run.component2?.processing_time_ms)}`
      ]
    },
    {
      key: 'component4', title: 'Component 4 · Trust ranking', icon: <ShieldCheck size={18} />,
      state: c4State,
      description: 'Loads CATF trust scores produced by the trained ABSA and review-credibility models, then ranks the C2 candidates.',
      facts: [
        `Engine: ${run.component4?.engine ?? 'catf_precomputed_absa_credibility_ranking'}`,
        `Artifact/model loaded: ${run.component4?.model_loaded === true ? 'Yes' : c4State === 'completed' ? 'Yes' : 'Pending'}`,
        `Versions: ${run.component4 ? Object.values(run.component4.versions).join(' · ') : 'Pending'}`,
        `Candidates: ${run.component4?.input_count ?? (run.component2 ? c2Count : 'Top-10 pending')} → ${c4Count || 'Top-5 pending'}`,
        `Source: ${run.component4?.handoff?.source ?? run.fallback?.source ?? 'component2'}`,
        `Runtime: ${formatDuration(run.component4?.pipeline_processing_time_ms ?? run.component4?.processing_time_ms)}`
      ]
    }
  ] as const;

  return <details style={{ marginTop: 16, border: '1px solid #94a3b8', borderRadius: 10, background: 'rgba(15, 23, 42, 0.04)' }}>
    <summary style={{ padding: 13, cursor: 'pointer', fontWeight: 700 }}>
      <Activity size={17} /> Pipeline execution log <small style={{ marginLeft: 6, fontWeight: 500 }}>expand technical audit</small>
    </summary>
    <div style={{ padding: '0 13px 13px' }}>
      <p style={{ marginTop: 0 }}>Persisted backend evidence for request <code>{run.request_id}</code>. This confirms the actual 1 → 2 → 4 handoff; it is not a simulated frontend progress display.</p>
      <div style={{ display: 'grid', gap: 10 }}>
        {stages.map(stage => {
          const appearance = stateStyle[stage.state];
          return <article key={stage.key} style={{ borderLeft: `4px solid ${appearance.color}`, borderRadius: 8, padding: 12, background: appearance.background }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
              <strong>{stage.icon} {stage.title}</strong>
              <span style={{ color: appearance.color, fontWeight: 700 }}>{stage.state === 'running' ? <RefreshCw size={14} /> : stage.state === 'completed' ? <CheckCircle size={14} /> : stage.state === 'failed' ? <AlertTriangle size={14} /> : <Clock size={14} />} {appearance.label}</span>
            </div>
            <p style={{ margin: '7px 0', fontSize: 14 }}>{stage.description}</p>
            <ul style={{ margin: 0, paddingLeft: 20, display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: '3px 18px' }}>
              {stage.facts.map(fact => <li key={fact}>{fact}</li>)}
            </ul>
            {stage.key === 'component1' && <Component1ProviderEvidence run={run} />}
            {stage.key === 'component2' && <Component2ProviderEvidence run={run} />}
            {stage.key === 'component4' && <Component4ProviderEvidence run={run} />}
          </article>;
        })}
      </div>
      <h4 style={{ marginBottom: 6 }}>Backend transition events</h4>
      {run.execution_log?.length ? <ol style={{ margin: 0, paddingLeft: 22 }}>
        {run.execution_log.map((event, index) => <li key={`${event.status}-${event.timestamp}-${index}`} style={{ marginBottom: 5 }}>
          <code>{new Date(event.timestamp).toLocaleTimeString()}</code> · <strong>{event.status}</strong> · {event.message}
        </li>)}
      </ol> : <p>No persisted transition events are available for this older run. Component payload evidence is shown above.</p>}
      {run.error && <p style={{ color: '#991b1b' }}><strong>{run.error.code}:</strong> {run.error.message}</p>}
    </div>
  </details>;
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
  const activeRunStorageKey = `${STORAGE_KEY}:${currentUser.id}`;

  const reloadHistory = async () => {
    const token = await requireFirebaseApiToken();
    const [runs, events] = await Promise.all([
      backendApi.listPipelines(token), backendApi.listCustomerInteractions(token)
    ]);
    setHistory(runs); setInteractions(events);
  };

  useEffect(() => {
    reloadHistory().catch(err => setError(err.message));
    const runId = localStorage.getItem(activeRunStorageKey);
    if (runId) requireFirebaseApiToken()
      .then(token => backendApi.getPipeline(token, runId))
      .then(setRun)
      .catch(() => localStorage.removeItem(activeRunStorageKey));
  }, [activeRunStorageKey]);

  useEffect(() => {
    if (!activeRunId || !activeRunStatus || !ACTIVE.has(activeRunStatus)) return;
    let stopped = false; let polls = 0;
    const poll = async () => {
      try {
        const next = await backendApi.getPipeline(await requireFirebaseApiToken(), activeRunId);
        if (stopped) return;
        setRun(next); polls += 1;
        if (ACTIVE.has(next.status)) window.setTimeout(poll, polls < 15 ? 2000 : 5000);
        else { localStorage.removeItem(activeRunStorageKey); reloadHistory().catch(() => undefined); }
      } catch (err: any) { if (!stopped) setError(err.message); }
    };
    const timer = window.setTimeout(poll, 2000);
    return () => { stopped = true; window.clearTimeout(timer); };
  }, [activeRunId, activeRunStatus, activeRunStorageKey]);

  const start = async (event: React.FormEvent) => {
    event.preventDefault(); setError('');
    if (!confirmed || !currentUser.location) { setError('Confirm your saved service location before continuing.'); return; }
    setBusy(true);
    try {
      const idempotencyKey = crypto.randomUUID();
      const token = await requireFirebaseApiToken();
      const started = await backendApi.startPipeline(token, form, idempotencyKey);
      localStorage.setItem(activeRunStorageKey, started.run_id);
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
    setBusy(true); setError('');
    try {
      const token = await requireFirebaseApiToken();
      const latest = await backendApi.getPipeline(token, run.run_id);
      if (latest.status !== 'failed') {
        setRun(latest);
        return;
      }
      setRun(await backendApi.retryPipeline(token, run.run_id));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
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
      <PipelineExecutionAudit run={run} />
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
