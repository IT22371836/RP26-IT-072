import React, { useEffect, useState } from 'react';
import { Database, UserCheck, Briefcase, MapPin, Mail, Phone, Globe, RefreshCw, Search, Filter, X, Shield, LogIn, FileText, Cpu, Calendar, Settings } from 'lucide-react';
import { fetchCustomers, fetchFilterRequests, fetchDailyDemand, hasUploadedDocuments, getUploadedDocumentCount, getProviderExtractedFeatures, getProviderCredibility } from '../config/firebase';
import type { Customer, Provider, FilterRequestItem, DailyDemandData } from '../config/firebase';
import {
  listAdminProvidersForConfiguredSource,
  setProviderVerificationForConfiguredSource
} from '../services/admin-service';
import rtdbSeedData from '../data/service-e333a-default-rtdb-export.json';
import { SRI_LANKA_DISTRICTS } from '../data/sriLankaData';
import { WeatherWidget } from './WeatherWidget';
import { ProviderDocumentsView } from './ProviderDocumentsView';
import { ProvidersFilterHistoryView } from './ProvidersFilterHistoryView';
import { WeeklyDemandTimetable } from './WeeklyDemandTimetable';
import { SERVICE_CATEGORIES } from '../data/categories';
import { AdminManualRelationsModal } from './AdminManualRelationsModal';
import { openProviderDocumentForConfiguredSource } from '../services/provider-service';
import { AdminPipelineAudit } from './AdminPipelineAudit';

