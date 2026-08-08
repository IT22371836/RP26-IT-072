import React from 'react';
import { FileText, Image as ImageIcon, ShieldCheck, Award, Briefcase, Trash2, ExternalLink, Plus, Building2, Lock } from 'lucide-react';
import type { ProviderDocuments, ProviderDocumentItem } from '../config/firebase';

interface ProviderDocumentsViewProps {
  documents?: ProviderDocuments;
  canManage?: boolean;
  isLocked?: boolean;
  onOpenUploadModal?: () => void;
  onDeleteDocument?: (category: 'identityDocument' | 'certification' | 'businessRegistration' | 'experienceProof' | 'portfolioWork', fileId: string) => void;
  onOpenDocument?: (
    category: 'identityDocument' | 'certification' | 'businessRegistration' | 'experienceProof' | 'portfolioWork',
    item: ProviderDocumentItem
  ) => void | Promise<void>;
}

export const ProviderDocumentsView: React.FC<ProviderDocumentsViewProps> = ({
  documents,
  canManage = false,
  isLocked = false,
  onOpenUploadModal,
  onDeleteDocument,
  onOpenDocument
}) => {
  const identityList = documents?.identityDocument || [];
  const certList = documents?.certification || [];
  const brList = documents?.businessRegistration || [];
  const expList = documents?.experienceProof || [];
  const portList = documents?.portfolioWork || [];

  const renderSection = (
    title: string,
    icon: React.ReactNode,
    category: 'identityDocument' | 'certification' | 'businessRegistration' | 'experienceProof' | 'portfolioWork',
    items: ProviderDocumentItem[]
  ) => {
    return (
      <div style={{ background: '#f8faf8', padding: '16px', borderRadius: '12px', border: '1px solid #cbd5e1', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <h4 style={{ fontSize: '0.94rem', margin: 0, display: 'flex', alignItems: 'center', gap: '6px', color: '#0f172a' }}>
            {icon} {title} ({items.length})
          </h4>
        </div>

        {items.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', fontStyle: 'italic', margin: 0 }}>
            No documents uploaded yet in this category.
          </p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '10px' }}>
            {items.map(item => (
              <div
                key={item.fileId}
                style={{
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                  {item.format === 'PDF' ? (
                    <FileText size={24} color="#dc2626" style={{ flexShrink: 0 }} />
                  ) : (
                    <ImageIcon size={24} color="#276221" style={{ flexShrink: 0 }} />
                  )}
                  <div style={{ overflow: 'hidden' }}>
                    {onOpenDocument ? (
                      <button
                        type="button"
                        onClick={() => void onOpenDocument(category, item)}
                        style={{ fontSize: '0.82rem', fontWeight: 600, color: '#276221', border: 0, padding: 0, background: 'transparent', cursor: 'pointer', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}
                        title={item.fileName}
                      >
                        {item.fileName} <ExternalLink size={10} style={{ display: 'inline' }} />
                      </button>
                    ) : (
                      <a
                        href={item.fileUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: '0.82rem', fontWeight: 600, color: '#276221', textDecoration: 'none', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                        title={item.fileName}
                      >
                        {item.fileName} <ExternalLink size={10} style={{ display: 'inline' }} />
                      </a>
                    )}
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', display: 'block' }}>
                      {item.format} • {new Date(item.uploadedAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                {canManage && onDeleteDocument && (
                  isLocked ? (
                    <button
                      type="button"
                      disabled
                      style={{ background: 'rgba(148, 163, 184, 0.1)', border: '1px solid rgba(148, 163, 184, 0.2)', color: '#64748b', padding: '4px 6px', borderRadius: '6px', cursor: 'not-allowed', opacity: 0.6 }}
                      title="Document deletion is locked while verification is requested or verified"
                    >
                      <Lock size={13} />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onDeleteDocument(category, item.fileId)}
                      style={{ background: 'rgba(239, 68, 68, 0.1)', border: 'none', color: '#dc2626', padding: '4px', borderRadius: '6px', cursor: 'pointer', flexShrink: 0 }}
                      title="Delete document"
                    >
                      <Trash2 size={14} />
                    </button>
                  )
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ background: '#f8faf8', padding: '20px', borderRadius: '14px', border: '1px solid #cbd5e1', marginTop: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
        <h3 style={{ fontSize: '1.05rem', margin: 0, display: 'flex', alignItems: 'center', gap: '8px', color: '#276221' }}>
          <FileText size={18} /> Provider Documents and Credentials Portfolio
          {isLocked && (
            <span style={{ fontSize: '0.74rem', background: 'rgba(245, 158, 11, 0.15)', color: '#b45309', border: '1px solid rgba(245, 158, 11, 0.3)', padding: '2px 8px', borderRadius: '12px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <Lock size={11} /> Document Actions Locked
            </span>
          )}
        </h3>

        {canManage && onOpenUploadModal && (
          <button
            type="button"
            className="btn btn-provider"
            onClick={isLocked ? undefined : onOpenUploadModal}
            disabled={isLocked}
            style={{ 
              padding: '6px 14px', 
              fontSize: '0.82rem',
              opacity: isLocked ? 0.55 : 1,
              cursor: isLocked ? 'not-allowed' : 'pointer',
              background: isLocked ? 'rgba(148, 163, 184, 0.15)' : undefined,
              borderColor: isLocked ? 'rgba(148, 163, 184, 0.3)' : undefined,
              color: isLocked ? '#94a3b8' : undefined
            }}
            title={isLocked ? "Document upload is locked while verification is processing or profile is verified" : "Upload new document"}
          >
            {isLocked ? <Lock size={14} /> : <Plus size={14} />} Upload New Document
          </button>
        )}
      </div>

      {renderSection('Certifications & Qualification Badges', <Award size={16} color="#d97706" />, 'certification', certList)}
      {renderSection('Business Registration (BR Certificate)', <Building2 size={16} color="#0284c7" />, 'businessRegistration', brList)}
      {renderSection('Portfolio Work & Project Photos', <ImageIcon size={16} color="#276221" />, 'portfolioWork', portList)}
      {renderSection('Experience Proof & Recommendation Letters', <Briefcase size={16} color="#7c3aed" />, 'experienceProof', expList)}
      {canManage && renderSection('Identity Verification (NIC / Passport)', <ShieldCheck size={16} color="#276221" />, 'identityDocument', identityList)}
    </div>
  );
};
