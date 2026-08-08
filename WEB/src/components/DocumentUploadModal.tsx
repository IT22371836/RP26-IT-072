import React, { useState } from 'react';
import { Upload, X, CheckCircle, Loader2, FileText } from 'lucide-react';
import type { Provider } from '../config/firebase';
import { uploadProviderDocumentForConfiguredSource } from '../services/provider-service';

interface DocumentUploadModalProps {
  provider: Provider;
  onClose: () => void;
  onSuccess: (updatedProvider: Provider) => void;
}

export const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  provider,
  onClose,
  onSuccess
}) => {
  const [category, setCategory] = useState<'certification' | 'businessRegistration' | 'portfolioWork' | 'experienceProof' | 'identityDocument'>('certification');
  const [fileName, setFileName] = useState('');
  const [fileDataUrl, setFileDataUrl] = useState('');
  const [uploading, setUploading] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!fileName) {
      setFileName(file.name);
    }

    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setFileDataUrl(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fileName.trim() || !fileDataUrl) {
      alert("Please select a document or image file to upload.");
      return;
    }

    setUploading(true);
    setSuccessMsg('');

    try {
      const updatedProvider = await uploadProviderDocumentForConfiguredSource(
        provider,
        category,
        fileName.trim(),
        fileDataUrl
      );
      setSuccessMsg("Document uploaded successfully to protected storage!");
      setTimeout(() => {
        onSuccess(updatedProvider);
        onClose();
      }, 1200);
    } catch (err: any) {
      console.error(err);
      alert("Document upload failed: " + err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '540px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
          <h2 style={{ fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: '8px', color: '#276221' }}>
            <Upload size={20} /> Upload Provider Document / Portfolio
          </h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        {successMsg && (
          <div style={{ background: 'rgba(39, 98, 33, 0.1)', border: '1px solid #276221', color: '#1e4b19', padding: '10px 14px', borderRadius: '10px', fontSize: '0.88rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle size={16} /> {successMsg}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          
          <div className="form-group">
            <label className="form-label">Document Category</label>
            <select
              className="form-control"
              value={category}
              onChange={(e) => setCategory(e.target.value as any)}
            >
              <option value="certification">Certification & NVQ Qualification</option>
              <option value="businessRegistration">Business Registration (BR Certificate)</option>
              <option value="portfolioWork">Portfolio Work & Project Photo</option>
              <option value="experienceProof">Experience Proof & Letter</option>
              <option value="identityDocument">Identity Document (NIC / License)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Document Name / Title</label>
            <input
              type="text"
              className="form-control"
              placeholder="e.g., NVQ Level 4 Certificate, Project Photo 1..."
              value={fileName}
              onChange={(e) => setFileName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Select File (JPG, PNG, or PDF)</label>
            <input
              type="file"
              accept="image/*,.pdf"
              className="form-control"
              onChange={handleFileChange}
              required
              style={{ padding: '8px' }}
            />
          </div>

          {fileDataUrl && (
            <div style={{ background: '#f8faf8', padding: '12px', borderRadius: '10px', marginBottom: '16px', border: '1px solid #cbd5e1', display: 'flex', alignItems: 'center', gap: '10px' }}>
              {fileDataUrl.includes('application/pdf') ? (
                <FileText size={28} color="#dc2626" />
              ) : (
                <img src={fileDataUrl} alt="Preview" style={{ width: '44px', height: '44px', objectFit: 'cover', borderRadius: '6px' }} />
              )}
              <div>
                <span style={{ fontSize: '0.84rem', fontWeight: 600, color: '#276221', display: 'block' }}>File Ready for Upload</span>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>{fileName}</span>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
            <button
              type="submit"
              className="btn btn-provider"
              style={{ flex: 1, padding: '12px' }}
              disabled={uploading}
            >
              {uploading ? <Loader2 size={16} className="spin" /> : <Upload size={16} />} Upload Document
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClose}
            >
              Cancel
            </button>
          </div>

        </form>
      </div>
    </div>
  );
};
