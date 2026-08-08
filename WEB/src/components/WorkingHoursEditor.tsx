import React from 'react';
import { Clock } from 'lucide-react';
import type { WorkingHours, DaySchedule } from '../config/firebase';

interface WorkingHoursEditorProps {
  workingHours: WorkingHours;
  onChange: (updatedHours: WorkingHours) => void;
}

const DAYS: (keyof WorkingHours)[] = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export const WorkingHoursEditor: React.FC<WorkingHoursEditorProps> = ({ workingHours, onChange }) => {
  const handleChange = (day: keyof WorkingHours, field: keyof DaySchedule, value: any) => {
    onChange({
      ...workingHours,
      [day]: {
        ...(workingHours[day] || { isOpen: false, start: '08:00 AM', end: '06:00 PM' }),
        [field]: value
      }
    });
  };

  return (
    <div className="glass-panel" style={{ background: 'var(--bg-card)', padding: '18px', borderRadius: '14px', border: '1px solid var(--bg-card-border)', margin: '18px 0' }}>
      <label className="form-label" style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)' }}>
        <Clock size={16} /> Manage Working Hours & Weekly Operating Days
      </label>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {DAYS.map(day => {
          const item = workingHours[day] || { isOpen: false, start: '08:00 AM', end: '06:00 PM' };
          return (
            <div
              key={day}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '10px',
                background: item.isOpen ? 'var(--input-bg)' : 'var(--bg-secondary)',
                padding: '10px 14px',
                borderRadius: '10px',
                border: `1px solid ${item.isOpen ? 'var(--primary)' : 'var(--bg-card-border)'}`
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: '130px' }}>
                <input
                  type="checkbox"
                  id={`check-${day}`}
                  checked={item.isOpen}
                  onChange={(e) => handleChange(day, 'isOpen', e.target.checked)}
                  style={{ width: '18px', height: '18px', accentColor: '#276221', cursor: 'pointer' }}
                />
                <label htmlFor={`check-${day}`} style={{ fontSize: '0.88rem', fontWeight: 600, cursor: 'pointer', margin: 0 }}>
                  {day}
                </label>
              </div>

              {item.isOpen ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="08:00 AM"
                    value={item.start || '08:00 AM'}
                    onChange={(e) => handleChange(day, 'start', e.target.value)}
                    style={{ width: '100px', padding: '4px 8px', fontSize: '0.82rem' }}
                  />
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>to</span>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="06:00 PM"
                    value={item.end || '06:00 PM'}
                    onChange={(e) => handleChange(day, 'end', e.target.value)}
                    style={{ width: '100px', padding: '4px 8px', fontSize: '0.82rem' }}
                  />
                </div>
              ) : (
                <span style={{ fontSize: '0.8rem', color: '#dc2626', fontStyle: 'italic' }}>
                  Closed on {day}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
