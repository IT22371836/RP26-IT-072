import React, { useState, useMemo } from 'react';
import type { 
  FilterRequestItem, 
  Customer, 
  Provider 
} from '../config/firebase';
import { 
  Search, 
  Calendar, 
  Filter, 
  Sparkles, 
  RefreshCw, 
  ShieldCheck, 
  CheckCircle2, 
  ChevronDown, 
  ChevronUp, 
  Clock, 
  Building2, 
  Cpu, 
  CloudSun 
} from 'lucide-react';

interface ProvidersFilterHistoryViewProps {
  filterRequests: FilterRequestItem[];
  customers: Customer[];
  providers: Provider[];
  loading: boolean;
  onRefresh: () => void;
}

export const ProvidersFilterHistoryView: React.FC<ProvidersFilterHistoryViewProps> = ({
  filterRequests,
  customers,
  providers,
  loading,
  onRefresh
}) => {
  // Filter States
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [riskFilter, setRiskFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedRequestId, setExpandedRequestId] = useState<string | null>(null);

  // Helper mapping customer user_id to customer full name
  const customerMap = useMemo(() => {
    const map: Record<string, Customer> = {};
    customers.forEach(c => {
      if (c.id) map[c.id] = c;
    });
    return map;
  }, [customers]);

  // Helper mapping provider_id to provider item
  const providerMap = useMemo(() => {
    const map: Record<string, Provider> = {};
    providers.forEach(p => {
      if (p.id) map[p.id] = p;
      if (p.uid) map[p.uid] = p;
    });
    return map;
  }, [providers]);

  // Quick Date Range Preset Handlers
  const handleSetPreset = (preset: 'ALL' | 'TODAY' | '7DAYS' | '30DAYS') => {
    const today = new Date();
    const formatDate = (d: Date) => d.toISOString().split('T')[0];

    if (preset === 'ALL') {
      setStartDate('');
      setEndDate('');
    } else if (preset === 'TODAY') {
      const todayStr = formatDate(today);
      setStartDate(todayStr);
      setEndDate(todayStr);
    } else if (preset === '7DAYS') {
      const past = new Date();
      past.setDate(today.getDate() - 7);
      setStartDate(formatDate(past));
      setEndDate(formatDate(today));
    } else if (preset === '30DAYS') {
      const past = new Date();
      past.setDate(today.getDate() - 30);
      setStartDate(formatDate(past));
      setEndDate(formatDate(today));
    }
  };

  // Reset all filters
  const handleResetFilters = () => {
    setStartDate('');
    setEndDate('');
    setRiskFilter('ALL');
    setSearchQuery('');
  };

  // Filter logic
  const filteredRequests = useMemo(() => {
    return filterRequests.filter(item => {
      const output = item.output_results;
      
      // Determine request date for date range filtering
      let requestDateStr = item.service_date || '';
      if (!requestDateStr && output?.evaluated_at) {
        requestDateStr = output.evaluated_at.split('T')[0];
      }

      // Date Range Filter
      if (startDate && requestDateStr && requestDateStr < startDate) {
        return false;
      }
      if (endDate && requestDateStr && requestDateStr > endDate) {
        return false;
      }

      // Risk Level Filter
      const risk = output?.weather_risk?.toUpperCase() || 'UNKNOWN';
      if (riskFilter !== 'ALL' && risk !== riskFilter) {
        return false;
      }

      // Search Query Filter
      if (searchQuery.trim()) {
        const query = searchQuery.trim().toLowerCase();
        const reqId = (item.request_id || item.id || '').toLowerCase();
        const userId = (item.user_id || '').toLowerCase();
        const customerObj = customerMap[item.user_id];
        const customerName = customerObj?.fullName.toLowerCase() || '';
        const rec = (output?.recommendation || '').toLowerCase();
        const locType = (item.location_type || '').toLowerCase();
        const weatherSum = (output?.weather_summary || '').toLowerCase();

        // Check evaluated provider names
        const hasMatchingProvider = output?.evaluated_providers?.some(ep => 
          ep.provider_name.toLowerCase().includes(query) ||
          ep.provider_id.toLowerCase().includes(query) ||
          (ep.recommendation || '').toLowerCase().includes(query)
        );

        const matches = 
          reqId.includes(query) ||
          userId.includes(query) ||
          customerName.includes(query) ||
          rec.includes(query) ||
          locType.includes(query) ||
          weatherSum.includes(query) ||
          Boolean(hasMatchingProvider);

        if (!matches) return false;
      }

      return true;
    });
  }, [filterRequests, startDate, endDate, riskFilter, searchQuery, customerMap]);

  // Overall Statistics Metrics
  const totalCount = filterRequests.length;
  const lowRiskCount = useMemo(() => {
    return filterRequests.filter(r => r.output_results?.weather_risk === 'LOW_RISK').length;
  }, [filterRequests]);

  const moderateHighRiskCount = useMemo(() => {
    return filterRequests.filter(r => r.output_results?.weather_risk && r.output_results?.weather_risk !== 'LOW_RISK').length;
  }, [filterRequests]);

  const totalEvaluatedProvidersCount = useMemo(() => {
    return filterRequests.reduce((acc, r) => acc + (r.output_results?.evaluated_providers?.length || 0), 0);
  }, [filterRequests]);

  const toggleExpand = (id: string) => {
    setExpandedRequestId(prev => prev === id ? null : id);
  };

  const getRiskBadgeStyle = (_risk?: string) => {
    return {
      bg: '#ffffff',
      border: '1px solid #276221',
      color: '#276221',
      icon: <CheckCircle2 size={14} color="#276221" />
    };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* Header Banner */}
      <div className="glass-panel" style={{ padding: '24px', background: '#ffffff', border: '1px solid #276221', borderLeft: '6px solid #276221' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <Cpu size={26} color="#276221" />
              <h2 style={{ fontSize: '1.5rem', margin: 0, color: '#1e293b' }}>
                Providers Filter History <span style={{ fontSize: '0.85rem', background: '#ffffff', color: '#276221', padding: '3px 10px', borderRadius: '12px', border: '1px solid #276221', fontWeight: 600 }}>ML System Audit Node</span>
              </h2>
            </div>
            <p style={{ color: '#64748b', fontSize: '0.88rem', margin: 0 }}>
              Full audit trail of ML provider filtering pipeline, weather risk evaluations, and spatial provider recommendations (`filter_requests` RTDB node). Restricted to System Administrator access only.
            </p>
          </div>

          <button 
            className="btn btn-outline"
            onClick={onRefresh}
            style={{ padding: '8px 16px', fontSize: '0.85rem', borderColor: '#276221', color: '#276221', background: '#ffffff' }}
          >
            <RefreshCw size={14} color="#276221" /> Refresh History
          </button>
        </div>
      </div>

      {/* Overview Metric Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        <div className="glass-panel" style={{ padding: '18px', background: '#ffffff', border: '1px solid #276221' }}>
          <div style={{ fontSize: '0.78rem', color: '#276221', marginBottom: '6px', fontWeight: 700 }}>Total Filter Requests</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#276221' }}>{totalCount}</div>
          <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '4px' }}>Recorded in `filter_requests` node</div>
        </div>

        <div className="glass-panel" style={{ padding: '18px', background: '#ffffff', border: '1px solid #276221' }}>
          <div style={{ fontSize: '0.78rem', color: '#276221', marginBottom: '6px', fontWeight: 700 }}>Low Weather Risk</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#276221' }}>{lowRiskCount}</div>
          <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '4px' }}>Safe indoor/outdoor conditions</div>
        </div>

        <div className="glass-panel" style={{ padding: '18px', background: '#ffffff', border: '1px solid #276221' }}>
          <div style={{ fontSize: '0.78rem', color: '#276221', marginBottom: '6px', fontWeight: 700 }}>Moderate / High Risk</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#276221' }}>{moderateHighRiskCount}</div>
          <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '4px' }}>Rain or extreme weather warnings</div>
        </div>

        <div className="glass-panel" style={{ padding: '18px', background: '#ffffff', border: '1px solid #276221' }}>
          <div style={{ fontSize: '0.78rem', color: '#276221', marginBottom: '6px', fontWeight: 700 }}>Evaluated Providers</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#276221' }}>{totalEvaluatedProvidersCount}</div>
          <div style={{ fontSize: '0.74rem', color: '#64748b', marginTop: '4px' }}>Total ML distance & status matches</div>
        </div>
      </div>

      {/* Filter Toolbar: Date Range Picker, Presets, Risk Level & Search */}
      <div className="glass-panel" style={{ padding: '22px', background: '#ffffff', border: '1px solid #276221' }}>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '18px' }}>
          
          {/* Start Date */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: '#276221', marginBottom: '6px', fontWeight: 600 }}>
              <Calendar size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} color="#276221" /> Start Date
            </label>
            <input 
              type="date" 
              className="form-control"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              style={{ fontSize: '0.85rem', borderColor: '#276221' }}
            />
          </div>

          {/* End Date */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: '#276221', marginBottom: '6px', fontWeight: 600 }}>
              <Calendar size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} color="#276221" /> End Date
            </label>
            <input 
              type="date" 
              className="form-control"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              style={{ fontSize: '0.85rem', borderColor: '#276221' }}
            />
          </div>

          {/* Risk Level Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: '#276221', marginBottom: '6px', fontWeight: 600 }}>
              <Filter size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} color="#276221" /> Weather Risk Level
            </label>
            <select 
              className="form-control"
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              style={{ fontSize: '0.85rem', borderColor: '#276221' }}
            >
              <option value="ALL">All Risk Levels</option>
              <option value="LOW_RISK">Low Risk Only</option>
              <option value="MODERATE_RISK">Moderate Risk Only</option>
              <option value="HIGH_RISK">High Risk Only</option>
            </select>
          </div>

          {/* Text Search */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: '#276221', marginBottom: '6px', fontWeight: 600 }}>
              <Search size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} color="#276221" /> Search Request / Provider
            </label>
            <input 
              type="text"
              className="form-control"
              placeholder="Request ID, Customer, Provider..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ fontSize: '0.85rem', borderColor: '#276221' }}
            />
          </div>
        </div>

        {/* Preset Date Buttons & Active Filters Bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', borderTop: '1px solid #e2e8f0', paddingTop: '14px' }}>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.78rem', color: '#276221', fontWeight: 600 }}>Quick Date Presets:</span>
            <button 
              type="button" 
              className="btn btn-outline" 
              style={{ padding: '4px 10px', fontSize: '0.75rem', borderRadius: '12px', borderColor: '#276221', color: '#276221', background: '#ffffff' }}
              onClick={() => handleSetPreset('ALL')}
            >
              All Time
            </button>
            <button 
              type="button" 
              className="btn btn-outline" 
              style={{ padding: '4px 10px', fontSize: '0.75rem', borderRadius: '12px', borderColor: '#276221', color: '#276221', background: '#ffffff' }}
              onClick={() => handleSetPreset('TODAY')}
            >
              Today
            </button>
            <button 
              type="button" 
              className="btn btn-outline" 
              style={{ padding: '4px 10px', fontSize: '0.75rem', borderRadius: '12px', borderColor: '#276221', color: '#276221', background: '#ffffff' }}
              onClick={() => handleSetPreset('7DAYS')}
            >
              Last 7 Days
            </button>
            <button 
              type="button" 
              className="btn btn-outline" 
              style={{ padding: '4px 10px', fontSize: '0.75rem', borderRadius: '12px', borderColor: '#276221', color: '#276221', background: '#ffffff' }}
              onClick={() => handleSetPreset('30DAYS')}
            >
              Last 30 Days
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
              Showing <strong>{filteredRequests.length}</strong> of <strong>{totalCount}</strong> filter request logs
            </span>
            {(startDate || endDate || riskFilter !== 'ALL' || searchQuery) && (
              <button
                type="button"
                className="btn"
                onClick={handleResetFilters}
                style={{ padding: '4px 12px', fontSize: '0.75rem', background: '#ffffff', border: '1px solid #276221', color: '#276221', borderRadius: '12px', fontWeight: 600 }}
              >
                Clear Filters
              </button>
            )}
          </div>

        </div>
      </div>

      {/* History Log Records List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px' }}>
          <p style={{ color: '#276221', fontWeight: 600 }}>Loading filter_requests history node from Realtime Database...</p>
        </div>
      ) : filteredRequests.length === 0 ? (
        <div className="glass-panel" style={{ textAlign: 'center', padding: '50px', color: '#64748b', background: '#ffffff', border: '1px solid #276221' }}>
          <ShieldCheck size={36} style={{ marginBottom: '12px', opacity: 0.8 }} color="#276221" />
          <h3 style={{ color: '#1e293b' }}>No filter request logs match your date range or search query</h3>
          <p style={{ fontSize: '0.88rem', marginTop: '6px' }}>
            Try adjusting your Start Date, End Date, or Risk Level filters above.
          </p>
          <button 
            type="button" 
            className="btn btn-primary" 
            style={{ marginTop: '14px', padding: '8px 18px', fontSize: '0.85rem', background: '#276221', borderColor: '#276221' }}
            onClick={handleResetFilters}
          >
            Reset All Filters
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {filteredRequests.map((item) => {
            const reqId = item.request_id || item.id || 'Unknown_ID';
            const output = item.output_results;
            const evalProviders = output?.evaluated_providers || [];
            const customerObj = customerMap[item.user_id];
            const riskBadge = getRiskBadgeStyle(output?.weather_risk);
            const isExpanded = expandedRequestId === reqId;

            // Formatted date string
            const evalDateStr = output?.evaluated_at ? new Date(output.evaluated_at).toLocaleString() : item.service_date;

            return (
              <div 
                key={reqId} 
                className="glass-panel" 
                style={{ 
                  padding: '20px', 
                  background: '#ffffff',
                  border: '1px solid #276221',
                  transition: 'all 0.2s ease'
                }}
              >
                {/* Header row for item */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '14px' }}>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#276221', background: '#ffffff', padding: '4px 10px', borderRadius: '8px', border: '1px solid #276221', fontFamily: 'monospace' }}>
                      🔑 {reqId}
                    </span>

                    {/* Location Type Badge */}
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '3px 10px', borderRadius: '10px', textTransform: 'uppercase', background: '#ffffff', color: '#276221', border: '1px solid #276221' }}>
                      🏡 {item.location_type || 'indoor'} service
                    </span>

                    {/* Weather Risk Badge */}
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '3px 10px', borderRadius: '10px', display: 'inline-flex', alignItems: 'center', gap: '5px', background: riskBadge.bg, border: riskBadge.border, color: riskBadge.color }}>
                      {riskBadge.icon} {output?.weather_risk || 'RISK_EVALUATED'}
                    </span>
                  </div>

                  {/* Timestamp & Expand Action */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                      <Clock size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} color="#276221" />
                      Evaluated: <strong>{evalDateStr}</strong>
                    </span>

                    <button
                      type="button"
                      className="btn btn-outline"
                      style={{ padding: '5px 12px', fontSize: '0.78rem', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '6px', borderColor: '#276221', color: '#276221', background: '#ffffff' }}
                      onClick={() => toggleExpand(reqId)}
                    >
                      {isExpanded ? <>Collapse <ChevronUp size={14} color="#276221" /></> : <>Inspect ({evalProviders.length} Providers) <ChevronDown size={14} color="#276221" /></>}
                    </button>
                  </div>
                </div>

                {/* Request Details Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px', fontSize: '0.85rem', marginBottom: '14px', background: '#ffffff', padding: '12px 16px', borderRadius: '10px', border: '1px solid #276221' }}>
                  
                  <div>
                    <span style={{ color: '#276221', display: 'block', fontSize: '0.75rem', fontWeight: 600 }}>Customer / Requester</span>
                    <strong style={{ color: '#1e293b' }}>{customerObj ? customerObj.fullName : 'Customer ID: ' + item.user_id}</strong>
                    {customerObj && (
                      <span style={{ display: 'block', fontSize: '0.74rem', color: '#64748b' }}>
                        📍 {customerObj.city}, {customerObj.district}
                      </span>
                    )}
                  </div>

                  <div>
                    <span style={{ color: '#276221', display: 'block', fontSize: '0.75rem', fontWeight: 600 }}>Scheduled Service Window</span>
                    <strong style={{ color: '#1e293b' }}>📅 {item.service_date || 'N/A'}</strong>
                    {item.service_time && (
                      <span style={{ display: 'block', fontSize: '0.74rem', color: '#64748b' }}>
                        ⏰ {item.service_time.start_time} - {item.service_time.end_time}
                      </span>
                    )}
                  </div>

                  <div>
                    <span style={{ color: '#276221', display: 'block', fontSize: '0.75rem', fontWeight: 600 }}>Weather Forecast Summary</span>
                    <span style={{ color: '#1e293b', fontSize: '0.8rem' }}>
                      <CloudSun size={13} style={{ verticalAlign: 'middle', marginRight: '4px' }} color="#276221" />
                      {output?.weather_summary || 'Weather forecast processed by ML pipeline'}
                    </span>
                  </div>

                </div>

                {/* Main ML Model System Recommendation Banner */}
                {output?.recommendation && (
                  <div style={{ background: '#ffffff', border: '1px solid #276221', borderRadius: '10px', padding: '12px 14px', marginBottom: '14px', fontSize: '0.84rem' }}>
                    <strong style={{ color: '#276221', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                      <Sparkles size={15} color="#276221" /> ML System Model Recommendation:
                    </strong>
                    <span style={{ color: '#1e293b' }}>{output.recommendation}</span>
                  </div>
                )}

                {/* Inline Evaluated Providers Grid / Details (Expanded by Default or Click) */}
                <div style={{ display: isExpanded ? 'block' : 'none', marginTop: '16px', paddingTop: '16px', borderTop: '1px dashed #cbd5e1' }}>
                  <h4 style={{ fontSize: '0.9rem', color: '#276221', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Building2 size={16} color="#276221" /> Evaluated Service Providers ({evalProviders.length})
                  </h4>

                  {evalProviders.length === 0 ? (
                    <p style={{ fontSize: '0.82rem', color: '#64748b' }}>No provider evaluations recorded for this request.</p>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(310px, 1fr))', gap: '12px' }}>
                      {evalProviders.map((ep, idx) => {
                        const provProfile = providerMap[ep.provider_id];

                        return (
                          <div 
                            key={ep.provider_id + '_' + idx}
                            style={{
                              background: '#ffffff',
                              border: '1px solid #276221',
                              borderRadius: '12px',
                              padding: '14px',
                              fontSize: '0.82rem'
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                              <strong style={{ fontSize: '0.92rem', color: '#1e293b' }}>
                                {ep.provider_name || (provProfile ? provProfile.fullName : 'Provider ' + ep.provider_id.substring(0, 6))}
                              </strong>

                              <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '2px 8px', borderRadius: '8px', background: '#ffffff', border: '1px solid #276221', color: '#276221' }}>
                                {ep.is_available ? 'Available' : 'Unavailable'}
                              </span>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', color: '#64748b', marginBottom: '8px' }}>
                              <div>📍 Distance: <strong style={{ color: '#276221' }}>{ep.distance_km !== undefined ? ep.distance_km + ' km' : 'N/A'}</strong></div>
                              {ep.service_day && <div>📅 Service Day: <strong>{ep.service_day}</strong></div>}
                              {ep.working_hours_status && (
                                <div style={{ fontSize: '0.76rem', color: '#1e293b' }}>
                                  🕒 {ep.working_hours_status}
                                </div>
                              )}
                              {ep.provider_location && (
                                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>
                                  Lat {ep.provider_location.latitude}, Lng {ep.provider_location.longitude}
                                </div>
                              )}
                            </div>

                            {ep.recommendation && (
                              <div style={{ marginTop: '6px', background: '#ffffff', padding: '8px 10px', borderRadius: '6px', borderLeft: '3px solid #276221', border: '1px solid #276221', fontSize: '0.78rem', color: '#1e293b' }}>
                                {ep.recommendation}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

              </div>
            );
          })}
        </div>
      )}

    </div>
  );
};
