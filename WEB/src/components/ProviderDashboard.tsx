// ProviderDashboard Component
import React, { useState } from 'react';
import { Briefcase, MapPin, Mail, Phone, Edit3, Save, CheckCircle, Loader2, X, Wrench, Award, Plus, Check, Clock, FileText, ShieldCheck, Lock, Star } from 'lucide-react';
import { DEFAULT_WORKING_HOURS, hasUploadedDocuments, getProviderCredibility } from '../config/firebase';
import type { Provider, WorkingHours } from '../config/firebase';
import {
  deleteProviderDocumentForConfiguredSource,
  openProviderDocumentForConfiguredSource,
  requestProviderVerificationForConfiguredSource,
  updateProviderProfileForConfiguredSource
} from '../services/provider-service';
import { SRI_LANKA_DISTRICTS, getCityCoordinates } from '../data/sriLankaData';
import { LocationMapPicker } from './LocationMapPicker';
import { ImageUploader } from './ImageUploader';
import { WorkingHoursView } from './WorkingHoursView';
import { WorkingHoursEditor } from './WorkingHoursEditor';
import { ProviderDocumentsView } from './ProviderDocumentsView';
import { DocumentUploadModal } from './DocumentUploadModal';
import { WeatherWidget } from './WeatherWidget';
import { ProviderCategoryDemandWidget } from './ProviderCategoryDemandWidget';
import { ProviderBookings } from './ProviderBookings';

interface ProviderDashboardProps {
  currentUser: Provider;
  onUpdateUser: (updatedUser: Provider) => void;
}

import { SERVICE_CATEGORIES, CATEGORY_SKILL_SUGGESTIONS } from '../data/categories';

