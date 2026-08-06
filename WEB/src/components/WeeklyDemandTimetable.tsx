import React, { useState } from 'react';
import {
  Calendar,
  RefreshCw,
  Search,
  Filter,
  TrendingUp,
  Award,
  BarChart3,
  Grid,
  Layers,
  Sparkles,
  Zap,
  Info,
  ArrowUpDown,
  Flame,
  CheckCircle2
} from 'lucide-react';
import type { DailyDemandData, DailyDemandCategoryItem } from '../config/firebase';

interface WeeklyDemandTimetableProps {
  demandData: DailyDemandData | null;
  loading: boolean;
  onRefresh: () => void;
}

const DAYS_OF_WEEK: Array<{ key: 'Monday' | 'Tuesday' | 'Wednesday' | 'Thursday' | 'Friday' | 'Saturday' | 'Sunday'; label: string; short: string; isWeekend?: boolean }> = [
  { key: 'Monday', label: 'Monday', short: 'Mon' },
  { key: 'Tuesday', label: 'Tuesday', short: 'Tue' },
  { key: 'Wednesday', label: 'Wednesday', short: 'Wed' },
  { key: 'Thursday', label: 'Thursday', short: 'Thu' },
  { key: 'Friday', label: 'Friday', short: 'Fri' },
  { key: 'Saturday', label: 'Saturday', short: 'Sat', isWeekend: true },
  { key: 'Sunday', label: 'Sunday', short: 'Sun', isWeekend: true },
];

