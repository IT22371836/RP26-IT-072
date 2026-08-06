import React, { useState } from 'react';
import { Camera, Upload, Link as LinkIcon, Check, Image as ImageIcon } from 'lucide-react';

interface ImageUploaderProps {
  label: string;
  imageValue: string;
  onChange: (urlOrBase64: string) => void;
  accentColor?: string;
}

const PRESET_AVATARS = [
  "https://api.dicebear.com/7.x/avataaars/svg?seed=Felix",
  "https://api.dicebear.com/7.x/avataaars/svg?seed=Aneka",
  "https://api.dicebear.com/7.x/avataaars/svg?seed=Zack",
  "https://api.dicebear.com/7.x/avataaars/svg?seed=Sara",
  "https://firebasestorage.googleapis.com/v0/b/service-e333a.appspot.com/o/providers%2Fprovider_default.png?alt=media"
];

export const ImageUploader: React.FC<ImageUploaderProps> = ({
  label,
  imageValue,
  onChange,
  accentColor = "var(--primary)"
}) => {
  const [mode, setMode] = useState<'upload' | 'url'>('upload');
  const [urlInput, setUrlInput] = useState('');

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        alert("File size too large. Please select an image smaller than 5MB.");
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        if (typeof reader.result === 'string') {
          onChange(reader.result);
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const handleUrlSubmit = () => {
    if (urlInput.trim()) {
      onChange(urlInput.trim());
    }
  };

  return (
    <div className="form-group">
      <label className="form-label">
        <Camera size={16} style={{ color: accentColor }} />
        {label}
      </label>

      <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
        {/* Preview Circle */}
        <div style={{
          width: '72px',
          height: '72px',
          borderRadius: '50%',
          border: `2px solid ${accentColor}`,
          overflow: 'hidden',
          background: 'rgba(15, 23, 42, 0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: `0 0 15px ${accentColor}33`,
          flexShrink: 0
        }}>
          {imageValue ? (
            <img 
              src={imageValue} 
              alt="Profile Preview" 
              style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
              onError={(e) => {
                (e.target as HTMLElement).setAttribute('src', 'https://api.dicebear.com/7.x/bottts/svg?seed=Fallback');
              }}
            />
          ) : (
            <ImageIcon size={28} style={{ color: 'var(--text-muted)' }} />
          )}
        </div>

        {/* Input Controls */}
        <div style={{ flex: 1, minWidth: '220px' }}>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
            <button
              type="button"
              className="btn btn-outline"
              style={{ padding: '6px 12px', fontSize: '0.78rem', borderColor: mode === 'upload' ? accentColor : undefined }}
              onClick={() => setMode('upload')}
            >
              <Upload size={14} /> File Upload
            </button>
            <button
              type="button"
              className="btn btn-outline"
              style={{ padding: '6px 12px', fontSize: '0.78rem', borderColor: mode === 'url' ? accentColor : undefined }}
              onClick={() => setMode('url')}
            >
              <LinkIcon size={14} /> Web URL
            </button>
          </div>

          {mode === 'upload' ? (
            <label className="btn btn-outline" style={{ width: '100%', padding: '10px', fontSize: '0.85rem', cursor: 'pointer', borderStyle: 'dashed' }}>
              <Upload size={16} /> Choose Image File...
              <input 
                type="file" 
                accept="image/*" 
                onChange={handleFileUpload} 
                style={{ display: 'none' }} 
              />
            </label>
          ) : (
            <div style={{ display: 'flex', gap: '6px' }}>
              <input 
                type="url" 
                placeholder="https://example.com/photo.jpg" 
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                className="form-control" 
                style={{ padding: '8px 12px', fontSize: '0.85rem' }}
              />
              <button 
                type="button"
                className="btn btn-primary" 
                style={{ padding: '8px 12px', background: accentColor }}
                onClick={handleUrlSubmit}
              >
                <Check size={16} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Preset Quick Selectors */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '10px' }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Presets:</span>
        <div style={{ display: 'flex', gap: '6px' }}>
          {PRESET_AVATARS.map((avatar, idx) => (
            <img 
              key={idx}
              src={avatar}
              alt={`Avatar ${idx}`}
              onClick={() => onChange(avatar)}
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                cursor: 'pointer',
                border: imageValue === avatar ? `2px solid ${accentColor}` : '1px solid rgba(255,255,255,0.2)',
                opacity: imageValue === avatar ? 1 : 0.6,
                transition: 'all 0.2s'
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
