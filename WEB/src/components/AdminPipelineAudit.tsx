import React, { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { backendApi } from '../config/api';
import type { PipelineRunDto } from '../config/api';
import { requireFirebaseApiToken } from '../config/firebaseApiToken';

export const AdminPipelineAudit: React.FC = () => {
  const [runs, setRuns] = useState<PipelineRunDto[]>([]);
  const [error, setError] = useState('');
  const load = () => requireFirebaseApiToken().then(token => backendApi.listPipelines(token)).then(setRuns).catch(err => setError(err.message));
  useEffect(() => { void load(); }, []);
  return <div>
    <button className="btn btn-outline" onClick={load}><RefreshCw size={15} /> Refresh pipeline audit</button>
    {error && <p style={{ color: '#991b1b' }}>{error}</p>}
    <div style={{ overflowX: 'auto', marginTop: 12 }}><table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead><tr><th>Run / request</th><th>User</th><th>Status</th><th>C1 / C2 / C4</th><th>Versions</th><th>Fallback</th><th>Error</th><th>Updated</th></tr></thead>
      <tbody>{runs.map(run => <tr key={run.run_id} style={{ borderTop: '1px solid #cbd5e1' }}>
        <td>{run.run_id}<br/><small>{run.request_id}</small></td><td>{run.user_id}</td><td>{run.status}</td>
        <td>{run.component1?.providers.length || 0} / {run.component2?.output_results.provider_ids?.length || 0} / {run.component4?.providers.length || 0}</td>
        <td><small>{run.component1?.component_version || '—'}<br/>{run.component2?.component_version || '—'}</small></td>
        <td>{run.fallback?.used ? run.fallback.fallback_reason : 'No'}</td><td>{run.error ? `${run.error.code}: ${run.error.message}` : '—'}</td>
        <td>{new Date(run.updated_at).toLocaleString()}</td>
      </tr>)}</tbody>
    </table></div>
    <p><small>Research import verification is produced by <code>import_pipeline_providers.py --verify-only --report …</code>; reports never contain the shared password.</small></p>
  </div>;
};
