import React, { useEffect, useState } from 'react';
import { 
  Calendar, 
  TrendingUp, 
  Flame, 
  CheckCircle2, 
  Zap, 
  Clock, 
  Sparkles, 
  Info,
  RefreshCw,
  Award
} from 'lucide-react';
import { fetchDailyDemand } from '../config/firebase';
import type { DailyDemandData, DailyDemandCategoryItem } from '../config/firebase';

interface ProviderCategoryDemandWidgetProps {
  category: string;
  providerName?: string;
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

export const ProviderCategoryDemandWidget: React.FC<ProviderCategoryDemandWidgetProps> = ({
  category,
  providerName
}) => {
  const [demandData, setDemandData] = useState<DailyDemandData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [matchedCategoryItem, setMatchedCategoryItem] = useState<DailyDemandCategoryItem | null>(null);

  const loadDemand = async () => {
    setLoading(true);
    try {
      const data = await fetchDailyDemand();
      setDemandData(data);
      if (data) {
        findCategoryMatch(data, category);
      }
    } catch (err) {
      console.error("Error loading provider category demand data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDemand();
  }, [category]);

  // Robust category matching logic
  const findCategoryMatch = (data: DailyDemandData, targetCat: string) => {
    if (!targetCat) return;

    const query = targetCat.trim().toLowerCase();

    // Check by_category dict
    if (data.by_category) {
      const categories = Object.values(data.by_category);
      let match = categories.find(c => c.service_category.toLowerCase() === query);
      
      if (!match) {
        match = categories.find(c => 
          c.service_category.toLowerCase().includes(query) || 
          query.includes(c.service_category.toLowerCase()) ||
          c.service_category.replace(/[^a-zA-Z0-9]/g, '').toLowerCase() === query.replace(/[^a-zA-Z0-9]/g, '').toLowerCase()
        );
      }

      if (match) {
        setMatchedCategoryItem(match);
        return;
      }
    }

    // Check summary array
    if (data.summary && Array.isArray(data.summary)) {
      let match = data.summary.find(s => s["Service Category"].toLowerCase() === query);

      if (!match) {
        match = data.summary.find(s => 
          s["Service Category"].toLowerCase().includes(query) || 
          query.includes(s["Service Category"].toLowerCase())
        );
      }

      if (match) {
        setMatchedCategoryItem({
          service_category: match["Service Category"],
          Monday: match.Monday || 0,
          Tuesday: match.Tuesday || 0,
          Wednesday: match.Wednesday || 0,
          Thursday: match.Thursday || 0,
          Friday: match.Friday || 0,
          Saturday: match.Saturday || 0,
          Sunday: match.Sunday || 0,
          total_weekly: match["Total Weekly Orders"] || 0,
          avg_daily: match["Avg Daily Orders"] || 0,
          demand_level: match["Weekly Demand Level"] || 'MEDIUM'
        });
        return;
      }
    }

    setMatchedCategoryItem(null);
  };

  // Render Demand Level Badge
  const renderDemandBadge = (level: string) => {
    const l = (level || '').toUpperCase();
    if (l === 'HIGH') {
      return (
        <span style={{
          padding: '4px 12px',
          borderRadius: '12px',
          fontSize: '0.8rem',
          fontWeight: 700,
          background: 'rgba(239, 68, 68, 0.2)',
          color: '#ef4444',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px'
        }}>
          <Flame size={14} /> HIGH DEMAND
        </span>
      );
    }
    if (l === 'LOW') {
      return (
        <span style={{
          padding: '4px 12px',
          borderRadius: '12px',
          fontSize: '0.8rem',
          fontWeight: 700,
          background: 'rgba(16, 185, 129, 0.2)',
          color: '#10b981',
          border: '1px solid rgba(16, 185, 129, 0.4)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px'
        }}>
          <CheckCircle2 size={14} /> STABLE DEMAND
        </span>
      );
    }
    return (
      <span style={{
        padding: '4px 12px',
        borderRadius: '12px',
        fontSize: '0.8rem',
        fontWeight: 700,
        background: 'rgba(245, 158, 11, 0.2)',
        color: '#f59e0b',
        border: '1px solid rgba(245, 158, 11, 0.4)',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px'
      }}>
        <Zap size={14} /> MEDIUM DEMAND
      </span>
    );
  };

  if (loading) {
    return (
      <div className="glass-panel" style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <Clock size={24} className="spin" style={{ marginBottom: '8px' }} />
        <p style={{ margin: 0, fontSize: '0.9rem' }}>Loading market demand forecast for {category}...</p>
      </div>
    );
  }

  if (!matchedCategoryItem) {
    return (
      <div className="glass-panel" style={{ padding: '20px', background: 'rgba(15, 23, 42, 0.5)', borderLeft: '4px solid var(--text-muted)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Calendar size={20} color="var(--primary)" />
            <h4 style={{ margin: 0, fontSize: '1.05rem' }}>Weekly Demand Timetable: {category}</h4>
          </div>
          <button className="btn btn-outline" onClick={loadDemand} style={{ padding: '4px 10px', fontSize: '0.78rem' }}>
            <RefreshCw size={12} /> Refresh
          </button>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.86rem', marginTop: '10px', margin: 0 }}>
          No specific demand forecast entry found for category <strong>"{category}"</strong> in the current `daily_demand` node.
        </p>
      </div>
    );
  }

  // Calculate Peak Day & Day values
  const dayValues = DAYS_OF_WEEK.map(d => ({
    ...d,
    val: matchedCategoryItem[d.key] || 0
  }));

  const maxVal = Math.max(...dayValues.map(d => d.val));
  const peakDayObj = dayValues.find(d => d.val === maxVal && maxVal > 0);

  return (
    <div 
      className="glass-panel" 
      style={{ 
        padding: '26px', 
        marginBottom: '30px', 
        background: '#ffffff',
        border: '1px solid #276221',
        borderLeft: '6px solid #276221'
      }}
    >
      {/* Header Bar */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
            <Calendar size={24} color="#276221" />
            <h3 style={{ fontSize: '1.4rem', fontWeight: 700, margin: 0, color: '#1e293b' }}>
              Weekly Demand Timetable ({matchedCategoryItem.service_category})
            </h3>
            {renderDemandBadge(matchedCategoryItem.demand_level)}
          </div>
          <p style={{ color: '#64748b', fontSize: '0.88rem', margin: 0 }}>
            Exclusive Monday to Sunday order demand predictions for <strong>{matchedCategoryItem.service_category}</strong> service providers.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {demandData?.target_week && (
            <span style={{ fontSize: '0.8rem', color: '#64748b', background: '#ffffff', padding: '6px 12px', borderRadius: '10px', border: '1px solid #276221' }}>
              📅 {demandData.target_week}
            </span>
          )}
          <button 
            className="btn btn-outline" 
            onClick={loadDemand} 
            style={{ padding: '6px 12px', fontSize: '0.8rem', borderColor: '#276221', color: '#276221' }}
            title="Refresh demand forecast"
          >
            <RefreshCw size={13} color="#276221" />
          </button>
        </div>
      </div>

      {/* Top Metrics Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', marginBottom: '22px' }}>
        
        {/* Total Weekly Orders */}
        <div style={{ background: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #276221', display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: '#ffffff', border: '1px solid #276221', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10b981', flexShrink: 0 }}>
            <TrendingUp size={22} color="#10b981" />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#276221', fontWeight: 600 }}>Total Weekly Demand</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#10b981' }}>
              {matchedCategoryItem.total_weekly} <span style={{ fontSize: '0.8rem', fontWeight: 500, color: '#64748b' }}>orders</span>
            </div>
          </div>
        </div>

        {/* Avg Daily Orders */}
        <div style={{ background: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #276221', display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: '#ffffff', border: '1px solid #276221', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6366f1', flexShrink: 0 }}>
            <Clock size={22} color="#6366f1" />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#276221', fontWeight: 600 }}>Daily Order Average</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#6366f1' }}>
              {matchedCategoryItem.avg_daily} <span style={{ fontSize: '0.8rem', fontWeight: 500, color: '#64748b' }}>/ day</span>
            </div>
          </div>
        </div>

        {/* Peak Demand Day */}
        <div style={{ background: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #276221', display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ width: '42px', height: '42px', borderRadius: '10px', background: '#ffffff', border: '1px solid #276221', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#f59e0b', flexShrink: 0 }}>
            <Award size={22} color="#f59e0b" />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#276221', fontWeight: 600 }}>Peak Demand Day</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#f59e0b' }}>
              {peakDayObj ? peakDayObj.label : 'N/A'} <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b' }}>({peakDayObj?.val || 0} orders)</span>
            </div>
          </div>
        </div>

      </div>

      {/* Monday to Sunday Daily Timetable Matrix / Breakdown */}
      <div style={{ marginBottom: '22px' }}>
        <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#1e293b', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Sparkles size={16} color="#276221" /> Monday to Sunday Daily Forecast Breakdown:
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '10px' }}>
          {dayValues.map(d => {
            const isPeak = d.val === maxVal && maxVal > 0;
            const barPct = maxVal > 0 ? Math.max(18, Math.round((d.val / maxVal) * 100)) : 10;

            return (
              <div
                key={d.key}
                style={{
                  background: '#ffffff',
                  border: '1px solid #276221',
                  borderRadius: '12px',
                  padding: '14px 10px',
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  position: 'relative'
                }}
              >
                {/* Day Name */}
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1e293b' }}>
                  {d.label}
                </div>
                <div style={{ fontSize: '0.68rem', color: '#64748b', marginBottom: '8px' }}>
                  {d.isWeekend ? 'Weekend' : 'Weekday'}
                </div>

                {/* Forecast Number */}
                <div style={{
                  fontSize: '1.4rem',
                  fontWeight: 800,
                  color: '#276221',
                  margin: '4px 0'
                }}>
                  {d.val}
                  <span style={{ fontSize: '0.7rem', display: 'block', fontWeight: 500, color: '#64748b' }}>orders</span>
                </div>

                {/* Progress Bar Indicator */}
                <div style={{ width: '100%', height: '6px', background: '#f1f5f9', borderRadius: '3px', overflow: 'hidden', marginTop: '6px', border: '1px solid #276221' }}>
                  <div style={{
                    width: `${barPct}%`,
                    height: '100%',
                    background: '#276221'
                  }} />
                </div>

                {/* Peak Badge */}
                {isPeak && (
                  <span style={{
                    position: 'absolute',
                    top: '-10px',
                    background: '#f59e0b',
                    color: '#000',
                    fontSize: '0.62rem',
                    fontWeight: 900,
                    padding: '2px 8px',
                    borderRadius: '8px',
                    letterSpacing: '0.5px'
                  }}>
                    ⭐ PEAK DAY
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Smart Provider Insight Notice */}
      <div style={{
        background: 'rgba(16, 185, 129, 0.12)',
        border: '1px solid rgba(16, 185, 129, 0.3)',
        borderRadius: '12px',
        padding: '14px 18px',
        display: 'flex',
        alignItems: 'center',
        gap: '14px'
      }}>
        <Info size={20} color="var(--accent-provider)" style={{ flexShrink: 0 }} />
        <div style={{ fontSize: '0.85rem', color: 'var(--text-main)', lineHeight: 1.5 }}>
          <strong>Smart Availability Recommendation for {providerName || 'Provider'}:</strong>{' '}
          {peakDayObj ? (
            <>
              Your peak demand day is <strong>{peakDayObj.label}</strong> with an estimated <strong>{peakDayObj.val} orders</strong>.
              Keep your working hours set to <span style={{ color: '#34d399', fontWeight: 700 }}>Open</span> on {peakDayObj.label} to maximize your job requests!
            </>
          ) : (
            `Maintain active working hours throughout the week to maximize job requests in ${matchedCategoryItem.service_category}.`
          )}
        </div>
      </div>

    </div>
  );
};
