// CustomerDashboard Component
import React, { useEffect, useState } from 'react';
import { MapPin, Mail, Phone, Globe, Edit3, Save, Search, Filter, CheckCircle, Loader2, X, Briefcase, Award, Map, Eye, Wrench, Star, ShieldCheck } from 'lucide-react';
import { fetchPublicProviders, getProviderCredibility } from '../config/firebase';
import type { Customer, Provider } from '../config/firebase';
import { updateCustomerProfileForConfiguredSource } from '../services/customer-service';
import { SRI_LANKA_DISTRICTS, getCityCoordinates } from '../data/sriLankaData';
import { LocationMapPicker } from './LocationMapPicker';
import { ImageUploader } from './ImageUploader';
import { ProviderCardMap } from './ProviderCardMap';
import { MasterProvidersMap } from './MasterProvidersMap';
import { WorkingHoursView } from './WorkingHoursView';
import { WeatherWidget } from './WeatherWidget';
import { SERVICE_CATEGORIES } from '../data/categories';
import { PipelineWorkspace } from './PipelineWorkspace';

interface CustomerDashboardProps {
  currentUser: Customer;
  onUpdateUser: (updatedUser: Customer) => void;
}

export const CustomerDashboard: React.FC<CustomerDashboardProps> = ({
  currentUser,
  onUpdateUser
}) => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [showMasterMap, setShowMasterMap] = useState(false);

  // Selected Provider for Full Profile Details Modal
  const [selectedProviderModal, setSelectedProviderModal] = useState<Provider | null>(null);

  // Search & Filter state for browsing providers
  const [categoryFilter, setCategoryFilter] = useState<string>('All');
  const [districtFilter, setDistrictFilter] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Customer Edit Profile Modal state
  const [isEditing, setIsEditing] = useState(false);
  const [editFullName, setEditFullName] = useState(currentUser.fullName || '');
  const [editPhone, setEditPhone] = useState(currentUser.phone || '');
  const [editDistrict, setEditDistrict] = useState(currentUser.district || 'Colombo');
  const [editCity, setEditCity] = useState(currentUser.city || 'Moratuwa');
  const [editLocation, setEditLocation] = useState(currentUser.location || { latitude: 6.7730, longitude: 79.8816 });
  const [editCustomerImage, setEditCustomerImage] = useState(currentUser.customerImage || '');
  const [editPreferredLanguages, setEditPreferredLanguages] = useState<string[]>(
    currentUser.preferredLanguage ? currentUser.preferredLanguage.split(', ') : ['Sinhala']
  );
  const [updating, setUpdating] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  // Load providers for Customer view
  const loadProviders = async () => {
    setLoadingProviders(true);
    try {
      const pList = await fetchPublicProviders();
      setProviders(pList);
    } catch (err) {
      console.error("Failed to load providers:", err);
    } finally {
      setLoadingProviders(false);
    }
  };

  useEffect(() => {
    loadProviders();
  }, []);

  // Update Edit form state if currentUser prop changes
  useEffect(() => {
    if (currentUser) {
      setEditFullName(currentUser.fullName || '');
      setEditPhone(currentUser.phone || '');
      setEditDistrict(currentUser.district || 'Colombo');
      setEditCity(currentUser.city || 'Moratuwa');
      setEditLocation(currentUser.location || { latitude: 6.7730, longitude: 79.8816 });
      setEditCustomerImage(currentUser.customerImage || '');
      setEditPreferredLanguages(
        currentUser.preferredLanguage ? currentUser.preferredLanguage.split(', ') : ['Sinhala']
      );
    }
  }, [currentUser]);

  const selectedEditDistrictObj = SRI_LANKA_DISTRICTS.find(d => d.name === editDistrict) || SRI_LANKA_DISTRICTS[0];
  const editCitiesList = selectedEditDistrictObj.cities;

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
      const updated = await updateCustomerProfileForConfiguredSource(currentUser, {
        fullName: editFullName.trim(),
        phone: editPhone.trim(),
        district: editDistrict,
        city: editCity,
        location: editLocation,
        customerImage: editCustomerImage,
        preferredLanguage: editPreferredLanguages.join(', ')
      });

      onUpdateUser(updated);
      setSuccessMsg("Customer profile updated successfully!");
      setTimeout(() => {
        setIsEditing(false);
        setSuccessMsg('');
      }, 1400);
    } catch (err: any) {
      console.error(err);
      alert("Failed to update profile: " + err.message);
    } finally {
      setUpdating(false);
    }
  };

  // Filtered Providers list
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

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto' }}>

      <PipelineWorkspace currentUser={currentUser} />

      {/* Customer Session Header */}
      <div className="glass-panel" style={{ padding: '28px', marginBottom: '32px', borderLeft: '6px solid var(--accent-customer)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <img
              src={currentUser.customerImage || 'https://api.dicebear.com/7.x/avataaars/svg?seed=' + currentUser.fullName}
              alt={currentUser.fullName}
              style={{ width: '76px', height: '76px', borderRadius: '50%', objectFit: 'cover', border: '3px solid var(--accent-customer)', boxShadow: '0 0 15px rgba(139,92,246,0.3)', flexShrink: 0, aspectRatio: '1 / 1' }}
              onError={(e) => {
                (e.target as HTMLElement).setAttribute('src', 'https://api.dicebear.com/7.x/bottts/svg?seed=' + currentUser.fullName);
              }}
            />
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                <h1 style={{ fontSize: '1.6rem', margin: 0 }}>{currentUser.fullName}</h1>
                <span style={{
                  padding: '4px 12px',
                  borderRadius: '16px',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  background: 'rgba(139,92,246,0.2)',
                  color: 'var(--accent-customer)',
                  border: '1px solid rgba(139,92,246,0.4)'
                }}>
                  Customer Account
                </span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                <span><Mail size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.email}</span>
                <span><Phone size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.phone}</span>
                <span><MapPin size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.city}, {currentUser.district} District</span>
                <span><Globe size={14} style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {currentUser.preferredLanguage}</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              className="btn btn-customer"
              onClick={() => setIsEditing(true)}
              style={{ padding: '10px 18px', fontSize: '0.9rem' }}
            >
              <Edit3 size={16} /> Edit Profile Details
            </button>
          </div>
        </div>
      </div>

      {/* FULL WEATHER FORECAST BANNER */}
      <div style={{ marginBottom: '28px' }}>
        <WeatherWidget
          location={currentUser.location}
          city={currentUser.city}
          district={currentUser.district}
        />
      </div>

      {/* SERVICE PROVIDERS DIRECTORY FOR CUSTOMERS */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '16px' }}>
          <div>
            <h2 style={{ fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px', color: '#1e293b' }}>
              <Briefcase color="#276221" /> Available Service Providers ({filteredProviders.length})
            </h2>
            <p style={{ color: '#64748b', fontSize: '0.88rem', margin: 0 }}>
              Click any provider box to open full profile details, working hours, and map location pin
            </p>
          </div>

          <button
            type="button"
            className="btn btn-outline"
            onClick={() => setShowMasterMap(!showMasterMap)}
            style={{ padding: '8px 16px', fontSize: '0.86rem', borderColor: 'var(--accent-provider)', color: '#34d399' }}
          >
            <Map size={16} /> {showMasterMap ? 'Hide Master Map' : 'View All Sri Lanka Pins Map'}
          </button>
        </div>

        {/* Optional Master Sri Lanka Pinpoint Map for all providers */}
        {showMasterMap && (
          <MasterProvidersMap providers={filteredProviders} />
        )}

        {/* Filter Bar */}
        <div className="glass-panel" style={{ padding: '18px', marginBottom: '24px', border: '1px solid #276221', background: 'transparent' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px', alignItems: 'center' }}>

            {/* Search Keyword */}
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
                <option value="All">All Service Categories</option>
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

        {/* Provider Summary Grid Cards */}
        {loadingProviders ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            <Loader2 className="spin" size={24} style={{ display: 'block', margin: '0 auto 10px auto' }} />
            Loading registered service providers...
          </div>
        ) : filteredProviders.length === 0 ? (
          <div className="glass-panel" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            No service providers match your search filters. Try clearing search filters.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '22px' }}>
            {filteredProviders.map((p) => (
              <div
                key={p.id || p.email}
                className="glass-panel glass-panel-hover"
                style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height: '100%', cursor: 'pointer' }}
                onClick={() => setSelectedProviderModal(p)}
              >
                {/* Upper Summary Section */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
                    <img
                      src={p.providerImage || (p as any).customerImage || 'https://firebasestorage.googleapis.com/v0/b/service-e333a.appspot.com/o/providers%2Fprovider_default.png?alt=media'}
                      alt={p.fullName}
                      style={{ width: '64px', height: '64px', borderRadius: '50%', objectFit: 'cover', border: '3px solid var(--accent-provider)', flexShrink: 0, aspectRatio: '1 / 1' }}
                      onError={(e) => {
                        (e.target as HTMLElement).setAttribute('src', 'https://api.dicebear.com/7.x/bottts/svg?seed=' + p.fullName);
                      }}
                    />
                    <div>
                      <h3 style={{ fontSize: '1.2rem', marginBottom: '4px' }}>{p.fullName}</h3>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.78rem', color: '#276221', border: '1px solid #276221', padding: '2px 8px', borderRadius: '6px', fontWeight: 600 }}>
                          {p.category || 'Service Provider'}
                        </span>
                        {p.verified ? (
                          <span style={{ fontSize: '0.74rem', color: '#276221', background: '#ffffff', border: '1px solid #276221', padding: '2px 8px', borderRadius: '6px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                            <CheckCircle size={12} color="#276221" /> Verified
                          </span>
                        ) : (
                          <span style={{ fontSize: '0.74rem', color: '#276221', background: '#ffffff', border: '1px solid #276221', padding: '2px 8px', borderRadius: '6px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                            ⚠️ Verification Pending
                          </span>
                        )}
                        {getProviderCredibility(p) && (
                          <span style={{ fontSize: '0.74rem', color: '#f59e0b', background: '#ffffff', border: '1px solid #276221', padding: '2px 8px', borderRadius: '6px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                            <Star size={11} fill="#fcd34d" color="#fcd34d" /> {getProviderCredibility(p)?.credibilityScore}% ({getProviderCredibility(p)?.credibilityLevel || 'Professional'})
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div style={{ fontSize: '0.86rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ color: 'var(--text-main)', wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
                      <Mail size={14} color="var(--accent-provider)" style={{ verticalAlign: 'middle', marginRight: '6px', flexShrink: 0 }} />
                      <span style={{ textDecoration: 'underline', wordBreak: 'break-word', overflowWrap: 'anywhere' }}>{p.email}</span>
                    </div>
                    <div style={{ color: 'var(--text-main)' }}>
                      <Phone size={14} color="var(--accent-provider)" style={{ verticalAlign: 'middle', marginRight: '6px' }} />
                      <span style={{ fontWeight: 600 }}>{p.phone}</span>
                    </div>
                    <div>
                      <MapPin size={14} color="var(--accent-provider)" style={{ verticalAlign: 'middle', marginRight: '6px' }} />
                      {p.city}, {p.district} District
                    </div>
                    {p.experienceYears !== undefined && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f59e0b', fontWeight: 600 }}>
                        <Award size={14} /> Experience: {p.experienceYears} Years
                      </div>
                    )}

                    {/* Render Provider Skills */}
                    {p.skills && p.skills.length > 0 && (
                      <div style={{ marginTop: '4px' }}>
                        <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>Skills & Expertise:</span>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {p.skills.map(skill => (
                            <span key={skill} style={{ border: '1px solid #276221', color: '#276221', background: 'rgba(39, 98, 33, 0.12)', fontSize: '0.76rem', padding: '3px 10px', borderRadius: '14px', fontWeight: 600 }}>
                              {skill}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* View Full Profile Action Button */}
                <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                  <button
                    type="button"
                    className="btn btn-provider"
                    style={{ width: '100%', padding: '10px', fontSize: '0.88rem', justifyContent: 'center' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedProviderModal(p);
                    }}
                  >
                    <Eye size={16} /> View Full Profile Details
                  </button>
                </div>

              </div>
            ))}
          </div>
        )}
      </div>

      {/* CUSTOMER EDIT PROFILE MODAL */}
      {isEditing && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '640px', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
              <h2 style={{ fontSize: '1.4rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Edit3 color="var(--accent-customer)" size={22} /> Edit Customer Profile
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
                label="Profile Image"
                imageValue={editCustomerImage}
                onChange={setEditCustomerImage}
                accentColor="var(--accent-customer)"
              />

              {/* Preferred Languages */}
              <div className="form-group" style={{ marginTop: '16px' }}>
                <label className="form-label">Preferred Languages</label>
                <div className="language-options">
                  {[
                    { id: 'Sinhala', label: '🇱🇰 Sinhala (සිංහල)' },
                    { id: 'English', label: '🇬🇧 English' },
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
                        {isSelected && <CheckCircle size={14} />}
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
                  className="btn btn-customer"
                  style={{ flex: 1, padding: '12px' }}
                  disabled={updating}
                >
                  {updating ? <Loader2 size={16} className="spin" /> : <Save size={16} />} Save Changes
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

      {/* FULL PROVIDER PROFILE DETAILS MODAL */}
      {selectedProviderModal && (
        <div className="modal-overlay" onClick={() => setSelectedProviderModal(null)}>
          <div className="modal-content" style={{ maxWidth: '780px', maxHeight: '90vh', overflowY: 'auto' }} onClick={(e) => e.stopPropagation()}>

            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <img
                  src={selectedProviderModal.providerImage || (selectedProviderModal as any).customerImage || 'https://firebasestorage.googleapis.com/v0/b/service-e333a.appspot.com/o/providers%2Fprovider_default.png?alt=media'}
                  alt={selectedProviderModal.fullName}
                  style={{ width: '56px', height: '56px', borderRadius: '50%', objectFit: 'cover', border: '2px solid var(--accent-provider)', flexShrink: 0, aspectRatio: '1 / 1' }}
                  onError={(e) => {
                    (e.target as HTMLElement).setAttribute('src', 'https://api.dicebear.com/7.x/bottts/svg?seed=' + selectedProviderModal.fullName);
                  }}
                />
                <div>
                  <h2 style={{ fontSize: '1.4rem', margin: 0 }}>{selectedProviderModal.fullName}</h2>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '3px' }}>
                    <span style={{ fontSize: '0.78rem', color: '#276221', border: '1px solid #276221', padding: '2px 8px', borderRadius: '6px', fontWeight: 600 }}>
                      {selectedProviderModal.category || 'Service Provider'}
                    </span>
                    {selectedProviderModal.verified ? (
                      <span style={{ fontSize: '0.74rem', color: '#276221', background: '#ffffff', border: '1px solid #276221', padding: '2px 8px', borderRadius: '6px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                        <CheckCircle size={12} color="#276221" /> Verified Provider
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.74rem', color: '#276221', background: '#ffffff', border: '1px solid #276221', padding: '2px 8px', borderRadius: '6px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                        ⚠️ Verification Pending
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <button
                onClick={() => setSelectedProviderModal(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={22} />
              </button>
            </div>

            {/* CREDIBILITY EVALUATION BANNER */}
            {getProviderCredibility(selectedProviderModal) && (
              <div style={{ background: '#ffffff', border: '1px solid #276221', borderRadius: '12px', padding: '16px', marginBottom: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                  <h4 style={{ fontSize: '0.94rem', margin: 0, color: '#34d399', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <ShieldCheck size={18} color="#10b981" /> Provider Credibility & Verification Score
                  </h4>
                  <span style={{ fontSize: '0.74rem', color: '#64748b' }}>
                    🕒 Evaluated: {getProviderCredibility(selectedProviderModal)?.lastEvaluatedAt ? new Date(getProviderCredibility(selectedProviderModal)?.lastEvaluatedAt ?? Date.now()).toLocaleDateString() : 'Recently'}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                  <div style={{ background: '#ffffff', padding: '10px 14px', borderRadius: '8px', border: '1px solid #276221' }}>
                    <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Credibility Level</span>
                    <strong style={{ fontSize: '1.05rem', color: '#fcd34d', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Star size={14} fill="#fcd34d" color="#fcd34d" /> {getProviderCredibility(selectedProviderModal)?.credibilityLevel || 'Professional'}
                    </strong>
                  </div>
                  <div style={{ background: '#ffffff', padding: '10px 14px', borderRadius: '8px', border: '1px solid #276221' }}>
                    <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Credibility Score</span>
                    <strong style={{ fontSize: '1.1rem', color: '#34d399' }}>
                      {getProviderCredibility(selectedProviderModal)?.credibilityScore}%
                    </strong>
                  </div>
                </div>
              </div>
            )}

            {/* Provider Contact & Key Info */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              <div style={{ background: '#ffffff', padding: '14px', borderRadius: '10px', border: '1px solid #276221', wordBreak: 'break-word', overflowWrap: 'anywhere' }}>
                <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Email Address</span>
                <a href={`mailto:${selectedProviderModal.email}`} style={{ color: '#38bdf8', fontWeight: 600, fontSize: '0.92rem', wordBreak: 'break-word', overflowWrap: 'anywhere', display: 'inline-block', maxWidth: '100%' }}>
                  <Mail size={14} color="#38bdf8" style={{ verticalAlign: 'middle', marginRight: '4px', flexShrink: 0 }} /> {selectedProviderModal.email}
                </a>
              </div>

              <div style={{ background: '#ffffff', padding: '14px', borderRadius: '10px', border: '1px solid #276221' }}>
                <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Phone Number</span>
                <a href={`tel:${selectedProviderModal.phone}`} style={{ color: '#34d399', fontWeight: 600, fontSize: '0.92rem' }}>
                  <Phone size={14} color="#34d399" style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {selectedProviderModal.phone}
                </a>
              </div>

              <div style={{ background: '#ffffff', padding: '14px', borderRadius: '10px', border: '1px solid #276221' }}>
                <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Location Area</span>
                <strong style={{ fontSize: '0.92rem', color: '#1e293b' }}>
                  <MapPin size={14} color="#38bdf8" style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {selectedProviderModal.city}, {selectedProviderModal.district} District
                </strong>
              </div>

              {selectedProviderModal.experienceYears !== undefined && (
                <div style={{ background: '#ffffff', padding: '14px', borderRadius: '10px', border: '1px solid #276221' }}>
                  <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Experience</span>
                  <strong style={{ color: '#f59e0b', fontSize: '0.92rem' }}>
                    <Award size={14} color="#f59e0b" style={{ verticalAlign: 'middle', marginRight: '4px' }} /> {selectedProviderModal.experienceYears} Years
                  </strong>
                </div>
              )}

              {selectedProviderModal.preferredLanguage && (
                <div style={{ background: '#ffffff', padding: '14px', borderRadius: '10px', border: '1px solid #276221' }}>
                  <span style={{ fontSize: '0.78rem', color: '#276221', display: 'block', marginBottom: '4px', fontWeight: 600 }}>Preferred Languages</span>
                  <strong style={{ fontSize: '0.92rem', color: '#1e293b' }}>{selectedProviderModal.preferredLanguage}</strong>
                </div>
              )}
            </div>

            {/* Skills */}
            {selectedProviderModal.skills && selectedProviderModal.skills.length > 0 && (
              <div style={{ marginBottom: '20px' }}>
                <h4 style={{ fontSize: '0.94rem', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px', color: '#1e293b' }}>
                  <Wrench size={16} color="#10b981" /> Specialized Skills
                </h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {selectedProviderModal.skills.map(s => (
                    <span key={s} style={{ border: '1px solid #276221', color: '#276221', background: '#ffffff', padding: '4px 12px', borderRadius: '16px', fontSize: '0.82rem', fontWeight: 600 }}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Description */}
            {selectedProviderModal.description && (
              <div style={{ marginBottom: '20px', background: '#ffffff', padding: '14px 18px', borderRadius: '12px', border: '1px solid #276221' }}>
                <h4 style={{ fontSize: '0.94rem', marginBottom: '4px', color: '#1e293b' }}>Bio / Service Description</h4>
                <p style={{ color: '#64748b', fontSize: '0.88rem', lineHeight: 1.5, margin: 0 }}>
                  {selectedProviderModal.description}
                </p>
              </div>
            )}

            {/* Working Hours Weekly Schedule */}
            <div style={{ marginBottom: '20px' }}>
              <WorkingHoursView workingHours={selectedProviderModal.workingHours} />
            </div>

            {/* Interactive Location Pin Map */}
            {selectedProviderModal.location && selectedProviderModal.location.latitude && selectedProviderModal.location.longitude && (
              <div style={{ marginBottom: '10px' }}>
                <ProviderCardMap
                  latitude={selectedProviderModal.location.latitude}
                  longitude={selectedProviderModal.location.longitude}
                  providerName={selectedProviderModal.fullName}
                  category={selectedProviderModal.category}
                  cityName={selectedProviderModal.city}
                  districtName={selectedProviderModal.district}
                />
              </div>
            )}

            {/* Close Modal Button */}
            <div style={{ marginTop: '20px', textAlign: 'right' }}>
              <button
                type="button"
                className="btn btn-outline"
                onClick={() => setSelectedProviderModal(null)}
                style={{ padding: '8px 20px' }}
              >
                Close Profile
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
};