export const WeeklyDemandTimetable: React.FC<WeeklyDemandTimetableProps> = ({
  demandData,
  loading,
  onRefresh
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [levelFilter, setLevelFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [viewMode, setViewMode] = useState<'timetable' | 'cards'>('timetable');
  const [sortBy, setSortBy] = useState<'total_weekly' | 'category' | 'avg_daily'>('total_weekly');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Process and normalize category demand records
  const getNormalizedCategories = (): DailyDemandCategoryItem[] => {
    if (!demandData) return [];

    if (demandData.by_category) {
      return Object.values(demandData.by_category).map(item => ({
        id: item.id,
        service_category: item.service_category || 'Unknown',
        Monday: item.Monday || 0,
        Tuesday: item.Tuesday || 0,
        Wednesday: item.Wednesday || 0,
        Thursday: item.Thursday || 0,
        Friday: item.Friday || 0,
        Saturday: item.Saturday || 0,
        Sunday: item.Sunday || 0,
        total_weekly: item.total_weekly || (item.Monday + item.Tuesday + item.Wednesday + item.Thursday + item.Friday + item.Saturday + item.Sunday),
        avg_daily: item.avg_daily || Math.round(((item.total_weekly || 0) / 7) * 10) / 10,
        demand_level: item.demand_level || 'MEDIUM'
      }));
    }

    if (demandData.summary && Array.isArray(demandData.summary)) {
      return demandData.summary.map(s => ({
        service_category: s["Service Category"] || 'Unknown',
        Monday: s.Monday || 0,
        Tuesday: s.Tuesday || 0,
        Wednesday: s.Wednesday || 0,
        Thursday: s.Thursday || 0,
        Friday: s.Friday || 0,
        Saturday: s.Saturday || 0,
        Sunday: s.Sunday || 0,
        total_weekly: s["Total Weekly Orders"] || 0,
        avg_daily: s["Avg Daily Orders"] || 0,
        demand_level: s["Weekly Demand Level"] || 'MEDIUM'
      }));
    }

    return [];
  };

  const allCategories = getNormalizedCategories();

  // Filter categories by search query & demand level
  const filteredCategories = allCategories.filter(cat => {
    const matchesSearch = !searchQuery || cat.service_category.toLowerCase().includes(searchQuery.trim().toLowerCase());
    const matchesLevel = levelFilter === 'ALL' || cat.demand_level.toUpperCase() === levelFilter;
    return matchesSearch && matchesLevel;
  });

  // Sort categories
  const sortedCategories = [...filteredCategories].sort((a, b) => {
    let comparison = 0;
    if (sortBy === 'total_weekly') {
      comparison = a.total_weekly - b.total_weekly;
    } else if (sortBy === 'avg_daily') {
      comparison = a.avg_daily - b.avg_daily;
    } else if (sortBy === 'category') {
      comparison = a.service_category.localeCompare(b.service_category);
    }
    return sortOrder === 'desc' ? -comparison : comparison;
  });

  // Overall Statistics Calculations
  const grandTotalWeeklyOrders = allCategories.reduce((sum, c) => sum + c.total_weekly, 0);
  const avgDailySystemOrders = Math.round((grandTotalWeeklyOrders / 7) * 10) / 10;

  const highestCategory = allCategories.length > 0
    ? [...allCategories].sort((a, b) => b.total_weekly - a.total_weekly)[0]
    : null;

  // Find peak day across all categories
  const dayTotals = DAYS_OF_WEEK.reduce((acc, day) => {
    acc[day.key] = allCategories.reduce((sum, cat) => sum + (cat[day.key] || 0), 0);
    return acc;
  }, {} as Record<string, number>);

  const peakDayKey = Object.keys(dayTotals).length > 0
    ? Object.keys(dayTotals).reduce((maxDay, currentDay) => dayTotals[currentDay] > dayTotals[maxDay] ? currentDay : maxDay, 'Monday')
    : 'Monday';

  // Toggle sort helper
  const handleSortToggle = (type: 'total_weekly' | 'category' | 'avg_daily') => {
    if (sortBy === type) {
      setSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(type);
      setSortOrder('desc');
    }
  };

  // Helper for cell heatmap intensity
  const getDemandCellStyle = (val: number, maxVal: number) => {
    const isPeak = val === maxVal && val > 0;
    let bg = '#f8fafc';
    let color = '#334155';
    let border = '1px solid #e2e8f0';

    if (val >= 30) {
      bg = '#fee2e2';
      color = '#991b1b';
      border = '1px solid #fca5a5';
    } else if (val >= 20) {
      bg = '#fef3c7';
      color = '#92400e';
      border = '1px solid #fcd34d';
    } else if (val >= 10) {
      bg = '#dbeafe';
      color = '#1e40af';
      border = '1px solid #93c5fd';
    } else {
      bg = '#e8f5e9';
      color = '#276221';
      border = '1px solid #c8e6c9';
    }

    if (isPeak) {
      border = '2px solid #f59e0b';
      bg = '#fef3c7';
      color = '#b45309';
    }

    return { bg, color, border, fontWeight: isPeak ? 700 : 500, isPeak };
  };


  // Helper to render Demand Level Badge
  const renderDemandBadge = (level: string) => {
    const l = level.toUpperCase();
    if (l === 'HIGH') {
      return (
        <span style={{
          padding: '4px 10px',
          borderRadius: '12px',
          fontSize: '0.75rem',
          fontWeight: 700,
          background: 'rgba(239, 68, 68, 0.2)',
          color: '#ef4444',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px'
        }}>
          <Flame size={12} /> HIGH
        </span>
      );
    }
    if (l === 'LOW') {
      return (
        <span style={{
          padding: '4px 10px',
          borderRadius: '12px',
          fontSize: '0.75rem',
          fontWeight: 700,
          background: 'rgba(39, 98, 33, 0.12)',
          color: '#276221',
          border: '1px solid #276221',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px'
        }}>
          <CheckCircle2 size={12} /> LOW
        </span>
      );
    }
    return (
      <span style={{
        padding: '4px 10px',
        borderRadius: '12px',
        fontSize: '0.75rem',
        fontWeight: 700,
        background: 'rgba(245, 158, 11, 0.2)',
        color: '#f59e0b',
        border: '1px solid rgba(245, 158, 11, 0.4)',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px'
      }}>
        <Zap size={12} /> MEDIUM
      </span>
    );
  };

  return (
    <div style={{ width: '100%' }}>
      {/* Header Banner */}
      <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px', background: 'var(--bg-card)', borderLeft: '6px solid var(--primary)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <Calendar size={26} color="#276221" />
              <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#1e293b' }}>Weekly Demand Timetable</h2>
            </div>
            <p style={{ color: '#64748b', fontSize: '0.92rem' }}>
              Monday to Sunday forecasted service demand schedule generated from machine learning predictions.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <button
              className="btn btn-outline"
              onClick={onRefresh}
              disabled={loading}
              style={{ padding: '8px 14px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px', borderColor: '#276221', color: '#276221' }}
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} /> {loading ? 'Fetching...' : 'Refresh Demand Node'}
            </button>
          </div>
        </div>

        {/* Metadata Bar */}
        {demandData && (
          <div style={{ marginTop: '18px', paddingTop: '16px', borderTop: '1px solid #e2e8f0', display: 'flex', flexWrap: 'wrap', gap: '20px', fontSize: '0.85rem', color: '#64748b' }}>
            <div>📅 <strong>Target Week:</strong> <span style={{ color: '#1e293b', fontWeight: 600 }}>{demandData.target_week || `${demandData.start_date} to ${demandData.end_date}`}</span></div>
            <div>🗓️ <strong>Compiled Date:</strong> <span style={{ color: '#1e293b', fontWeight: 600 }}>{demandData.compile_date || 'N/A'}</span></div>
            <div>🕒 <strong>Last Updated:</strong> <span style={{ color: '#1e293b', fontWeight: 600 }}>{demandData.last_updated ? new Date(demandData.last_updated).toLocaleString() : 'N/A'}</span></div>
          </div>
        )}
      </div>

      {/* Metric Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>

        {/* Total Weekly Forecast */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '16px', background: 'var(--bg-card)', border: '1px solid var(--bg-card-border)' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'rgba(68, 158, 57, 0.15)', border: '1px solid rgba(68, 158, 57, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--primary)', flexShrink: 0 }}>
            <TrendingUp size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontWeight: 600 }}>Weekly Total Orders</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-main)' }}>{grandTotalWeeklyOrders.toLocaleString()}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--primary)' }}>Forecasted across 7 days</div>
          </div>
        </div>

        {/* Average Daily Orders */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '16px', background: 'var(--bg-card)', border: '1px solid var(--bg-card-border)' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'rgba(68, 158, 57, 0.15)', border: '1px solid rgba(68, 158, 57, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--primary)', flexShrink: 0 }}>
            <BarChart3 size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontWeight: 600 }}>Daily System Average</div>
            <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-main)' }}>{avgDailySystemOrders.toLocaleString()}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--primary)' }}>Orders per day</div>
          </div>
        </div>

        {/* Peak Demand Category */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '16px', background: 'var(--bg-card)', border: '1px solid var(--bg-card-border)' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ef4444', flexShrink: 0 }}>
            <Award size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontWeight: 600 }}>Highest Demand Category</div>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-main)' }}>{highestCategory ? highestCategory.service_category : 'N/A'}</div>
            <div style={{ fontSize: '0.75rem', color: '#ef4444' }}>{highestCategory ? `${highestCategory.total_weekly} orders/week` : ''}</div>
          </div>
        </div>

        {/* Peak Demand Day */}
        <div className="glass-panel" style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '16px', background: 'var(--bg-card)', border: '1px solid var(--bg-card-border)' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#f59e0b', flexShrink: 0 }}>
            <Sparkles size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontWeight: 600 }}>Peak Demand Day</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-main)' }}>{peakDayKey}</div>
            <div style={{ fontSize: '0.75rem', color: '#f59e0b' }}>{dayTotals[peakDayKey] ? `${dayTotals[peakDayKey]} total daily orders` : ''}</div>
          </div>
        </div>

      </div>

      {/* Control Bar: Search, Filters & View Toggle */}
      <div className="glass-panel" style={{ padding: '18px 22px', marginBottom: '24px', background: 'var(--bg-card)', border: '1px solid var(--bg-card-border)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'center', justifyContent: 'space-between' }}>

          {/* Search Box */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: '1', minWidth: '240px' }}>
            <div style={{ position: 'relative', width: '100%' }}>
              <Search size={16} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                className="form-control"
                placeholder="Search category (e.g. Electricians, Plumbers)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ paddingLeft: '38px', fontSize: '0.9rem', border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--text-main)' }}
              />
            </div>
          </div>

          {/* Level Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Filter size={16} color="var(--primary)" />
            <select
              className="form-control"
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value as any)}
              style={{ fontSize: '0.86rem', padding: '8px 12px', border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--text-main)' }}
            >
              <option value="ALL" style={{ background: 'var(--bg-card)', color: 'var(--text-main)' }}>All Demand Levels</option>
              <option value="HIGH" style={{ background: 'var(--bg-card)', color: 'var(--text-main)' }}>High Demand (&gt; 25/day)</option>
              <option value="MEDIUM" style={{ background: 'var(--bg-card)', color: 'var(--text-main)' }}>Medium Demand (11 - 25/day)</option>
              <option value="LOW" style={{ background: 'var(--bg-card)', color: 'var(--text-main)' }}>Low Demand (≤ 10/day)</option>
            </select>
          </div>

          {/* View Mode Toggle */}
          <div style={{ display: 'flex', background: 'var(--bg-secondary)', padding: '4px', borderRadius: '10px', border: '1px solid var(--input-border)' }}>
            <button
              onClick={() => setViewMode('timetable')}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                border: 'none',
                background: viewMode === 'timetable' ? 'var(--primary)' : 'transparent',
                color: viewMode === 'timetable' ? '#fff' : 'var(--text-muted)',
                fontWeight: 600,
                fontSize: '0.82rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Grid size={15} /> Matrix Grid
            </button>
            <button
              onClick={() => setViewMode('cards')}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                border: 'none',
                background: viewMode === 'cards' ? 'var(--primary)' : 'transparent',
                color: viewMode === 'cards' ? '#fff' : 'var(--text-muted)',
                fontWeight: 600,
                fontSize: '0.82rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <Layers size={15} /> Category Cards
            </button>
          </div>

        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>Loading `daily_demand` node data from Firebase...</p>
        </div>
      ) : sortedCategories.length === 0 ? (
        <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>
          <Info size={36} style={{ marginBottom: '12px', color: '#94a3b8' }} />
          <h3>No Demand Data Found</h3>
          <p style={{ fontSize: '0.88rem', marginTop: '6px' }}>No categories match your search filter or Firebase node is currently empty.</p>
        </div>
      ) : viewMode === 'timetable' ? (
        /* TIMETABLE MATRIX GRID VIEW */
        <div className="glass-panel" style={{ overflowX: 'auto', padding: '0', borderRadius: '16px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
            <thead>
              <tr style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--input-border)' }}>
                <th
                  onClick={() => handleSortToggle('category')}
                  style={{ padding: '14px 18px', cursor: 'pointer', userSelect: 'none', color: 'var(--text-main)' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    Service Category <ArrowUpDown size={14} color="var(--text-muted)" />
                  </div>
                </th>

                {DAYS_OF_WEEK.map(d => (
                  <th
                    key={d.key}
                    style={{
                      padding: '14px 12px',
                      textAlign: 'center',
                      background: d.isWeekend ? 'rgba(68, 158, 57, 0.15)' : 'transparent',
                      color: d.isWeekend ? 'var(--primary)' : 'var(--text-main)'
                    }}
                  >
                    <div>{d.label}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400 }}>{d.isWeekend ? 'Weekend' : 'Weekday'}</div>
                  </th>
                ))}

                <th
                  onClick={() => handleSortToggle('total_weekly')}
                  style={{ padding: '14px 14px', textAlign: 'center', cursor: 'pointer', userSelect: 'none', background: 'var(--bg-secondary)', color: 'var(--text-main)' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                    Total Orders <ArrowUpDown size={14} color="var(--text-muted)" />
                  </div>
                </th>

                <th
                  onClick={() => handleSortToggle('avg_daily')}
                  style={{ padding: '14px 14px', textAlign: 'center', cursor: 'pointer', userSelect: 'none', color: 'var(--text-main)' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}>
                    Avg Daily <ArrowUpDown size={14} color="var(--text-muted)" />
                  </div>
                </th>

                <th style={{ padding: '14px 16px', textAlign: 'center', color: 'var(--text-main)' }}>Demand Level</th>
              </tr>
            </thead>

            <tbody>
              {sortedCategories.map((cat, idx) => {
                const dayKeys = DAYS_OF_WEEK.map(d => d.key);
                const maxVal = Math.max(...dayKeys.map(k => cat[k] || 0));

                return (
                  <tr
                    key={cat.id || cat.service_category}
                    style={{
                      borderBottom: '1px solid var(--bg-card-border)',
                      background: idx % 2 === 0 ? 'var(--bg-card)' : 'var(--input-bg)'
                    }}
                  >
                    {/* Category Title */}
                    <td style={{ padding: '14px 18px', fontWeight: 600, color: 'var(--text-main)', whiteSpace: 'nowrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: cat.demand_level === 'HIGH' ? '#ef4444' : cat.demand_level === 'LOW' ? 'var(--primary)' : '#f59e0b' }} />
                        {cat.service_category}
                      </div>
                    </td>

                    {/* Monday to Sunday Daily Cells */}
                    {DAYS_OF_WEEK.map(d => {
                      const val = cat[d.key] || 0;
                      const style = getDemandCellStyle(val, maxVal);

                      return (
                        <td
                          key={d.key}
                          style={{
                            padding: '12px 8px',
                            textAlign: 'center',
                            fontWeight: style.fontWeight as any,
                            fontSize: '0.86rem'
                          }}
                        >
                          <div style={{
                            padding: '6px 8px',
                            borderRadius: '8px',
                            background: style.bg,
                            color: style.color,
                            border: style.border,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '4px',
                            minWidth: '44px'
                          }}>
                            {style.isPeak && <Sparkles size={11} color="#f59e0b" />}
                            <span className="demand-cell-num">{val}</span>
                          </div>
                        </td>
                      );
                    })}

                    {/* Total Weekly Orders */}
                    <td style={{ padding: '14px 14px', textAlign: 'center', fontWeight: 800, fontSize: '0.95rem', color: 'var(--primary)', background: 'var(--bg-secondary)' }}>
                      {cat.total_weekly}
                    </td>

                    {/* Avg Daily Orders */}
                    <td style={{ padding: '14px 14px', textAlign: 'center', fontWeight: 700, fontSize: '0.88rem', color: 'var(--text-muted)' }}>
                      {cat.avg_daily}
                    </td>

                    {/* Demand Level Badge */}
                    <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                      {renderDemandBadge(cat.demand_level)}
                    </td>
                  </tr>
                );
              })}
            </tbody>

            {/* Timetable Summary Footer Totals Row */}
            <tfoot>
              <tr style={{ background: 'var(--bg-secondary)', borderTop: '2px solid var(--input-border)', fontWeight: 800 }}>
                <td style={{ padding: '16px 18px', color: 'var(--primary)' }}>
                  SUMMARY TOTALS ({sortedCategories.length} Categories)
                </td>

                {DAYS_OF_WEEK.map(d => {
                  const daySum = sortedCategories.reduce((sum, c) => sum + (c[d.key] || 0), 0);
                  const isGlobalPeak = d.key === peakDayKey;

                  return (
                    <td key={d.key} style={{ padding: '16px 10px', textAlign: 'center' }}>
                      <div style={{
                        padding: '6px 8px',
                        borderRadius: '8px',
                        background: isGlobalPeak ? 'rgba(245, 158, 11, 0.25)' : 'rgba(99, 102, 241, 0.15)',
                        color: isGlobalPeak ? '#fcd34d' : '#a5b4fc',
                        border: isGlobalPeak ? '1px solid rgba(245, 158, 11, 0.5)' : '1px solid rgba(99, 102, 241, 0.3)',
                        fontSize: '0.9rem',
                        fontWeight: 800
                      }}>
                        {daySum}
                      </div>
                    </td>
                  );
                })}

                <td style={{ padding: '16px 14px', textAlign: 'center', color: 'var(--accent-customer)', fontSize: '1rem' }}>
                  {sortedCategories.reduce((sum, c) => sum + c.total_weekly, 0)}
                </td>

                <td style={{ padding: '16px 14px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  {Math.round((sortedCategories.reduce((sum, c) => sum + c.avg_daily, 0) / (sortedCategories.length || 1)) * 10) / 10}
                </td>

                <td style={{ padding: '16px 16px', textAlign: 'center' }}>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>7-Day Matrix</span>
                </td>
              </tr>
            </tfoot>

          </table>
        </div>
      ) : (
        /* CATEGORY CARDS VIEW */
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {sortedCategories.map(cat => {
            const maxVal = Math.max(...DAYS_OF_WEEK.map(d => cat[d.key] || 0));

            return (
              <div key={cat.service_category} className="glass-panel glass-panel-hover" style={{ padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>{cat.service_category}</h3>
                    {renderDemandBadge(cat.demand_level)}
                  </div>

                  <div style={{ display: 'flex', gap: '16px', marginBottom: '18px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    <div>Total Orders: <strong style={{ color: 'var(--accent-customer)' }}>{cat.total_weekly}</strong></div>
                    <div>Avg Daily: <strong style={{ color: 'var(--text-main)' }}>{cat.avg_daily}</strong></div>
                  </div>

                  {/* Daily Distribution Timetable Bar Graph */}
                  <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>Monday - Sunday Daily Forecast</div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '6px', alignItems: 'flex-end', height: '70px', padding: '8px 0', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                      {DAYS_OF_WEEK.map(d => {
                        const val = cat[d.key] || 0;
                        const heightPct = maxVal > 0 ? Math.max(15, Math.round((val / maxVal) * 100)) : 10;
                        const isPeak = val === maxVal && val > 0;

                        return (
                          <div key={d.key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                            <div style={{ fontSize: '0.68rem', color: isPeak ? '#fcd34d' : 'var(--text-dim)', fontWeight: 700, marginBottom: '2px' }}>
                              {val}
                            </div>
                            <div style={{
                              width: '100%',
                              height: `${heightPct}%`,
                              borderRadius: '4px 4px 0 0',
                              background: isPeak
                                ? 'linear-gradient(180deg, #f59e0b 0%, #d97706 100%)'
                                : d.isWeekend
                                  ? 'linear-gradient(180deg, #818cf8 0%, #4f46e5 100%)'
                                  : 'linear-gradient(180deg, #38bdf8 0%, #0284c7 100%)'
                            }} />
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '4px', textTransform: 'uppercase' }}>
                              {d.short}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: '14px', paddingTop: '10px', borderTop: '1px solid rgba(255, 255, 255, 0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                  <span>⭐ Peak: {DAYS_OF_WEEK.find(d => cat[d.key] === maxVal)?.label || 'N/A'}</span>
                  <span>7-Day Dispatch Target</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Legend & Context Footer */}
      <div className="glass-panel" style={{ marginTop: '24px', padding: '16px 20px', border: '1px solid var(--input-border)', background: 'var(--bg-card)', fontSize: '0.82rem', color: 'var(--text-muted)', display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <strong>Legend:</strong>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>🔥 HIGH (&gt; 25 orders/day)</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>⚡ MEDIUM (11 - 25 orders/day)</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>✅ LOW (≤ 10 orders/day)</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#f59e0b', fontWeight: 600 }}>⭐ PEAK (Highest demand day per service)</span>
        </div>

        <div></div>
      </div>
    </div>
  );
};
