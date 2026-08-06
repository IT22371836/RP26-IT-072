import React, { useState } from 'react';
import { Briefcase, User, Mail, Phone, MapPin, Globe, CheckCircle, Loader2, Wrench, Shield, Award, Check, Plus, X, Lock, Eye, EyeOff } from 'lucide-react';
import { SRI_LANKA_DISTRICTS, getCityCoordinates } from '../data/sriLankaData';
import { LocationMapPicker } from './LocationMapPicker';
import { ImageUploader } from './ImageUploader';
import { registerProvider } from '../config/firebase';
import type { Provider } from '../config/firebase';

interface ProviderRegisterFormProps {
  onSuccess: (provider: Provider) => void;
  onSwitchToLogin: () => void;
}

import { SERVICE_CATEGORIES, CATEGORY_SKILL_SUGGESTIONS } from '../data/categories';

export const ProviderRegisterForm: React.FC<ProviderRegisterFormProps> = ({
  onSuccess,
  onSwitchToLogin
}) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('+94');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [nic, setNic] = useState('');
  const [category, setCategory] = useState(SERVICE_CATEGORIES[0]);
  const [district, setDistrict] = useState('Colombo');
  const [city, setCity] = useState('Dehiwala');
  const [location, setLocation] = useState({ latitude: 6.8511, longitude: 79.8656 });
  const [providerImage, setProviderImage] = useState('https://firebasestorage.googleapis.com/v0/b/service-e333a.appspot.com/o/providers%2Fprovider_default.png?alt=media');
  const [preferredLanguages, setPreferredLanguages] = useState<string[]>(['English', 'Sinhala']);
  const [experienceYears, setExperienceYears] = useState(5);
  
  const [skillsList, setSkillsList] = useState<string[]>([
    'House Wiring',
    'Circuit Breaker Installation',
    'Solar Panel Setup'
  ]);
  const [skillInputText, setSkillInputText] = useState('');

  const [description, setDescription] = useState('');

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const selectedDistrictObj = SRI_LANKA_DISTRICTS.find(d => d.name === district) || SRI_LANKA_DISTRICTS[0];
  const citiesList = selectedDistrictObj.cities;

  const handleAddSkill = (skillToAdd?: string) => {
    const text = (skillToAdd || skillInputText).trim();
    if (text && !skillsList.includes(text)) {
      setSkillsList([...skillsList, text]);
      if (!skillToAdd) setSkillInputText('');
    }
  };

  const handleRemoveSkill = (skillToRemove: string) => {
    setSkillsList(skillsList.filter(s => s !== skillToRemove));
  };

  const handleLanguageToggle = (lang: string) => {
    if (preferredLanguages.includes(lang)) {
      if (preferredLanguages.length === 1) return;
      setPreferredLanguages(preferredLanguages.filter(l => l !== lang));
    } else {
      setPreferredLanguages([...preferredLanguages, lang]);
    }
  };

  const handleDistrictChange = (newDistrictName: string) => {
    setDistrict(newDistrictName);
    const found = SRI_LANKA_DISTRICTS.find(d => d.name === newDistrictName);
    if (found) {
      const defaultCity = found.cities[0] || '';
      setCity(defaultCity);
      const coords = getCityCoordinates(newDistrictName, defaultCity);
      setLocation(coords);
    }
  };

  const handleCityChange = (newCityName: string) => {
    setCity(newCityName);
    const coords = getCityCoordinates(district, newCityName);
    setLocation(coords);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (!fullName.trim()) return setErrorMsg('Please enter your full name.');
    if (!email.trim() || !email.includes('@')) return setErrorMsg('Please enter a valid email address.');
    if (!phone.trim()) return setErrorMsg('Please enter your phone number.');
    if (password.length < 6) return setErrorMsg('Password must be at least 6 characters.');
    if (password !== confirmPassword) return setErrorMsg('Passwords do not match.');
    if (preferredLanguages.length === 0) return setErrorMsg('Please select at least one preferred language.');
    if (skillsList.length === 0) return setErrorMsg('Please add at least one skill tag.');

    setLoading(true);

    try {
      const created = await registerProvider(
        {
          fullName: fullName.trim(),
          email: email.trim().toLowerCase(),
          phone: phone.trim(),
          nic: nic.trim() || '199012345678',
          category,
          district,
          city,
          location,
          providerImage,
          preferredLanguage: preferredLanguages.join(', '),
          experienceYears: Number(experienceYears),
          skills: skillsList,
          description: description.trim() || `Professional ${category} specialist in ${city}, ${district}.`
        },
        password
      );

      setSuccessMsg(`Provider profile registered successfully in Firebase Auth & RTDB for ${created.fullName}!`);
      setTimeout(() => {
        onSuccess(created);
      }, 1200);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || 'Failed to register provider.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel glass-panel-hover" style={{ maxWidth: '680px', margin: '0 auto', padding: '36px' }}>
      
      {/* Header Banner */}
      <div style={{ textAlign: 'center', marginBottom: '28px' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 16px', borderRadius: '20px', background: 'rgba(39, 98, 33, 0.1)', border: '1px solid rgba(39, 98, 33, 0.25)', color: '#276221', fontSize: '0.85rem', fontWeight: 600, marginBottom: '12px' }}>
          <Briefcase size={14} /> Service Provider Sign Up
        </div>
        <h1 style={{ fontSize: '2rem', marginBottom: '8px' }}>Register as a <span className="gradient-text-provider">Service Provider</span></h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem' }}>
          Offer your skills to customers across Sri Lanka and receive ratings
        </p>
      </div>

      {errorMsg && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', color: '#b91c1c', padding: '12px 16px', borderRadius: '12px', fontSize: '0.9rem', marginBottom: '20px' }}>
          ⚠️ {errorMsg}
        </div>
      )}

      {successMsg && (
        <div style={{ background: 'rgba(39, 98, 33, 0.1)', border: '1px solid #276221', color: '#1e4b19', padding: '12px 16px', borderRadius: '12px', fontSize: '0.9rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle size={18} /> {successMsg}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        
        {/* Full Name */}
        <div className="form-group">
          <label className="form-label">
            <User size={16} color="var(--accent-provider)" /> Full Name
          </label>
          <input
            type="text"
            className="form-control"
            placeholder="e.g. Kamal Fernando"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        </div>

        {/* Grid: Email & Phone */}
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">
              <Mail size={16} color="var(--accent-provider)" /> Email Address
            </label>
            <input
              type="email"
              className="form-control"
              placeholder="kamal.fernando@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              <Phone size={16} color="var(--accent-provider)" /> Phone Number
            </label>
            <input
              type="tel"
              className="form-control"
              placeholder="+94719876543"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
            />
          </div>
        </div>

        {/* Grid: Password & Verify Password */}
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">
              <Lock size={16} color="var(--accent-provider)" /> Account Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? "text" : "password"}
                className="form-control"
                placeholder="Min 6 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <span
                onClick={() => setShowPassword(!showPassword)}
                style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">
              <Lock size={16} color="var(--accent-provider)" /> Confirm Password
            </label>
            <input
              type={showPassword ? "text" : "password"}
              className="form-control"
              placeholder="Re-enter password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
        </div>

        {/* Grid: NIC & Service Category */}
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">
              <Shield size={16} color="var(--accent-provider)" /> NIC Number
            </label>
            <input
              type="text"
              className="form-control"
              placeholder="199012345678"
              value={nic}
              onChange={(e) => setNic(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              <Wrench size={16} color="var(--accent-provider)" /> Service Category
            </label>
            <select
              className="form-control"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {SERVICE_CATEGORIES.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Grid: District & City Dropdowns */}
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">
              <MapPin size={16} color="var(--accent-provider)" /> Service District
            </label>
            <select
              className="form-control"
              value={district}
              onChange={(e) => handleDistrictChange(e.target.value)}
            >
              {SRI_LANKA_DISTRICTS.map((d) => (
                <option key={d.name} value={d.name}>
                  {d.name} District
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">
              <MapPin size={16} color="var(--accent-provider)" /> Service City / Town
            </label>
            <select
              className="form-control"
              value={city}
              onChange={(e) => handleCityChange(e.target.value)}
            >
              {citiesList.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Map Picker for Location */}
        <div className="form-group">
          <LocationMapPicker
            location={location}
            onChange={setLocation}
            centerLat={location.latitude}
            centerLng={location.longitude}
            selectedCityName={city}
          />
        </div>

        {/* Provider Image Upload */}
        <ImageUploader
          label="Provider Profile Image"
          imageValue={providerImage}
          onChange={setProviderImage}
          accentColor="var(--accent-provider)"
        />

        {/* Experience Field */}
        <div className="form-group" style={{ marginTop: '16px' }}>
          <label className="form-label">
            <Award size={16} color="var(--accent-provider)" /> Professional Experience (Years)
          </label>
          <input
            type="number"
            min="0"
            max="50"
            className="form-control"
            value={experienceYears}
            onChange={(e) => setExperienceYears(Number(e.target.value))}
          />
        </div>

        {/* --- FULL-WIDTH MODERN SKILLS TAG MANAGER UI --- */}
        <div className="form-group" style={{ background: '#f8faf8', padding: '20px', borderRadius: '16px', border: '1px solid #cbd5e1', margin: '20px 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <label className="form-label" style={{ margin: 0, fontSize: '0.95rem' }}>
              <Wrench size={18} color="var(--accent-provider)" /> Specialized Skills & Capabilities
            </label>
            <span style={{ fontSize: '0.78rem', background: 'rgba(39, 98, 33, 0.12)', color: '#276221', padding: '3px 10px', borderRadius: '12px', fontWeight: 600 }}>
              {skillsList.length} Skills Added
            </span>
          </div>

          {/* Render Active Skill Badges */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '14px', minHeight: '38px', alignItems: 'center' }}>
            {skillsList.length === 0 ? (
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                No skills added yet. Add skills below or click suggestions.
              </span>
            ) : (
              skillsList.map((skill) => (
                <div
                  key={skill}
                  style={{
                    background: 'linear-gradient(135deg, #276221 0%, #327a2a 100%)',
                    border: '1px solid #276221',
                    color: '#ffffff',
                    padding: '6px 14px',
                    borderRadius: '20px',
                    fontSize: '0.86rem',
                    fontWeight: 600,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                    boxShadow: '0 2px 8px rgba(39, 98, 33, 0.2)'
                  }}
                >
                  <span>{skill}</span>
                  <X
                    size={14}
                    style={{ cursor: 'pointer', opacity: 0.9 }}
                    onClick={() => handleRemoveSkill(skill)}
                  />
                </div>
              ))
            )}
          </div>

          {/* Add Skill Input & Button */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '12px' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Type a skill (e.g. House Wiring) and press Enter..."
              value={skillInputText}
              onChange={(e) => setSkillInputText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddSkill();
                }
              }}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn btn-provider"
              onClick={() => handleAddSkill()}
              style={{ padding: '10px 18px', whiteSpace: 'nowrap' }}
            >
              <Plus size={16} /> Add Skill
            </button>
          </div>

          {/* Quick Suggestion Chips based on selected Category */}
          <div>
            <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', display: 'block', marginBottom: '8px' }}>
              💡 Quick Add Suggestions for <strong>{category}</strong>:
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {(CATEGORY_SKILL_SUGGESTIONS[category] || CATEGORY_SKILL_SUGGESTIONS["Electricians"] || []).map((sug) => {
                const isAlreadyAdded = skillsList.includes(sug);
                return (
                  <button
                    key={sug}
                    type="button"
                    className="suggestion-chip-btn"
                    onClick={() => handleAddSkill(sug)}
                    disabled={isAlreadyAdded}
                    style={{
                      background: isAlreadyAdded ? '#f1f5f9' : '#eaf3e8',
                      border: '1px solid #cbd5e1',
                      color: isAlreadyAdded ? 'var(--text-dim)' : '#276221',
                      padding: '4px 10px',
                      borderRadius: '12px',
                      fontSize: '0.76rem',
                      cursor: isAlreadyAdded ? 'default' : 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      opacity: isAlreadyAdded ? 0.5 : 1,
                      transition: 'all 0.2s ease'
                    }}
                  >
                    {isAlreadyAdded ? <Check size={12} /> : <Plus size={12} />}
                    {sug}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Bio / Description */}
        <div className="form-group">
          <label className="form-label">
            Bio / Description
          </label>
          <textarea
            className="form-control"
            rows={3}
            placeholder="Brief description of your expertise, services, and working hours..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {/* Preferred Languages (Multiple Selectable Pills) */}
        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label className="form-label">
              <Globe size={16} color="var(--accent-provider)" /> Preferred Languages (Select Multiple)
            </label>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {preferredLanguages.length} selected
            </span>
          </div>
          <div className="language-options">
            {[
              { id: 'English', label: '🇬🇧 English' },
              { id: 'Sinhala', label: '🇱🇰 Sinhala (සිංහල)' },
              { id: 'Tamil', label: '🇱🇰 Tamil (தமிழ்)' }
            ].map((lang) => {
              const isSelected = preferredLanguages.includes(lang.id);
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

        {/* Submit Button */}
        <button
          type="submit"
          className="btn btn-provider"
          style={{ width: '100%', padding: '14px', marginTop: '16px', fontSize: '1.05rem' }}
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 size={18} className="spin" /> Registering in Firebase Auth & RTDB...
            </>
          ) : (
            'Complete Provider Registration'
          )}
        </button>

        <div style={{ textAlign: 'center', marginTop: '18px', fontSize: '0.88rem', color: 'var(--text-muted)' }}>
          Already registered as a provider?{' '}
          <span 
            onClick={onSwitchToLogin} 
            style={{ color: 'var(--accent-provider)', cursor: 'pointer', fontWeight: 600, textDecoration: 'underline' }}
          >
            Log in here
          </span>
        </div>

      </form>
    </div>
  );
};
