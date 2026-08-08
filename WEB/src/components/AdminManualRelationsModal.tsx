import React, { useState } from 'react';
import { Settings, X, Plus, Save, Loader2, CheckCircle, Cpu, FileText, Wand2, Sparkles, Zap } from 'lucide-react';
import { updateProviderProfile, uploadProviderDocument } from '../config/firebase';
import type { Provider, ProviderDocuments, ProviderDocumentItem, ExtractedFeatures, CredibilityInfo } from '../config/firebase';

interface AdminManualRelationsModalProps {
  provider: Provider;
  adminUser: any;
  onClose: () => void;
  onSuccess: () => void;
}

export const AdminManualRelationsModal: React.FC<AdminManualRelationsModalProps> = ({
  provider,
  adminUser,
  onClose,
  onSuccess
}) => {
  const initialDocs: ProviderDocuments = provider.documents || {
    identityDocument: [],
    certification: [],
    businessRegistration: [],
    experienceProof: [],
    portfolioWork: [],
    status: false
  };

  const initialFeatures: ExtractedFeatures = provider.extractedFeatures || provider.documents?.extractedFeatures || {
    provider_id: provider.id,
    service_category: provider.category || 'Electricians',
    identity_verified: (initialDocs.identityDocument && initialDocs.identityDocument.length > 0) ? 1 : 0,
    certification_count: initialDocs.certification ? initialDocs.certification.length : 0,
    highest_cert_level: 'NVQ Level 4',
    cert_issuer_reputation: 0.85,
    business_registered: (initialDocs.businessRegistration && initialDocs.businessRegistration.length > 0) ? 1 : 0,
    experience_years: provider.experienceYears || 5,
    experience_reference_count: (initialDocs.experienceProof && initialDocs.experienceProof.length > 0) ? initialDocs.experienceProof.length : 1,
    portfolio_count: initialDocs.portfolioWork ? initialDocs.portfolioWork.length : 1,
    portfolio_quality_score: 0.80,
    credibility: provider.credibility || {
      credibilityScore: 85.0,
      credibilityLevel: 'Professional',
      lastEvaluatedAt: new Date().toISOString()
    }
  };

  const [docsState, setDocsState] = useState<ProviderDocuments>({
    identityDocument: [...(initialDocs.identityDocument || [])],
    certification: [...(initialDocs.certification || [])],
    businessRegistration: [...(initialDocs.businessRegistration || [])],
    experienceProof: [...(initialDocs.experienceProof || [])],
    portfolioWork: [...(initialDocs.portfolioWork || [])],
    status: initialDocs.status || false
  });

  const [featuresState, setFeaturesState] = useState<ExtractedFeatures>({
    ...initialFeatures,
    identity_verified: initialFeatures.identity_verified ?? 0,
    business_registered: initialFeatures.business_registered ?? 0,
    certification_count: initialFeatures.certification_count ?? 0,
    highest_cert_level: initialFeatures.highest_cert_level || 'NVQ Level 4',
    cert_issuer_reputation: initialFeatures.cert_issuer_reputation ?? 0.85,
    experience_years: initialFeatures.experience_years ?? (provider.experienceYears || 5),
    experience_reference_count: initialFeatures.experience_reference_count ?? 1,
    portfolio_count: initialFeatures.portfolio_count ?? 1,
    portfolio_quality_score: initialFeatures.portfolio_quality_score ?? 0.80,
  });

  const [credScore, setCredScore] = useState<number>(
    initialFeatures.credibility?.credibilityScore ?? provider.credibility?.credibilityScore ?? 80.0
  );
  const [credLevel, setCredLevel] = useState<string>(
    initialFeatures.credibility?.credibilityLevel ?? provider.credibility?.credibilityLevel ?? 'Professional'
  );

  // New File Form State for Manual Document Relation Creation
  const [newDocCategory, setNewDocCategory] = useState<'identityDocument' | 'certification' | 'businessRegistration' | 'experienceProof' | 'portfolioWork'>('identityDocument');
  const [newDocTitle, setNewDocTitle] = useState('');
  const [newDocUrl, setNewDocUrl] = useState('');
  const [_newDocFile, setNewDocFile] = useState<File | null>(null);
  const [newDocFileDataUrl, setNewDocFileDataUrl] = useState('');
  const [uploadingDoc, setUploadingDoc] = useState(false);

  const [selectedPreset, setSelectedPreset] = useState<'full' | 'specialist' | 'business'>('full');
  const [autoCreating, setAutoCreating] = useState(false);

  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  // Keep the visibility branch after Hooks so their order remains stable across renders.
  if (!adminUser || adminUser.role !== 'admin' || provider.verified) {
    return null;
  }

  // 1-Click Automatic Creation & Population Function
  const handleAutoPopulateFullNode = (presetType: 'full' | 'specialist' | 'business' = selectedPreset) => {
    const time = Date.now();
    const pid = provider.id || 'provider_sample';
    const categoryName = provider.category || 'Professional Technical';
    const fullName = provider.fullName || 'Provider';

    let docs: ProviderDocuments = {
      identityDocument: [
        {
          fileId: `doc_${time}_nic`,
          fileName: `${fullName} - National Identity Card (NIC)`,
          fileUrl: `https://firebasestorage.googleapis.com/v0/b/service-e333a.firebasestorage.app/o/providers%2F${pid}%2Fdocuments%2Fdoc_nic.png?alt=media`,
          format: 'PNG',
          uploadedAt: new Date().toISOString()
        }
      ],
      certification: [
        {
          fileId: `doc_${time}_cert`,
          fileName: `${categoryName} - NVQ Level 4 Qualification Certificate`,
          fileUrl: `https://firebasestorage.googleapis.com/v0/b/service-e333a.firebasestorage.app/o/providers%2F${pid}%2Fdocuments%2Fdoc_cert.pdf?alt=media`,
          format: 'PDF',
          uploadedAt: new Date().toISOString()
        }
      ],
      businessRegistration: presetType !== 'specialist' ? [
        {
          fileId: `doc_${time}_br`,
          fileName: `${fullName} - Business Registration Certificate (BR)`,
          fileUrl: `https://firebasestorage.googleapis.com/v0/b/service-e333a.firebasestorage.app/o/providers%2F${pid}%2Fdocuments%2Fdoc_br.pdf?alt=media`,
          format: 'PDF',
          uploadedAt: new Date().toISOString()
        }
      ] : [],
      experienceProof: [
        {
          fileId: `doc_${time}_exp`,
          fileName: `Client Reference Letter & ${provider.experienceYears || 5}+ Yrs Experience Proof`,
          fileUrl: `https://firebasestorage.googleapis.com/v0/b/service-e333a.firebasestorage.app/o/providers%2F${pid}%2Fdocuments%2Fdoc_exp.pdf?alt=media`,
          format: 'PDF',
          uploadedAt: new Date().toISOString()
        }
      ],
      portfolioWork: presetType === 'full' ? [
        {
          fileId: `doc_${time}_port1`,
          fileName: `${categoryName} Completed Site Project Photo`,
          fileUrl: `https://firebasestorage.googleapis.com/v0/b/service-e333a.firebasestorage.app/o/providers%2F${pid}%2Fdocuments%2Fdoc_port1.jpg?alt=media`,
          format: 'JPG',
          uploadedAt: new Date().toISOString()
        },
        {
          fileId: `doc_${time}_port2`,
          fileName: `Advanced Technical Installation Showcase`,
          fileUrl: `https://firebasestorage.googleapis.com/v0/b/service-e333a.firebasestorage.app/o/providers%2F${pid}%2Fdocuments%2Fdoc_port2.jpg?alt=media`,
          format: 'JPG',
          uploadedAt: new Date().toISOString()
        }
      ] : [
        {
          fileId: `doc_${time}_port1`,
          fileName: `${categoryName} Completed Work Photo`,
          fileUrl: `https://firebasestorage.googleapis.com/v0/b/service-e333a.firebasestorage.app/o/providers%2F${pid}%2Fdocuments%2Fdoc_port1.jpg?alt=media`,
          format: 'JPG',
          uploadedAt: new Date().toISOString()
        }
      ],
      status: false,
      verified: true
    };

    setDocsState(docs);

    const autoFeatures: ExtractedFeatures = {
      provider_id: provider.id,
      service_category: provider.category || 'Electricians',
      identity_verified: 1,
      business_registered: presetType !== 'specialist' ? 1 : 0,
      certification_count: docs.certification?.length || 1,
      highest_cert_level: 'NVQ Level 4',
      cert_issuer_reputation: presetType === 'full' ? 0.95 : 0.85,
      experience_years: provider.experienceYears || (presetType === 'full' ? 8 : 5),
      experience_reference_count: docs.experienceProof?.length || 1,
      portfolio_count: docs.portfolioWork?.length || 1,
      portfolio_quality_score: presetType === 'full' ? 0.90 : 0.80,
    };

    setFeaturesState(autoFeatures);

    // Compute credibility score
    let score = 50.0;
    if (autoFeatures.identity_verified === 1) score += 15;
    if (autoFeatures.business_registered === 1) score += 15;
    score += Math.min((autoFeatures.certification_count || 0) * 5, 15);
    score += Math.min((autoFeatures.experience_years || 0) * 1.5, 15);
    score += Math.min((autoFeatures.portfolio_count || 0) * 2, 10);
    score += (autoFeatures.portfolio_quality_score || 0) * 10;
    const finalScore = Math.min(Math.round(score * 100) / 100, 98.5);

    let level = 'Beginner';
    if (finalScore >= 85) level = 'Professional';
    else if (finalScore >= 60) level = 'Intermediate';

    setCredScore(finalScore);
    setCredLevel(level);

    setSuccessMsg(`⚡ Auto-populated full documents node & relations using [${presetType.toUpperCase()}] package!`);
    return { docs, autoFeatures, finalScore, level };
  };

  // 1-Click Auto Create & Save Directly to Database
  const handleOneClickAutoCreateAndSave = async (presetType: 'full' | 'specialist' | 'business' = selectedPreset) => {
    if (!provider.id) return;
    setAutoCreating(true);
    setSuccessMsg('');

    try {
      const generated = handleAutoPopulateFullNode(presetType);
      
      const cred: CredibilityInfo = {
        credibilityScore: generated.finalScore,
        credibilityLevel: generated.level,
        lastEvaluatedAt: new Date().toISOString()
      };

      const updatedFeatures: ExtractedFeatures = {
        ...generated.autoFeatures,
        credibility: cred
      };

      const updatedDocs: ProviderDocuments = {
        ...generated.docs,
        extractedFeatures: updatedFeatures,
        status: false,
        verified: true
      };

      await updateProviderProfile(provider.id, {
        documents: updatedDocs,
        extractedFeatures: updatedFeatures,
        verified: true
      });

      setSuccessMsg(`🚀 1-Click Success! Created full documents node & ML relations for ${provider.fullName}!`);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1200);
    } catch (err: any) {
      console.error(err);
      alert("Failed 1-click automatic creation: " + err.message);
    } finally {
      setAutoCreating(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setNewDocFile(file);
    if (!newDocTitle) {
      setNewDocTitle(file.name);
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setNewDocFileDataUrl(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleAddManualDocument = async () => {
    if (!newDocTitle.trim()) {
      alert("Please provide a document title.");
      return;
    }

    let finalUrl = newDocUrl.trim();

    if (newDocFileDataUrl && provider.id) {
      setUploadingDoc(true);
      try {
        const item = await uploadProviderDocument(provider.id, newDocCategory, newDocTitle.trim(), newDocFileDataUrl);
        finalUrl = item.fileUrl;
      } catch (err: any) {
        console.error(err);
        alert("Failed to upload document file: " + err.message);
        setUploadingDoc(false);
        return;
      } finally {
        setUploadingDoc(false);
      }
    }

    if (!finalUrl) {
      finalUrl = `https://firebasestorage.googleapis.com/v0/b/service-e333a.appspot.com/o/providers%2Fmanual_doc_${Date.now()}.pdf?alt=media`;
    }

    const newItem: ProviderDocumentItem = {
      fileId: `doc_${Math.floor(100000 + Math.random() * 900000)}`,
      fileName: newDocTitle.trim(),
      fileUrl: finalUrl,
      format: finalUrl.toLowerCase().includes('.pdf') ? 'PDF' : 'PNG',
      uploadedAt: new Date().toISOString()
    };

    const categoryList = docsState[newDocCategory] || [];
    const updatedCategoryList = [...categoryList, newItem];

    const updatedDocsState = {
      ...docsState,
      [newDocCategory]: updatedCategoryList
    };

    setDocsState(updatedDocsState);

    // Auto update counts in featuresState
    setFeaturesState(prev => ({
      ...prev,
      identity_verified: (updatedDocsState.identityDocument && updatedDocsState.identityDocument.length > 0) ? 1 : prev.identity_verified,
      business_registered: (updatedDocsState.businessRegistration && updatedDocsState.businessRegistration.length > 0) ? 1 : prev.business_registered,
      certification_count: updatedDocsState.certification ? updatedDocsState.certification.length : prev.certification_count,
      experience_reference_count: updatedDocsState.experienceProof ? updatedDocsState.experienceProof.length : prev.experience_reference_count,
      portfolio_count: updatedDocsState.portfolioWork ? updatedDocsState.portfolioWork.length : prev.portfolio_count
    }));

    // Reset Form
    setNewDocTitle('');
    setNewDocUrl('');
    setNewDocFile(null);
    setNewDocFileDataUrl('');
  };

  const handleRemoveDocument = (cat: 'identityDocument' | 'certification' | 'businessRegistration' | 'experienceProof' | 'portfolioWork', fileId: string) => {
    const list = docsState[cat] || [];
    const filtered = list.filter(item => item.fileId !== fileId);
    setDocsState({
      ...docsState,
      [cat]: filtered
    });
  };

  const handleAutoCalculateScore = () => {
    let score = 50.0;
    if (featuresState.identity_verified === 1) score += 15;
    if (featuresState.business_registered === 1) score += 15;
    score += Math.min((featuresState.certification_count || 0) * 5, 15);
    score += Math.min((featuresState.experience_years || 0) * 1.5, 15);
    score += Math.min((featuresState.portfolio_count || 0) * 2, 10);
    score += (featuresState.portfolio_quality_score || 0) * 10;
    const finalScore = Math.min(Math.round(score * 100) / 100, 99.5);

    let level = 'Beginner';
    if (finalScore >= 85) level = 'Professional';
    else if (finalScore >= 60) level = 'Intermediate';

    setCredScore(finalScore);
    setCredLevel(level);
  };

  const handleSaveRelations = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!provider.id) return;

    setSaving(true);
    setSuccessMsg('');

    const cred: CredibilityInfo = {
      credibilityScore: credScore,
      credibilityLevel: credLevel,
      lastEvaluatedAt: new Date().toISOString()
    };

    const updatedFeatures: ExtractedFeatures = {
      ...featuresState,
      provider_id: provider.id,
      service_category: provider.category || 'Electricians',
      credibility: cred
    };

    const updatedDocs: ProviderDocuments = {
      ...docsState,
      extractedFeatures: updatedFeatures,
      status: false,
      verified: true
    };

    try {
      await updateProviderProfile(provider.id, {
        documents: updatedDocs,
        extractedFeatures: updatedFeatures,
        verified: true
      });

      setSuccessMsg("Provider manual documents and extractedFeatures relations created/updated successfully!");
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1200);
    } catch (err: any) {
      console.error(err);
      alert("Failed to save manual relations: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '880px', maxHeight: '92vh', overflowY: 'auto' }}>
        
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '14px' }}>
          <div>
            <span style={{ fontSize: '0.75rem', background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5', padding: '3px 8px', borderRadius: '8px', fontWeight: 700, textTransform: 'uppercase', display: 'inline-block', marginBottom: '4px' }}>
              🔒 ADMIN PRIVILEGE ONLY • UNVERIFIED PROFILE
            </span>
            <h2 style={{ fontSize: '1.4rem', margin: 0, display: 'flex', alignItems: 'center', gap: '10px', color: '#38bdf8' }}>
              <Settings size={22} color="#38bdf8" /> Admin Manual Documents & Extracted Features Setup
            </h2>
            <p style={{ margin: '4px 0 0 0', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Manually attach document files & configure ML extracted features relation for <strong>{provider.fullName}</strong>
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', padding: '8px', borderRadius: '50%', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        {successMsg && (
          <div style={{ background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', color: '#6ee7b7', padding: '12px 16px', borderRadius: '12px', fontSize: '0.9rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle size={18} /> {successMsg}
          </div>
        )}

        {/* ⚡ ONE-CLICK AUTOMATIC SETUP CONTROL PANEL */}
        <div style={{ background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.15) 0%, rgba(99, 102, 241, 0.15) 100%)', border: '1px solid rgba(56, 189, 248, 0.4)', borderRadius: '14px', padding: '18px', marginBottom: '22px', boxShadow: '0 8px 24px rgba(0, 0, 0, 0.2)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '1.05rem', margin: 0, color: '#e0f2fe', display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700 }}>
              <Zap size={20} color="#f59e0b" /> 1-Click Automatic Documents Node & Full Relation Setup
            </h3>
            <span style={{ fontSize: '0.75rem', background: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24', padding: '3px 10px', borderRadius: '20px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={13} /> Admin Automation
            </span>
          </div>

          <p style={{ margin: '0 0 14px 0', fontSize: '0.83rem', color: '#cbd5e1', lineHeight: '1.4' }}>
            Automatically generate full document node structures, set up ML extracted feature metrics, and compute credibility relations for this unverified profile in 1 click.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', alignItems: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600 }}>Preset Document Template Package:</label>
              <select
                className="form-control"
                value={selectedPreset}
                onChange={(e) => setSelectedPreset(e.target.value as any)}
                style={{ padding: '8px 12px', fontSize: '0.85rem', background: 'rgba(15, 23, 42, 0.9)', borderColor: '#38bdf8' }}
              >
                <option value="full">Full Verification Package (Professional - Score ~95)</option>
                <option value="specialist">Technical Specialist Package (Intermediate - Score ~82)</option>
                <option value="business">Registered Business Owner Package (Professional - Score ~88)</option>
              </select>
            </div>

            <div style={{ display: 'flex', gap: '8px', alignSelf: 'flex-end', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn"
                onClick={() => handleAutoPopulateFullNode(selectedPreset)}
                style={{ background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8', border: '1px solid #38bdf8', padding: '8px 14px', fontSize: '0.84rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <Wand2 size={15} /> 1-Click Populate Preview
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={autoCreating || saving}
                onClick={() => handleOneClickAutoCreateAndSave(selectedPreset)}
                style={{ padding: '8px 14px', fontSize: '0.84rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                {autoCreating ? <Loader2 size={15} className="spin" /> : <Zap size={15} />} 1-Click Auto Save
              </button>
            </div>
          </div>
        </div>

        <form onSubmit={handleSaveRelations}>

          {/* SECTION 1: MANUAL DOCUMENTS RELATION CREATION */}
          <div style={{ background: 'rgba(15, 23, 42, 0.65)', borderRadius: '14px', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '20px', marginBottom: '24px' }}>
            <h3 style={{ fontSize: '1.1rem', margin: '0 0 14px 0', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileText size={18} /> 1. Manual Provider Documents Relation (`documents`)
            </h3>

            {/* Add New Document Sub-form */}
            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.08)', marginBottom: '16px' }}>
              <span style={{ fontSize: '0.82rem', color: '#38bdf8', fontWeight: 600, display: 'block', marginBottom: '10px' }}>
                ➕ Create & Attach New Document File Entry:
              </span>

              <div className="grid-2" style={{ marginBottom: '12px' }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label" style={{ fontSize: '0.78rem' }}>Document Category</label>
                  <select
                    className="form-control"
                    value={newDocCategory}
                    onChange={(e) => setNewDocCategory(e.target.value as any)}
                  >
                    <option value="identityDocument">Identity Document (NIC / Passport)</option>
                    <option value="certification">Certification & Qualification</option>
                    <option value="businessRegistration">Business Registration (BR)</option>
                    <option value="experienceProof">Experience Proof & Reference Letter</option>
                    <option value="portfolioWork">Portfolio Work & Project Photo</option>
                  </select>
                </div>

                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label" style={{ fontSize: '0.78rem' }}>Document Title / Name</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="e.g. NIC Front Scan, NVQ Level 4 Certificate..."
                    value={newDocTitle}
                    onChange={(e) => setNewDocTitle(e.target.value)}
                  />
                </div>
              </div>

              <div className="grid-2" style={{ marginBottom: '14px' }}>
                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label" style={{ fontSize: '0.78rem' }}>Upload File (Image/PDF)</label>
                  <input
                    type="file"
                    accept="image/*,.pdf"
                    className="form-control"
                    onChange={handleFileChange}
                    style={{ padding: '6px' }}
                  />
                </div>

                <div className="form-group" style={{ margin: 0 }}>
                  <label className="form-label" style={{ fontSize: '0.78rem' }}>Or Direct File URL</label>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="https://firebasestorage.googleapis.com/..."
                    value={newDocUrl}
                    onChange={(e) => setNewDocUrl(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="button"
                className="btn btn-outline"
                onClick={handleAddManualDocument}
                disabled={uploadingDoc}
                style={{ padding: '8px 16px', fontSize: '0.84rem', borderColor: '#38bdf8', color: '#38bdf8' }}
              >
                {uploadingDoc ? <Loader2 size={14} className="spin" /> : <Plus size={14} />} Attach Document to Relation
              </button>
            </div>

            {/* List of Attached Documents by Category */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
              {[
                { key: 'identityDocument', label: '🪪 Identity Documents', items: docsState.identityDocument || [] },
                { key: 'certification', label: '📜 Certifications', items: docsState.certification || [] },
                { key: 'businessRegistration', label: '🏢 Business Registration', items: docsState.businessRegistration || [] },
                { key: 'experienceProof', label: '💼 Experience Proof', items: docsState.experienceProof || [] },
                { key: 'portfolioWork', label: '🖼️ Portfolio Work', items: docsState.portfolioWork || [] }
              ].map(catGroup => (
                <div key={catGroup.key} style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f8fafc', marginBottom: '8px', display: 'flex', justifyContent: 'space-between' }}>
                    <span>{catGroup.label}</span>
                    <span style={{ color: '#38bdf8' }}>({catGroup.items.length})</span>
                  </div>
                  {catGroup.items.length === 0 ? (
                    <span style={{ fontSize: '0.74rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>No document attached</span>
                  ) : (
                    catGroup.items.map(item => (
                      <div key={item.fileId} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(255,255,255,0.05)', padding: '4px 8px', borderRadius: '6px', marginBottom: '4px', fontSize: '0.76rem' }}>
                        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '140px' }} title={item.fileName}>
                          📄 {item.fileName}
                        </span>
                        <X size={14} color="#fca5a5" style={{ cursor: 'pointer', flexShrink: 0 }} onClick={() => handleRemoveDocument(catGroup.key as any, item.fileId)} />
                      </div>
                    ))
                  )}
                </div>
              ))}
            </div>

          </div>

          {/* SECTION 2: EXTRACTED FEATURES RELATION CONFIGURATION */}
          <div style={{ background: 'rgba(15, 23, 42, 0.65)', borderRadius: '14px', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '20px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
              <h3 style={{ fontSize: '1.1rem', margin: 0, color: '#34d399', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Cpu size={18} /> 2. Manual Extracted Features Relation (`extractedFeatures`)
              </h3>

              <button
                type="button"
                className="btn btn-outline"
                onClick={handleAutoCalculateScore}
                style={{ padding: '6px 12px', fontSize: '0.78rem', borderColor: '#34d399', color: '#34d399' }}
              >
                ⚡ Auto-Compute Credibility Score
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
              
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem' }}>Identity Verified (`identity_verified`)</label>
                <select
                  className="form-control"
                  value={featuresState.identity_verified}
                  onChange={(e) => setFeaturesState({ ...featuresState, identity_verified: Number(e.target.value) })}
                >
                  <option value={1}>1 - Verified Identity</option>
                  <option value={0}>0 - Unverified Identity</option>
                </select>
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem' }}>Business Registered (`business_registered`)</label>
                <select
                  className="form-control"
                  value={featuresState.business_registered}
                  onChange={(e) => setFeaturesState({ ...featuresState, business_registered: Number(e.target.value) })}
                >
                  <option value={1}>1 - Formal BR Registered</option>
                  <option value={0}>0 - Unregistered Business</option>
                </select>
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem' }}>Certification Count (`certification_count`)</label>
                <input
                  type="number"
                  min="0"
                  max="20"
                  className="form-control"
                  value={featuresState.certification_count}
                  onChange={(e) => setFeaturesState({ ...featuresState, certification_count: Number(e.target.value) })}
                />
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem' }}>Highest Cert Level (`highest_cert_level`)</label>
                <select
                  className="form-control"
                  value={featuresState.highest_cert_level}
                  onChange={(e) => setFeaturesState({ ...featuresState, highest_cert_level: e.target.value })}
                >
                  <option value="NVQ Level 4">NVQ Level 4</option>
                  <option value="NVQ Level 3">NVQ Level 3</option>
                  <option value="Vocational Cert">Vocational Certificate</option>
                  <option value="Diploma / Degree">Diploma / Degree</option>
                  <option value="None">None</option>
                </select>
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem' }}>Issuer Reputation (`cert_issuer_reputation` 0-1)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  className="form-control"
                  value={featuresState.cert_issuer_reputation}
                  onChange={(e) => setFeaturesState({ ...featuresState, cert_issuer_reputation: Number(e.target.value) })}
                />
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem' }}>Experience Years (`experience_years`)</label>
                <input
                  type="number"
                  min="0"
                  max="50"
                  className="form-control"
                  value={featuresState.experience_years}
                  onChange={(e) => setFeaturesState({ ...featuresState, experience_years: Number(e.target.value) })}
                />
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem' }}>Reference Count (`experience_reference_count`)</label>
                <input
                  type="number"
                  min="0"
                  max="20"
                  className="form-control"
                  value={featuresState.experience_reference_count}
                  onChange={(e) => setFeaturesState({ ...featuresState, experience_reference_count: Number(e.target.value) })}
                />
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem' }}>Portfolio Count (`portfolio_count`)</label>
                <input
                  type="number"
                  min="0"
                  max="50"
                  className="form-control"
                  value={featuresState.portfolio_count}
                  onChange={(e) => setFeaturesState({ ...featuresState, portfolio_count: Number(e.target.value) })}
                />
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem' }}>Portfolio Quality (`portfolio_quality_score` 0-1)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  className="form-control"
                  value={featuresState.portfolio_quality_score}
                  onChange={(e) => setFeaturesState({ ...featuresState, portfolio_quality_score: Number(e.target.value) })}
                />
              </div>

            </div>

            {/* CREDIBILITY SCORE & TIER OVERRIDE */}
            <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem', color: '#fcd34d' }}>Credibility Score (`credibilityScore` 0-100)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="100"
                  className="form-control"
                  value={credScore}
                  onChange={(e) => setCredScore(Number(e.target.value))}
                />
              </div>

              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label" style={{ fontSize: '0.78rem', color: '#fcd34d' }}>Credibility Level (`credibilityLevel`)</label>
                <select
                  className="form-control"
                  value={credLevel}
                  onChange={(e) => setCredLevel(e.target.value)}
                >
                  <option value="Professional">Professional (85 - 100)</option>
                  <option value="Intermediate">Intermediate (60 - 84)</option>
                  <option value="Beginner">Beginner (0 - 59)</option>
                </select>
              </div>
            </div>

          </div>

          {/* ACTION BUTTONS */}
          <div style={{ display: 'flex', gap: '14px', marginTop: '20px' }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={saving}
              style={{ flex: 1, padding: '12px', fontSize: '0.95rem' }}
            >
              {saving ? <Loader2 size={18} className="spin" /> : <Save size={18} />} Save Manual Documents & Features Relations
            </button>
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClose}
              style={{ padding: '12px 24px', fontSize: '0.95rem' }}
            >
              Cancel
            </button>
          </div>

        </form>
      </div>
    </div>
  );
};