export const ProviderDashboard: React.FC<ProviderDashboardProps> = ({
  currentUser,
  onUpdateUser
}) => {
  // Provider Edit Modal State
  const [isEditing, setIsEditing] = useState(false);
  const [editFullName, setEditFullName] = useState(currentUser.fullName || '');
  const [editPhone, setEditPhone] = useState(currentUser.phone || '');
  const [editNic, setEditNic] = useState(currentUser.nic || '');
  const [editCategory, setEditCategory] = useState(currentUser.category || SERVICE_CATEGORIES[0]);
  const [editDistrict, setEditDistrict] = useState(currentUser.district || 'Colombo');
  const [editCity, setEditCity] = useState(currentUser.city || 'Dehiwala');
  const [editLocation, setEditLocation] = useState(currentUser.location || { latitude: 6.8511, longitude: 79.8656 });
  const [editProviderImage, setEditProviderImage] = useState(currentUser.providerImage || (currentUser as any).customerImage || '');
  const [editPreferredLanguages, setEditPreferredLanguages] = useState<string[]>(
    currentUser.preferredLanguage ? currentUser.preferredLanguage.split(', ') : ['English', 'Sinhala']
  );
  const [editExperienceYears, setEditExperienceYears] = useState(currentUser.experienceYears || 5);
  const [editSkillsList, setEditSkillsList] = useState<string[]>(currentUser.skills || ['House Wiring', 'Circuit Breaker Installation']);
  const [skillInputText, setSkillInputText] = useState('');
  const [editDescription, setEditDescription] = useState(currentUser.description || '');
  const [editWorkingHours, setEditWorkingHours] = useState<WorkingHours>(
    currentUser.workingHours || DEFAULT_WORKING_HOURS
  );

  // Dedicated Working Hours Modal State
  const [isEditingHours, setIsEditingHours] = useState(false);
  const [updatingHours, setUpdatingHours] = useState(false);
  const [hoursSuccessMsg, setHoursSuccessMsg] = useState('');

  // Document Upload Modal State
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  const handleDeleteDocument = async (category: 'identityDocument' | 'certification' | 'businessRegistration' | 'experienceProof' | 'portfolioWork', fileId: string) => {
    if (!currentUser.id) return;

    if (isVerificationProcessing || currentUser.verified) {
      alert("⚠️ Action Locked: You cannot delete verification documents after submitting a verification request or while your profile is verified.");
      return;
    }

    if (!confirm("Are you sure you want to delete this document?")) return;

    try {
      const updated = await deleteProviderDocumentForConfiguredSource(
        currentUser,
        category,
        fileId
      );
      onUpdateUser(updated);
    } catch (err: any) {
      alert("Failed to delete document: " + err.message);
    }
  };

  const [requestingVerification, setRequestingVerification] = useState(false);
  const [docValidationErrorMsg, setDocValidationErrorMsg] = useState('');

  const handleRequestVerification = async () => {
    if (!currentUser.id) return;
    setDocValidationErrorMsg('');

    // Check if provider has uploaded any documents
    if (!hasUploadedDocuments(currentUser.documents)) {
      setDocValidationErrorMsg("⚠️ Document Upload Required: You cannot request verification without uploading documents. Please click 'Upload Documents & Portfolio' to add your identity, certification, or registration documents first.");
      return;
    }

    setRequestingVerification(true);
    try {
      const updated = await requestProviderVerificationForConfiguredSource(currentUser);
      onUpdateUser(updated);
    } catch (err: any) {
      alert("Failed to submit document verification request: " + err.message);
    } finally {
      setRequestingVerification(false);
    }
  };

  const [updating, setUpdating] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const selectedEditDistrictObj = SRI_LANKA_DISTRICTS.find(d => d.name === editDistrict) || SRI_LANKA_DISTRICTS[0];
  const editCitiesList = selectedEditDistrictObj.cities;

  const handleAddSkill = (skillToAdd?: string) => {
    const text = (skillToAdd || skillInputText).trim();
    if (text && !editSkillsList.includes(text)) {
      setEditSkillsList([...editSkillsList, text]);
      if (!skillToAdd) setSkillInputText('');
    }
  };

  const handleRemoveSkill = (skillToRemove: string) => {
    setEditSkillsList(editSkillsList.filter(s => s !== skillToRemove));
  };

  const handleEditDistrictChange = (newDistrictName: string) => {
    setEditDistrict(newDistrictName);
    const found = SRI_LANKA_DISTRICTS.find(d => d.name === newDistrictName);
    if (found) {
      const defaultCity = found.cities[0] || '';
      setEditCity(defaultCity);
      setEditLocation(getCityCoordinates(newDistrictName, defaultCity));
    }
  };

  const handleEditCityChange = (newCityName: string) => {
    setEditCity(newCityName);
    setEditLocation(getCityCoordinates(editDistrict, newCityName));
  };

  const handleLanguageToggle = (lang: string) => {
    if (editPreferredLanguages.includes(lang)) {
      if (editPreferredLanguages.length === 1) return;
      setEditPreferredLanguages(editPreferredLanguages.filter(l => l !== lang));
    } else {
      setEditPreferredLanguages([...editPreferredLanguages, lang]);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentUser.id) return;

    setUpdating(true);
    setSuccessMsg('');

    try {
      const updated = await updateProviderProfileForConfiguredSource(currentUser, {
        fullName: editFullName.trim(),
        phone: editPhone.trim(),
        nic: editNic.trim(),
        category: editCategory,
        district: editDistrict,
        city: editCity,
        location: editLocation,
        providerImage: editProviderImage,
        preferredLanguage: editPreferredLanguages.join(', '),
        experienceYears: Number(editExperienceYears),
        skills: editSkillsList,
        description: editDescription.trim()
      });

      onUpdateUser(updated);
      setSuccessMsg("Provider profile updated successfully!");
      setTimeout(() => {
        setIsEditing(false);
        setSuccessMsg('');
      }, 1400);
    } catch (err: any) {
      console.error(err);
      alert("Failed to update provider profile: " + err.message);
    } finally {
      setUpdating(false);
    }
  };

  const handleSaveWorkingHours = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentUser.id) return;

    setUpdatingHours(true);
    setHoursSuccessMsg('');

    try {
      const updated = await updateProviderProfileForConfiguredSource(currentUser, {
        workingHours: editWorkingHours
      });

      onUpdateUser(updated);
      setHoursSuccessMsg("Working hours schedule updated successfully!");
      setTimeout(() => {
        setIsEditingHours(false);
        setHoursSuccessMsg('');
      }, 1400);
    } catch (err: any) {
      console.error(err);
      alert("Failed to update working hours: " + err.message);
    } finally {
      setUpdatingHours(false);
    }
  };

  const isVerificationProcessing = !currentUser.verified && currentUser.documents?.status === true && hasUploadedDocuments(currentUser.documents);
  const credibility = getProviderCredibility(currentUser);

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto' }}>

      <ProviderBookings />

      {/* Provider Session Banner */}
      <div className="glass-panel" style={{ padding: '30px', marginBottom: '32px', borderLeft: '6px solid var(--accent-provider)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '22px' }}>
            <img
              src={currentUser.providerImage || (currentUser as any).customerImage || 'https://firebasestorage.googleapis.com/v0/b/service-e333a.appspot.com/o/providers%2Fprovider_default.png?alt=media'}
              alt={currentUser.fullName}
              style={{ width: '82px', height: '82px', borderRadius: '50%', objectFit: 'cover', border: '3px solid var(--accent-provider)', boxShadow: '0 0 18px rgba(16,185,129,0.3)', flexShrink: 0, aspectRatio: '1 / 1' }}
              onError={(e) => {
                (e.target as HTMLElement).setAttribute('src', 'https://api.dicebear.com/7.x/bottts/svg?seed=' + currentUser.fullName);
              }}
            />
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                <h1 style={{ fontSize: '1.7rem', margin: 0 }}>{currentUser.fullName}</h1>
                <span style={{
                  padding: '4px 12px',
                  borderRadius: '16px',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  background: 'rgba(16,185,129,0.2)',
                  color: 'var(--accent-provider)',
                  border: '1px solid rgba(16,185,129,0.4)'
                }}>
                  {currentUser.category || 'Service Provider'}
                </span>
                {currentUser.verified ? (
                  <span style={{
                    padding: '4px 12px',
                    borderRadius: '16px',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    background: 'rgba(16,185,129,0.2)',
                    color: '#34d399',
                    border: '1px solid rgba(16,185,129,0.4)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <CheckCircle size={14} /> Verified Provider
                  </span>
                ) : isVerificationProcessing ? (
                  <span style={{
                    padding: '4px 12px',
                    borderRadius: '16px',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    background: 'rgba(245, 158, 11, 0.25)',
                    color: '#fcd34d',
                    border: '1px solid rgba(245, 158, 11, 0.5)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <Clock size={14} className="spin" /> Verification Request Processing (Status: True)
                  </span>
                ) : (
                  <span style={{
                    padding: '4px 12px',
                    borderRadius: '16px',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    background: 'rgba(239, 68, 68, 0.18)',
                    color: '#fca5a5',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    ⚠️ Documents Unverified
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                <span style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}><Mail size={14} style={{ verticalAlign: 'middle', marginRight: '4px', flexShrink: 0 }} /> {currentUser.email}</span>
                <span><Phone size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.phone}</span>
                <span><MapPin size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.city}, {currentUser.district} District</span>
                <span><Award size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.experienceYears || 5} Years Experience</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            {!currentUser.verified && (
              isVerificationProcessing ? (
                <button
                  type="button"
                  className="btn btn-outline"
                  disabled
                  style={{ padding: '10px 18px', fontSize: '0.9rem', borderColor: '#fcd34d', color: '#fcd34d', cursor: 'not-allowed', opacity: 0.9 }}
                >
                  <Clock size={16} className="spin" /> Document Verification Processing...
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={handleRequestVerification}
                  disabled={requestingVerification}
                  style={{ padding: '10px 18px', fontSize: '0.9rem', borderColor: '#34d399', color: '#34d399', background: 'rgba(52, 211, 153, 0.1)' }}
                >
                  {requestingVerification ? <Loader2 size={16} className="spin" /> : <ShieldCheck size={16} />} Request Document Verification
                </button>
              )
            )}
            <button
              className="btn btn-provider"
              onClick={() => setIsEditing(true)}
              style={{ padding: '10px 18px', fontSize: '0.9rem' }}
            >
              <Edit3 size={16} /> Edit Provider Profile
            </button>
            <button
              className="btn btn-outline"
              onClick={() => setIsEditingHours(true)}
              style={{ padding: '10px 18px', fontSize: '0.9rem', borderColor: '#34d399', color: '#34d399' }}
            >
              <Clock size={16} /> Manage Working Hours
            </button>
            <button
              className="btn btn-outline"
              onClick={() => {
                if (isVerificationProcessing || currentUser.verified) {
                  alert("⚠️ Action Locked: You cannot upload new documents while a document verification request is processing or when your profile is verified.");
                  return;
                }
                setIsUploadModalOpen(true);
              }}
              disabled={isVerificationProcessing || currentUser.verified}
              style={{
                padding: '10px 18px',
                fontSize: '0.9rem',
                borderColor: (isVerificationProcessing || currentUser.verified) ? '#64748b' : '#38bdf8',
                color: (isVerificationProcessing || currentUser.verified) ? '#64748b' : '#38bdf8',
                opacity: (isVerificationProcessing || currentUser.verified) ? 0.6 : 1,
                cursor: (isVerificationProcessing || currentUser.verified) ? 'not-allowed' : 'pointer'
              }}
              title={isVerificationProcessing || currentUser.verified ? 'Document upload is locked while verification is requested or verified' : 'Upload documents and portfolio'}
            >
              {isVerificationProcessing || currentUser.verified ? <Lock size={16} /> : <FileText size={16} />} Upload Documents and Portfolio
            </button>
          </div>
        </div>
      </div>

      {/* DOCUMENT VERIFICATION ERROR BANNER */}
      {docValidationErrorMsg && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: '14px', padding: '16px 20px', marginBottom: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '14px' }}>
          <div style={{ color: '#fca5a5', fontSize: '0.9rem', lineHeight: 1.5 }}>
            {docValidationErrorMsg}
          </div>
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => setIsUploadModalOpen(true)}
            style={{ padding: '6px 14px', fontSize: '0.82rem', borderColor: '#fca5a5', color: '#fca5a5', whiteSpace: 'nowrap' }}
          >
            <Plus size={14} /> Upload Documents Now
          </button>
        </div>
      )}

      {/* FULL WEATHER FORECAST BANNER */}
      <div style={{ marginBottom: '28px' }}>
        <WeatherWidget
          location={currentUser.location}
          city={currentUser.city}
          district={currentUser.district}
        />
      </div>

      {/* RIGHT MAIN CONTENT COLUMN */}
      <div>

        {/* DOCUMENT VERIFICATION PROCESSING STATUS NOTICE */}
        {isVerificationProcessing && (
          <div style={{ background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.4)', borderRadius: '14px', padding: '18px 22px', marginBottom: '28px', display: 'flex', alignItems: 'center', gap: '16px' }}>
            <Clock size={28} color="#fcd34d" className="spin" style={{ flexShrink: 0 }} />
            <div>
              <h4 style={{ margin: 0, color: '#fcd34d', fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                Document Verification Request Processing
              </h4>
              <p style={{ margin: '6px 0 0 0', color: 'var(--text-muted)', fontSize: '0.88rem', lineHeight: 1.5 }}>
                Your verification request has been received. System administrators are reviewing your uploaded identity cards, NVQ certificates, BR files, and portfolio documents. You will be notified once verified!
              </p>
            </div>
          </div>
        )}

        {/* CREDIBILITY & SYSTEM VERIFICATION EVALUATION CARD */}
        {credibility && (
          <div className="glass-panel" style={{ padding: '24px', marginBottom: '32px', borderLeft: '6px solid #276221', background: '#ffffff', border: '1px solid #276221' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '1.2rem', margin: 0, display: 'flex', alignItems: 'center', gap: '10px', color: '#276221' }}>
                <ShieldCheck color="#276221" size={24} /> Credibility and System Verification Evaluation
              </h3>
              <span style={{ fontSize: '0.8rem', color: '#64748b', background: '#ffffff', border: '1px solid #276221', padding: '4px 12px', borderRadius: '12px' }}>
                🕒 Last Evaluated: {credibility.lastEvaluatedAt ? new Date(credibility.lastEvaluatedAt).toLocaleString() : 'Recently'}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '18px' }}>
              <div style={{ background: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #276221' }}>
                <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Credibility Level</span>
                <strong style={{ fontSize: '1.15rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Star size={18} fill="#fcd34d" color="#fcd34d" /> {credibility.credibilityLevel || 'Professional'}
                </strong>
              </div>

              <div style={{ background: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #276221' }}>
                <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Credibility Score</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <strong style={{ fontSize: '1.3rem', color: '#10b981' }}>
                    {credibility.credibilityScore !== undefined ? credibility.credibilityScore : 90}%
                  </strong>
                  <div style={{ flex: 1, background: '#f1f5f9', height: '8px', borderRadius: '4px', overflow: 'hidden', border: '1px solid #276221' }}>
                    <div style={{ width: `${Math.min(credibility.credibilityScore || 90, 100)}%`, height: '100%', background: '#276221' }} />
                  </div>
                </div>
              </div>

              <div style={{ background: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #276221' }}>
                <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Verification Status</span>
                <strong style={{ fontSize: '1.05rem', color: currentUser.verified ? '#10b981' : '#f59e0b' }}>
                  {currentUser.verified ? '✓ Verified & Authenticated' : '⏳ Evaluation Complete'}
                </strong>
              </div>
            </div>
          </div>
        )}

        {/* PROVIDER'S SPECIFIC CATEGORY DEMAND TIMETABLE WIDGET */}
        <ProviderCategoryDemandWidget
          category={currentUser.category || 'Electricians'}
          providerName={currentUser.fullName}
        />

        {/* PROVIDER DETAILS VIEW CARD */}
        <div className="glass-panel" style={{ padding: '30px', marginBottom: '32px', background: '#ffffff', border: '1px solid #276221' }}>
          <h2 style={{ fontSize: '1.4rem', marginBottom: '18px', display: 'flex', alignItems: 'center', gap: '10px', borderBottom: '1px solid #cbd5e1', paddingBottom: '12px', color: '#1e293b' }}>
            <Briefcase color="#276221" /> My Public Service Profile Details
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '20px', marginBottom: '24px' }}>
            <div style={{ background: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #276221' }}>
              <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Service Category</span>
              <strong style={{ fontSize: '1.05rem', color: '#276221' }}>{currentUser.category || 'Electricians'}</strong>
            </div>

            <div style={{ background: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #276221' }}>
              <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>NIC Number</span>
              <strong style={{ fontSize: '1.05rem', color: '#1e293b' }}>{currentUser.nic || '199012345678'}</strong>
            </div>

            <div style={{ background: '#ffffff', padding: '16px', borderRadius: '12px', border: '1px solid #276221' }}>
              <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Preferred Languages</span>
              <strong style={{ fontSize: '1.05rem', color: '#1e293b' }}>{currentUser.preferredLanguage}</strong>
            </div>
          </div>

          {/* Skills Tag Section */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '1.05rem', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px', color: '#1e293b' }}>
              <Wrench size={18} color="#276221" /> Specialized Skills and Capabilities
            </h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {currentUser.skills && currentUser.skills.length > 0 ? (
                currentUser.skills.map(s => (
                  <span
                    key={s}
                    style={{
                      background: '#ffffff',
                      border: '1px solid #276221',
                      color: '#276221',
                      padding: '6px 14px',
                      borderRadius: '20px',
                      fontSize: '0.88rem',
                      fontWeight: 600
                    }}
                  >
                    {s}
                  </span>
                ))
              ) : (
                <span style={{ color: '#64748b', fontStyle: 'italic' }}>No skills added yet. Click Edit Profile to add skills.</span>
              )}
            </div>
          </div>

          {/* Bio / Description */}
          {currentUser.description && (
            <div style={{ marginBottom: '24px', background: '#ffffff', padding: '18px', borderRadius: '14px', border: '1px solid #276221' }}>
              <h3 style={{ fontSize: '1.02rem', marginBottom: '6px', color: '#1e293b' }}>Bio / Service Description</h3>
              <p style={{ color: '#64748b', fontSize: '0.92rem', lineHeight: 1.5, margin: 0 }}>
                {currentUser.description}
              </p>
            </div>
          )}

          {/* GPS Location Pin */}
          {currentUser.location && (
            <div style={{ background: '#ffffff', padding: '14px 18px', borderRadius: '12px', border: '1px solid #276221', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', fontWeight: 600 }}>Service Area GPS Pin</span>
                <strong style={{ color: '#276221', fontSize: '0.92rem' }}>
                  📍 Latitude: {currentUser.location.latitude} | Longitude: {currentUser.location.longitude}
                </strong>
              </div>
              <span style={{ fontSize: '0.8rem', color: '#276221', background: '#ffffff', border: '1px solid #276221', padding: '4px 10px', borderRadius: '8px', fontWeight: 600 }}>
                Active on Map
              </span>
            </div>
          )}

          {/* Working Hours Weekly Schedule */}
          <WorkingHoursView
            workingHours={currentUser.workingHours}
            onEditClick={() => setIsEditingHours(true)}
          />

          {/* Provider Verification Documents & Credentials Portfolio */}
          <ProviderDocumentsView
            documents={currentUser.documents}
            canManage={true}
            isLocked={isVerificationProcessing || currentUser.verified}
            onOpenUploadModal={() => setIsUploadModalOpen(true)}
            onDeleteDocument={handleDeleteDocument}
            onOpenDocument={(category, item) =>
              openProviderDocumentForConfiguredSource(currentUser, category, item)
            }
          />

        </div>
      </div>

      {/* PROVIDER EDIT PROFILE MODAL */}
      {isEditing && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '680px', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
              <h2 style={{ fontSize: '1.4rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Edit3 color="var(--accent-provider)" size={22} /> Edit Provider Profile
              </h2>
              <button
                onClick={() => setIsEditing(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {successMsg && (
              <div style={{ background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', color: '#6ee7b7', padding: '10px 14px', borderRadius: '10px', fontSize: '0.88rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle size={16} /> {successMsg}
              </div>
            )}

            <form onSubmit={handleSaveProfile}>

              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  className="form-control"
                  value={editFullName}
                  onChange={(e) => setEditFullName(e.target.value)}
                  required
                />
              </div>

              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Phone Number</label>
                  <input
                    type="tel"
                    className="form-control"
                    value={editPhone}
                    onChange={(e) => setEditPhone(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">NIC Number</label>
                  <input
                    type="text"
                    className="form-control"
                    value={editNic}
                    onChange={(e) => setEditNic(e.target.value)}
                  />
                </div>
              </div>

              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Service Category</label>
                  <select
                    className="form-control"
                    value={editCategory}
                    onChange={(e) => setEditCategory(e.target.value)}
                  >
                    {SERVICE_CATEGORIES.map(cat => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Experience (Years)</label>
                  <input
                    type="number"
                    min="0"
                    max="50"
                    className="form-control"
                    value={editExperienceYears}
                    onChange={(e) => setEditExperienceYears(Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">District</label>
                  <select
                    className="form-control"
                    value={editDistrict}
                    onChange={(e) => handleEditDistrictChange(e.target.value)}
                  >
                    {SRI_LANKA_DISTRICTS.map(d => (
                      <option key={d.name} value={d.name}>{d.name} District</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">City / Town</label>
                  <select
                    className="form-control"
                    value={editCity}
                    onChange={(e) => handleEditCityChange(e.target.value)}
                  >
                    {editCitiesList.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Map Location update */}
              <div className="form-group">
                <LocationMapPicker
                  location={editLocation}
                  onChange={setEditLocation}
                  centerLat={editLocation.latitude}
                  centerLng={editLocation.longitude}
                  selectedCityName={editCity}
                />
              </div>

              {/* Profile Image update */}
              <ImageUploader
                label="Provider Profile Image"
                imageValue={editProviderImage}
                onChange={setEditProviderImage}
                accentColor="var(--accent-provider)"
              />

              {/* Interactive Skills Manager */}
              <div className="form-group" style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '18px', borderRadius: '14px', border: '1px solid rgba(16, 185, 129, 0.25)', margin: '18px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <label className="form-label" style={{ margin: 0 }}>
                    <Wrench size={16} color="var(--accent-provider)" /> Specialized Skills
                  </label>
                  <span style={{ fontSize: '0.78rem', background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', padding: '2px 8px', borderRadius: '10px', fontWeight: 600 }}>
                    {editSkillsList.length} Skills
                  </span>
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
                  {editSkillsList.map(skill => (
                    <div
                      key={skill}
                      style={{
                        background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.25) 0%, rgba(6, 182, 212, 0.25) 100%)',
                        border: '1px solid rgba(16, 185, 129, 0.4)',
                        color: '#ffffff',
                        padding: '4px 12px',
                        borderRadius: '16px',
                        fontSize: '0.84rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <span>{skill}</span>
                      <X size={14} style={{ cursor: 'pointer' }} onClick={() => handleRemoveSkill(skill)} />
                    </div>
                  ))}
                </div>

                <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Type skill and press Enter..."
                    value={skillInputText}
                    onChange={(e) => setSkillInputText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddSkill();
                      }
                    }}
                  />
                  <button type="button" className="btn btn-provider" onClick={() => handleAddSkill()} style={{ padding: '8px 14px' }}>
                    <Plus size={14} /> Add
                  </button>
                </div>

                {/* Suggestions */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {(CATEGORY_SKILL_SUGGESTIONS[editCategory] || CATEGORY_SKILL_SUGGESTIONS["Electricians"] || []).map(sug => {
                    const added = editSkillsList.includes(sug);
                    return (
                      <button
                        key={sug}
                        type="button"
                        onClick={() => handleAddSkill(sug)}
                        disabled={added}
                        style={{
                          background: added ? 'rgba(255, 255, 255, 0.04)' : 'rgba(255, 255, 255, 0.08)',
                          border: '1px solid rgba(255, 255, 255, 0.15)',
                          color: added ? 'var(--text-dim)' : 'var(--text-main)',
                          padding: '3px 8px',
                          borderRadius: '10px',
                          fontSize: '0.74rem',
                          cursor: added ? 'default' : 'pointer'
                        }}
                      >
                        {added ? '✓ ' : '+ '} {sug}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Description */}
              <div className="form-group">
                <label className="form-label">Bio / Description</label>
                <textarea
                  className="form-control"
                  rows={3}
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                />
              </div>

              {/* Preferred Languages */}
              <div className="form-group" style={{ marginTop: '16px' }}>
                <label className="form-label">Preferred Languages</label>
                <div className="language-options">
                  {[
                    { id: 'English', label: '🇬🇧 English' },
                    { id: 'Sinhala', label: '🇱🇰 Sinhala (සිංහල)' },
                    { id: 'Tamil', label: '🇱🇰 Tamil (தமிழ்)' }
                  ].map((lang) => {
                    const isSelected = editPreferredLanguages.includes(lang.id);
                    return (
                      <div
                        key={lang.id}
                        className={`lang-pill ${isSelected ? 'active' : ''}`}
                        onClick={() => handleLanguageToggle(lang.id)}
                        style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                      >
                        {isSelected && <Check size={14} />}
                        {lang.label}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Save Button */}
              <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                <button
                  type="submit"
                  className="btn btn-provider"
                  style={{ flex: 1, padding: '12px' }}
                  disabled={updating}
                >
                  {updating ? <Loader2 size={16} className="spin" /> : <Save size={16} />} Save Provider Details
                </button>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setIsEditing(false)}
                >
                  Cancel
                </button>
              </div>

            </form>
          </div>
        </div>
      )}

      {/* DEDICATED WORKING HOURS EDIT MODAL */}
      {isEditingHours && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '640px', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
              <h2 style={{ fontSize: '1.35rem', display: 'flex', alignItems: 'center', gap: '8px', color: '#34d399' }}>
                <Clock size={22} /> Manage Working Hours and Operating Days
              </h2>
              <button
                onClick={() => setIsEditingHours(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {hoursSuccessMsg && (
              <div style={{ background: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981', color: '#6ee7b7', padding: '10px 14px', borderRadius: '10px', fontSize: '0.88rem', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle size={16} /> {hoursSuccessMsg}
              </div>
            )}

            <form onSubmit={handleSaveWorkingHours}>
              <WorkingHoursEditor
                workingHours={editWorkingHours}
                onChange={setEditWorkingHours}
              />

              <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
                <button
                  type="submit"
                  className="btn btn-provider"
                  style={{ flex: 1, padding: '12px' }}
                  disabled={updatingHours}
                >
                  {updatingHours ? <Loader2 size={16} className="spin" /> : <Save size={16} />} Save Working Hours
                </button>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setIsEditingHours(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DEDICATED DOCUMENT UPLOAD MODAL */}
      {isUploadModalOpen && currentUser.id && (
        <DocumentUploadModal
          provider={currentUser}
          onClose={() => setIsUploadModalOpen(false)}
          onSuccess={onUpdateUser}
        />
      )}

    </div>
  );
};