interface DashboardProps {
  currentUser: any | null;
  onUpdateUser: (user: any) => void;
  onNavigateRegister: (role: 'customer' | 'provider') => void;
  onLogout?: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  currentUser,
  onUpdateUser: _onUpdateUser,
  onNavigateRegister,
  onLogout: _onLogout
}) => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [filterRequests, setFilterRequests] = useState<FilterRequestItem[]>([]);
  const [demandData, setDemandData] = useState<DailyDemandData | null>(null);
  const [activeTab, setActiveTab] = useState<'customers' | 'providers' | 'filterHistory' | 'weeklyDemand' | 'pipelineAudit'>(
    currentUser && currentUser.role === 'customer' ? 'providers' : 'customers'
  );
  const [loading, setLoading] = useState(true);

  // Search & Filter State for Providers
  const [categoryFilter, setCategoryFilter] = useState<string>('All');
  const [districtFilter, setDistrictFilter] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Admin Documents Review Modal State
  const [selectedProviderForDocs, setSelectedProviderForDocs] = useState<Provider | null>(null);

  // Admin Manual Documents & Extracted Features Setup Modal State (Unverified Profiles Only)
  const [manualRelationsProvider, setManualRelationsProvider] = useState<Provider | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [cList, pList, frList, dData] = await Promise.all([
        fetchCustomers(),
        listAdminProvidersForConfiguredSource(),
        fetchFilterRequests(),
        fetchDailyDemand()
      ]);

      setDemandData(dData);

      if (cList.length === 0 && rtdbSeedData.customers) {
        const seedC = Object.keys(rtdbSeedData.customers).map(k => ({ id: k, ...(rtdbSeedData.customers as any)[k] }));
        setCustomers(seedC);
      } else {
        setCustomers(cList);
      }

      if (pList.length === 0 && rtdbSeedData.providers) {
        const seedP = Object.keys(rtdbSeedData.providers).map(k => ({ id: k, ...(rtdbSeedData.providers as any)[k] }));
        setProviders(seedP);
      } else {
        setProviders(pList);
      }

      if (frList.length === 0 && rtdbSeedData.filter_requests) {
        const seedFR = Object.keys(rtdbSeedData.filter_requests).map(k => ({
          id: k,
          request_id: (rtdbSeedData.filter_requests as any)[k].request_id || k,
          ...(rtdbSeedData.filter_requests as any)[k]
        }));
        setFilterRequests(seedFR);
      } else {
        setFilterRequests(frList);
      }
    } catch (err) {
      console.error("Error loading database items:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);



  // Filtered Providers list for Customer Browse View
  const filteredProviders = providers.filter(p => {
    const matchesCategory = categoryFilter === 'All' || (p.category && p.category.toLowerCase().includes(categoryFilter.toLowerCase()));
    const matchesDistrict = districtFilter === 'All' || p.district === districtFilter;
    const query = searchQuery.trim().toLowerCase();
    const matchesSearch = !query ||
      p.fullName.toLowerCase().includes(query) ||
      (p.category && p.category.toLowerCase().includes(query)) ||
      (p.skills && p.skills.some(s => s.toLowerCase().includes(query))) ||
      p.city.toLowerCase().includes(query);

    return matchesCategory && matchesDistrict && matchesSearch;
  });

  // Check if non-admin user is attempting to access Database View directly
  if (!currentUser || currentUser.role !== 'admin') {
    return (
      <div className="glass-panel" style={{ maxWidth: '600px', margin: '60px auto', padding: '40px', textAlign: 'center' }}>
        <div style={{
          width: '64px',
          height: '64px',
          borderRadius: '20px',
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '16px',
          color: '#fca5a5'
        }}>
          <Shield size={32} />
        </div>
        <h2 style={{ fontSize: '1.6rem', marginBottom: '8px' }}>Admin Access Restricted</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginBottom: '24px' }}>
          Database View privileges are restricted to System Administrators only.
        </p>
        <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '14px 18px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.08)', marginBottom: '24px', textAlign: 'left', fontSize: '0.86rem' }}>
          <span style={{ color: 'var(--accent-customer)', fontWeight: 600, display: 'block', marginBottom: '6px' }}>🔑 Backend authorization required</span>
          <div>Administrator accounts and credentials are managed by FastAPI.</div>
        </div>
        <button
          className="btn btn-primary"
          style={{ padding: '12px 24px', fontSize: '0.95rem' }}
          onClick={() => onNavigateRegister('customer')}
        >
          <LogIn size={18} /> Switch to Login View
        </button>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto' }}>

      {/* Current User Session Banner with Profile Check & Update */}
      {currentUser && (
        <div className="glass-panel" style={{ padding: '24px', marginBottom: '30px', borderLeft: `6px solid ${currentUser.role === 'customer' ? 'var(--accent-customer)' : 'var(--accent-provider)'}` }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '18px' }}>
              <img
                src={(currentUser.role === 'provider' ? currentUser.providerImage || currentUser.customerImage : currentUser.customerImage || currentUser.providerImage) || 'https://api.dicebear.com/7.x/avataaars/svg?seed=Default'}
                alt={currentUser.fullName}
                style={{ width: '72px', height: '72px', borderRadius: '50%', objectFit: 'cover', border: `3px solid ${currentUser.role === 'customer' ? 'var(--accent-customer)' : 'var(--accent-provider)'}`, flexShrink: 0, aspectRatio: '1 / 1' }}
                onError={(e) => {
                  (e.target as HTMLElement).setAttribute('src', 'https://api.dicebear.com/7.x/bottts/svg?seed=' + currentUser.fullName);
                }}
              />
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <h2 style={{ fontSize: '1.4rem' }}>{currentUser.fullName}</h2>
                  <span style={{
                    padding: '3px 10px',
                    borderRadius: '12px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    background: currentUser.role === 'customer' ? 'rgba(139,92,246,0.2)' : 'rgba(39, 98, 33, 0.12)',
                    color: currentUser.role === 'customer' ? 'var(--accent-customer)' : '#276221',
                    border: `1px solid ${currentUser.role === 'customer' ? 'rgba(139,92,246,0.4)' : '#276221'}`
                  }}>
                    Active {currentUser.role} Session
                  </span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', color: 'var(--text-muted)', fontSize: '0.86rem' }}>
                  <span><Mail size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.email}</span>
                  <span><Phone size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.phone}</span>
                  <span><MapPin size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.city}, {currentUser.district} District</span>
                  <span><Globe size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.preferredLanguage}</span>
                </div>
              </div>
            </div>

            {/* Profile Action Buttons */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>

              {currentUser.location && (
                <span style={{ fontSize: '0.78rem', color: '#276221', background: '#ffffff', padding: '4px 10px', borderRadius: '8px', border: '1px solid #276221', fontWeight: 600 }}>
                  📍 Lat: {currentUser.location.latitude.toFixed(4)}, Lon: {currentUser.location.longitude.toFixed(4)}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* FULL WEATHER FORECAST BANNER */}
      {currentUser && (
        <div style={{ marginBottom: '28px' }}>
          <WeatherWidget
            location={currentUser.location}
            city={currentUser.city}
            district={currentUser.district}
          />
        </div>
      )}

      {/* RIGHT MAIN CONTENT COLUMN */}
      <div>
        {/* Quick Stats Overview */}

        {/* Main Database Section Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '1.6rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Database color="var(--primary)" /> Realtime Database Hub
            </h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
              Synchronized with Firebase Realtime Database & Firebase Storage
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              className="btn btn-outline"
              onClick={loadData}
              style={{ padding: '8px 14px', fontSize: '0.85rem' }}
            >
              <RefreshCw size={14} /> Refresh
            </button>
            {/* <button
              className="btn btn-primary"
              onClick={handleSeedFirebase}
              disabled={seeding}
              style={{ padding: '8px 14px', fontSize: '0.85rem' }}
            >
              <Sparkles size={14} /> {seeding ? 'Seeding...' : 'Seed RTDB Data'}
            </button> */}
          </div>
        </div>

        {/* Database Switcher Tabs */}
        <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap' }}>
          <button
            className={`btn ${activeTab === 'providers' ? 'btn-customer' : 'btn-outline'}`}
            onClick={() => setActiveTab('providers')}
          >
            <Briefcase size={18} /> Service Providers Directory ({providers.length})
          </button>
          <button
            className={`btn ${activeTab === 'customers' ? 'btn-customer' : 'btn-outline'}`}
            onClick={() => setActiveTab('customers')}
          >
            <UserCheck size={18} /> Customers Node ({customers.length})
          </button>
          <button
            className={`btn ${activeTab === 'filterHistory' ? 'btn-customer' : 'btn-outline'}`}
            onClick={() => setActiveTab('filterHistory')}
          >
            <Cpu size={18} /> Providers Filter History ({filterRequests.length})
          </button>
          <button
            className={`btn ${activeTab === 'weeklyDemand' ? 'btn-customer' : 'btn-outline'}`}
            onClick={() => setActiveTab('weeklyDemand')}
          >
            <Calendar size={18} /> Weekly Demand Timetable
          </button>
          {currentUser?.role === 'admin' && <button
            className={`btn ${activeTab === 'pipelineAudit' ? 'btn-customer' : 'btn-outline'}`}
            onClick={() => setActiveTab('pipelineAudit')}
          >
            <Cpu size={18} /> Pipeline Audit
          </button>}
        </div>

        {/* Search & Filter Bar when viewing Service Providers */}
        {activeTab === 'providers' && (
          <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px', border: '1px solid #276221', background: 'transparent' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px', alignItems: 'center' }}>

              {/* Keyword Search */}
              <div style={{ position: 'relative' }}>
                <Search size={16} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  className="form-control"
                  placeholder="Search provider name or skill..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ paddingLeft: '38px' }}
                />
              </div>

              {/* Category Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Filter size={16} color="var(--accent-provider)" />
                <select
                  className="form-control"
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                >
                  <option value="All">All Categories</option>
                  {SERVICE_CATEGORIES.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>

              {/* District Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <MapPin size={16} color="var(--accent-provider)" />
                <select
                  className="form-control"
                  value={districtFilter}
                  onChange={(e) => setDistrictFilter(e.target.value)}
                >
                  <option value="All">All Sri Lanka Districts</option>
                  {SRI_LANKA_DISTRICTS.map(d => (
                    <option key={d.name} value={d.name}>{d.name} District</option>
                  ))}
                </select>
              </div>

            </div>
          </div>
        )}

        {/* Loading state */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px' }}>
            <p style={{ color: 'var(--text-muted)' }}>Loading database records from Firebase...</p>
          </div>
        ) : activeTab === 'pipelineAudit' ? (
          <AdminPipelineAudit />
        ) : activeTab === 'weeklyDemand' ? (
          /* Weekly Demand Timetable (daily_demand Node) View */
          <WeeklyDemandTimetable
            demandData={demandData}
            loading={loading}
            onRefresh={loadData}
          />
        ) : activeTab === 'filterHistory' ? (
          /* Providers Filter History (ML Node) View */
          <ProvidersFilterHistoryView
            filterRequests={filterRequests}
            customers={customers}
            providers={providers}
            loading={loading}
            onRefresh={loadData}
          />
        ) : activeTab === 'customers' ? (
          /* Customers List */
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
            {customers.map((c) => (
              <div key={c.id || c.email} className="glass-panel glass-panel-hover" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '14px' }}>
                  <img
                    src={c.customerImage || 'https://api.dicebear.com/7.x/avataaars/svg?seed=' + c.fullName}
                    alt={c.fullName}
                    style={{ width: '52px', height: '52px', borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--accent-customer)', flexShrink: 0, aspectRatio: '1 / 1' }}
                    onError={(e) => {
                      (e.target as HTMLElement).setAttribute('src', 'https://api.dicebear.com/7.x/bottts/svg?seed=' + c.fullName);
                    }}
                  />
                  <div>
                    <h3 style={{ fontSize: '1.1rem' }}>{c.fullName}</h3>
                    <span style={{ fontSize: '0.78rem', color: 'var(--accent-customer)', fontWeight: 600 }}>Customer</span>
                  </div>
                </div>

                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}><Mail size={14} style={{ verticalAlign: 'middle', marginRight: '6px', flexShrink: 0 }} /> {c.email}</div>
                  <div><Phone size={14} style={{ verticalAlign: 'middle', marginRight: '6px' }} /> {c.phone}</div>
                  <div><MapPin size={14} style={{ verticalAlign: 'middle', marginRight: '6px' }} /> {c.city}, {c.district} District</div>
                  <div><Globe size={14} style={{ verticalAlign: 'middle', marginRight: '6px' }} /> Languages: <strong>{c.preferredLanguage}</strong></div>
                  {c.location && (
                    <div style={{ marginTop: '4px', border: '1px solid #276221', padding: '6px 10px', borderRadius: '8px', fontSize: '0.78rem', color: '#276221', fontWeight: 600 }}>
                      📍 GPS: Lat {c.location.latitude}, Lng {c.location.longitude}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* Providers Directory List */
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '20px' }}>
            {filteredProviders.length === 0 ? (
              <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                No service providers found matching your filters.
              </div>
            ) : (
              filteredProviders.map((p) => (
                <div key={p.id || p.email} className="glass-panel glass-panel-hover" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '14px' }}>
                    <img
                      src={p.providerImage || (p as any).customerImage || 'https://firebasestorage.googleapis.com/v0/b/service-e333a.appspot.com/o/providers%2Fprovider_default.png?alt=media'}
                      alt={p.fullName}
                      style={{ width: '58px', height: '58px', borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--accent-provider)', flexShrink: 0, aspectRatio: '1 / 1' }}
                      onError={(e) => {
                        (e.target as HTMLElement).setAttribute('src', 'https://api.dicebear.com/7.x/bottts/svg?seed=' + p.fullName);
                      }}
                    />
                    <div>
                      <h3 style={{ fontSize: '1.15rem' }}>{p.fullName}</h3>
                      <span style={{ fontSize: '0.8rem', color: '#276221', border: '1px solid #276221', padding: '2px 8px', borderRadius: '6px', fontWeight: 600, display: 'inline-block', marginTop: '2px' }}>
                        {p.category || 'Service Provider'}
                      </span>
                    </div>
                  </div>

                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}><Mail size={14} style={{ verticalAlign: 'middle', marginRight: '6px', flexShrink: 0 }} /> {p.email}</div>
                    <div><Phone size={14} style={{ verticalAlign: 'middle', marginRight: '6px' }} /> {p.phone}</div>
                    <div><MapPin size={14} style={{ verticalAlign: 'middle', marginRight: '6px' }} /> {p.city}, {p.district} District</div>
                    {p.experienceYears !== undefined && (
                      <div>⭐ Experience: <strong>{p.experienceYears} Years</strong></div>
                    )}
                    {p.skills && p.skills.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px' }}>
                        {p.skills.map(skill => (
                          <span key={skill} style={{ border: '1px solid #276221', color: '#276221', background: 'rgba(39, 98, 33, 0.12)', fontSize: '0.74rem', padding: '2px 8px', borderRadius: '12px', fontWeight: 600 }}>
                            {skill}
                          </span>
                        ))}
                      </div>
                    )}
                    {p.location && (
                      <div style={{ marginTop: '6px', border: '1px solid #276221', padding: '6px 10px', borderRadius: '8px', fontSize: '0.78rem', color: '#276221', fontWeight: 600 }}>
                        📍 GPS: Lat {p.location.latitude}, Lng {p.location.longitude}
                      </div>
                    )}

                    {/* ADMIN EXTRACTED FEATURES DATA PANEL */}
                    {getProviderExtractedFeatures(p) && (
                      <div style={{ marginTop: '10px', border: '1px solid #276221', padding: '10px 12px', borderRadius: '8px', fontSize: '0.78rem' }}>
                        <strong style={{ color: '#276221', display: 'block', marginBottom: '6px', fontSize: '0.8rem' }}>
                          Extracted Features Analytics Data:
                        </strong>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 10px', color: '#1e293b' }}>
                          <div>• Category: <strong>{getProviderExtractedFeatures(p)?.service_category}</strong></div>
                          <div>• ID Verified: <strong>{getProviderExtractedFeatures(p)?.identity_verified === 1 ? 'Yes (1)' : 'No (0)'}</strong></div>
                          <div>• BR Registered: <strong>{getProviderExtractedFeatures(p)?.business_registered === 1 ? 'Yes (1)' : 'No (0)'}</strong></div>
                          <div>• Cert Count: <strong>{getProviderExtractedFeatures(p)?.certification_count}</strong></div>
                          <div>• Highest Cert: <strong>{getProviderExtractedFeatures(p)?.highest_cert_level}</strong></div>
                          <div>• Issuer Rep: <strong>{getProviderExtractedFeatures(p)?.cert_issuer_reputation}</strong></div>
                          <div>• Exp Years: <strong>{getProviderExtractedFeatures(p)?.experience_years} yrs</strong></div>
                          <div>• Ref Count: <strong>{getProviderExtractedFeatures(p)?.experience_reference_count}</strong></div>
                          <div>• Portfolio Count: <strong>{getProviderExtractedFeatures(p)?.portfolio_count}</strong></div>
                          <div>• Portfolio Quality: <strong>{getProviderExtractedFeatures(p)?.portfolio_quality_score}</strong></div>
                          <div>• Credibility Level: <strong style={{ color: '#f59e0b' }}>{getProviderCredibility(p)?.credibilityLevel || 'Professional'}</strong></div>
                          <div>• Credibility Score: <strong style={{ color: '#276221' }}>{getProviderCredibility(p)?.credibilityScore}%</strong></div>
                        </div>
                        {getProviderCredibility(p)?.lastEvaluatedAt && (
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '6px' }}>
                            🕒 Evaluated: {new Date(getProviderCredibility(p)?.lastEvaluatedAt ?? Date.now()).toLocaleString()}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Admin Verification Control Action */}
                    <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.76rem', color: p.verified ? '#34d399' : (p.documents?.status && hasUploadedDocuments(p.documents)) ? '#fcd34d' : '#fca5a5', fontWeight: 600 }}>
                        {p.verified ? '✓ System Verified' : (p.documents?.status && hasUploadedDocuments(p.documents)) ? '⏳ Verification Request (Status: True)' : '⚠️ Unverified'}
                      </span>
                      <button
                        type="button"
                        className="btn"
                        style={{
                          fontSize: '0.74rem',
                          padding: '4px 10px',
                          background: p.verified ? 'rgba(239,68,68,0.15)' : 'rgba(16,185,129,0.2)',
                          border: `1px solid ${p.verified ? 'rgba(239,68,68,0.3)' : '#10b981'}`,
                          color: p.verified ? '#fca5a5' : '#34d399',
                          borderRadius: '8px'
                        }}
                        onClick={async () => {
                          if (p.id) {
                            await setProviderVerificationForConfiguredSource(p, !p.verified);
                            loadData();
                          }
                        }}
                      >
                        {p.verified ? 'Revoke Verification' : '✔ Approve & Verify'}
                      </button>
                    </div>

                    {/* Button for Admin to Check Uploaded Documents */}
                    <div style={{ marginTop: '10px' }}>
                      <button
                        type="button"
                        onClick={() => setSelectedProviderForDocs(p)}
                        style={{
                          width: '100%',
                          padding: '8px 12px',
                          background: (p.documents?.status && hasUploadedDocuments(p.documents))
                            ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.25) 0%, rgba(217, 119, 6, 0.25) 100%)'
                            : 'rgba(56, 189, 248, 0.12)',
                          border: (p.documents?.status && hasUploadedDocuments(p.documents))
                            ? '1px solid rgba(245, 158, 11, 0.5)'
                            : '1px solid rgba(56, 189, 248, 0.3)',
                          color: (p.documents?.status && hasUploadedDocuments(p.documents))
                            ? '#fcd34d'
                            : '#38bdf8',
                          borderRadius: '8px',
                          fontSize: '0.82rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '8px',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        <FileText size={15} /> Check Uploaded Documents ({getUploadedDocumentCount(p.documents)})
                        {p.documents?.status && hasUploadedDocuments(p.documents) && (
                          <span style={{ background: '#f59e0b', color: '#000', fontSize: '0.68rem', padding: '1px 6px', borderRadius: '10px', fontWeight: 800 }}>
                            REVIEW NEEDED
                          </span>
                        )}
                      </button>
                    </div>

                    {/* ADMIN PRIVILEGE ONLY: Option to Manually Create Documents & Extracted Features Relation (ONLY FOR UNVERIFIED PROFILES) */}
                    {!p.verified && currentUser?.role === 'admin' && (
                      <div style={{ marginTop: '8px' }}>
                        <button
                          type="button"
                          onClick={() => setManualRelationsProvider(p)}
                          style={{
                            width: '100%',
                            padding: '7px 12px',
                            background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(99, 102, 241, 0.2) 100%)',
                            border: '1px solid rgba(56, 189, 248, 0.4)',
                            color: '#38bdf8',
                            borderRadius: '8px',
                            fontSize: '0.8rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px'
                          }}
                          title="Admin Privilege: Manually create/attach documents & extractedFeatures relation for unverified profile"
                        >
                          Manual Documents & Extracted Features Setup
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Admin Provider Documents Checking Modal */}
        {selectedProviderForDocs && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.8)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px'
          }}>
            <div className="glass-panel" style={{
              maxWidth: '850px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '28px',
              borderRadius: '20px',
              background: '#ffffff',
              border: '1px solid #276221',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              color: '#1e293b'
            }}>
              {/* Modal Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', borderBottom: '1px solid #cbd5e1', paddingBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <img
                    src={selectedProviderForDocs.providerImage || (selectedProviderForDocs as any).customerImage || 'https://api.dicebear.com/7.x/bottts/svg?seed=' + selectedProviderForDocs.fullName}
                    alt={selectedProviderForDocs.fullName}
                    style={{ width: '50px', height: '50px', borderRadius: '50%', objectFit: 'cover', border: '2px solid #276221' }}
                  />
                  <div>
                    <h3 style={{ fontSize: '1.25rem', margin: 0, color: '#1e293b' }}>
                      {selectedProviderForDocs.fullName}'s Documents
                    </h3>
                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                      Category: <strong style={{ color: '#276221' }}>{selectedProviderForDocs.category || 'Service Provider'}</strong> • {selectedProviderForDocs.city}, {selectedProviderForDocs.district}
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedProviderForDocs(null)}
                  style={{ background: '#ffffff', border: '1px solid #276221', color: '#276221', padding: '8px', borderRadius: '50%', cursor: 'pointer' }}
                >
                  <X size={20} color="#276221" />
                </button>
              </div>

              {/* Verification Status & Admin Action Bar */}
              <div style={{
                background: '#ffffff',
                border: '1px solid #276221',
                borderRadius: '12px',
                padding: '16px',
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px'
              }}>
                <div>
                  <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#276221' }}>
                    {selectedProviderForDocs.verified
                      ? '✓ Provider is Fully Verified'
                      : (selectedProviderForDocs.documents?.status && hasUploadedDocuments(selectedProviderForDocs.documents))
                        ? '⏳ Verification Review Requested (Pending Admin Decision)'
                        : '⚠️ Unverified Provider Account'}
                  </div>
                  <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
                    Total uploaded files: <strong style={{ color: '#1e293b' }}>{getUploadedDocumentCount(selectedProviderForDocs.documents)} document(s)</strong>
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  {!selectedProviderForDocs.verified && currentUser?.role === 'admin' && (
                    <button
                      type="button"
                      className="btn"
                      style={{
                        fontSize: '0.82rem',
                        padding: '8px 14px',
                        background: '#ffffff',
                        border: '1px solid #276221',
                        color: '#276221',
                        borderRadius: '10px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                      onClick={() => {
                        const p = selectedProviderForDocs;
                        setSelectedProviderForDocs(null);
                        setManualRelationsProvider(p);
                      }}
                    >
                      <Settings size={14} color="#276221" /> ⚙️ Manual Documents & Features Setup
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn"
                    style={{
                      fontSize: '0.85rem',
                      padding: '8px 18px',
                      background: selectedProviderForDocs.verified ? '#ffffff' : '#276221',
                      border: '1px solid #276221',
                      color: selectedProviderForDocs.verified ? '#276221' : '#ffffff',
                      borderRadius: '10px',
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                    onClick={async () => {
                      if (selectedProviderForDocs.id) {
                        const newVerified = !selectedProviderForDocs.verified;
                        const updated = await setProviderVerificationForConfiguredSource(
                          selectedProviderForDocs,
                          newVerified
                        );
                        setSelectedProviderForDocs(updated);
                        loadData();
                      }
                    }}
                  >
                    {selectedProviderForDocs.verified ? 'Revoke Verification' : '✔ Approve & Verify Provider'}
                  </button>
                </div>
              </div>

              {/* Render Document Viewer */}
              <ProviderDocumentsView
                documents={selectedProviderForDocs.documents}
                canManage={false}
                onOpenDocument={(category, item) =>
                  openProviderDocumentForConfiguredSource(
                    selectedProviderForDocs,
                    category,
                    item,
                    true
                  )
                }
              />
            </div>
          </div>
        )}

        {/* Quick Action Register Banner */}
        <div className="glass-panel" style={{ marginTop: '40px', padding: '28px', textAlign: 'center', background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(6, 182, 212, 0.15) 100%)' }}>
          <h3 style={{ fontSize: '1.3rem', marginBottom: '8px' }}>Register a New Account</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '18px' }}>
            Select registration type to add new entries to Firebase Realtime Database
          </p>
          <div style={{ display: 'inline-flex', gap: '14px' }}>
            <button className="btn btn-customer" onClick={() => onNavigateRegister('customer')}>
              <UserCheck size={18} /> Customer Sign Up
            </button>
            <button className="btn btn-provider" onClick={() => onNavigateRegister('provider')}>
              <Briefcase size={18} /> Provider Sign Up
            </button>
          </div>
        </div>
        {/* Admin Manual Relations Creation Modal for Unverified Profiles */}
        {manualRelationsProvider && (
          <AdminManualRelationsModal
            provider={manualRelationsProvider}
            adminUser={currentUser}
            onClose={() => setManualRelationsProvider(null)}
            onSuccess={() => {
              setManualRelationsProvider(null);
              loadData();
            }}
          />
        )}
      </div>
    </div>
  );
};
