import React from 'react';
import { Clock } from 'lucide-react';
import type { WorkingHours } from '../config/firebase';
import { DEFAULT_WORKING_HOURS } from '../config/firebase';

interface WorkingHoursViewProps {
  workingHours?: WorkingHours;
  onEditClick?: () => void;
}

const DAYS: (keyof WorkingHours)[] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export const WorkingHoursView: React.FC<WorkingHoursViewProps> = ({ workingHours, onEditClick }) => {
  const schedule = workingHours || DEFAULT_WORKING_HOURS;

  return (
    <div className="glass-panel" style={{ background: 'var(--bg-card)', padding: '18px', borderRadius: '14px', border: '1px solid var(--bg-card-border)', marginTop: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <h4 style={{ fontSize: '0.96rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)' }}>
          <Clock size={16} /> Working Hours Schedule
        </h4>
        {onEditClick && (
          <button
            type="button"
            className="btn btn-outline"
            onClick={onEditClick}
            style={{ fontSize: '0.76rem', padding: '4px 10px', borderColor: 'var(--primary)', color: 'var(--primary)' }}
          >
            ✏️ Edit Schedule
          </button>
        )}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '8px' }}>
        {DAYS.map(day => {
          const item = schedule[day] || { isOpen: false, start: '', end: '' };
          return (
            <div
              key={day}
              style={{
                background: item.isOpen ? 'var(--input-bg)' : 'var(--bg-secondary)',
                border: `1px solid ${item.isOpen ? 'var(--primary)' : 'var(--bg-card-border)'}`,
                borderRadius: '8px',
                padding: '8px 10px',
                textAlign: 'center'
              }}
            >
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '2px' }}>{day}</div>
              {item.isOpen ? (
                <div style={{ fontSize: '0.74rem', color: 'var(--primary)', fontWeight: 600 }}>
                  {item.start || '08:00 AM'} - {item.end || '06:00 PM'}
                </div>
              ) : (
                <div style={{ fontSize: '0.74rem', color: '#dc2626', fontWeight: 600 }}>
                  Closed
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
