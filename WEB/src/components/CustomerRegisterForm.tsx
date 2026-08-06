import React, { useState } from 'react';
import { User, Mail, Phone, MapPin, Globe, CheckCircle, Sparkles, Loader2, Check, Lock, Eye, EyeOff } from 'lucide-react';
import { SRI_LANKA_DISTRICTS, getCityCoordinates } from '../data/sriLankaData';
import { LocationMapPicker } from './LocationMapPicker';
import { ImageUploader } from './ImageUploader';
import { registerCustomer } from '../config/firebase';
import type { Customer } from '../config/firebase';

interface CustomerRegisterFormProps {
  onSuccess: (customer: Customer) => void;
  onSwitchToLogin: () => void;
}

export const CustomerRegisterForm: React.FC<CustomerRegisterFormProps> = ({
  onSuccess,
  onSwitchToLogin
}) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('+94');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const [district, setDistrict] = useState('Colombo');
  const [city, setCity] = useState('Moratuwa');
  const [location, setLocation] = useState({ latitude: 6.7730, longitude: 79.8816 });
  const [customerImage, setCustomerImage] = useState('https://api.dicebear.com/7.x/avataaars/svg?seed=SamanPerera');
  const [preferredLanguages, setPreferredLanguages] = useState<string[]>(['Sinhala']);
  
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Get cities list for selected district
  const selectedDistrictObj = SRI_LANKA_DISTRICTS.find(d => d.name === district) || SRI_LANKA_DISTRICTS[0];
  const citiesList = selectedDistrictObj.cities;

  // Toggle multiple language selection
  const handleLanguageToggle = (lang: string) => {
    if (preferredLanguages.includes(lang)) {
      if (preferredLanguages.length === 1) return;
      setPreferredLanguages(preferredLanguages.filter(l => l !== lang));
    } else {
      setPreferredLanguages([...preferredLanguages, lang]);
    }
  };

  // When district changes, update default city and map location
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

  // When city changes, update map location to focus that city
  const handleCityChange = (newCityName: string) => {
    setCity(newCityName);
    const coords = getCityCoordinates(district, newCityName);
    setLocation(coords);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    // Field validations
    if (!fullName.trim()) return setErrorMsg('Please enter your full name.');
    if (!email.trim() || !email.includes('@')) return setErrorMsg('Please enter a valid email address.');
    if (!phone.trim()) return setErrorMsg('Please enter your phone number.');
    if (password.length < 6) return setErrorMsg('Password must be at least 6 characters.');
    if (password !== confirmPassword) return setErrorMsg('Passwords do not match.');
    if (preferredLanguages.length === 0) return setErrorMsg('Please select at least one preferred language.');

    setLoading(true);

    try {
      const created = await registerCustomer(
        {
          fullName: fullName.trim(),
          email: email.trim().toLowerCase(),
          phone: phone.trim(),
          district,
          city,
          location,
          customerImage,
          preferredLanguage: preferredLanguages.join(', ')
        },
        password
      );

      setSuccessMsg(`Customer account created successfully in Firebase Auth & RTDB for ${created.fullName}!`);
      setTimeout(() => {
        onSuccess(created);
      }, 1200);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || 'Failed to register customer.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel glass-panel-hover" style={{ maxWidth: '680px', margin: '0 auto', padding: '36px' }}>
      
      {/* Header Banner */}
      <div style={{ textAlign: 'center', marginBottom: '28px' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 16px', borderRadius: '20px', background: 'rgba(39, 98, 33, 0.1)', border: '1px solid rgba(39, 98, 33, 0.25)', color: '#276221', fontSize: '0.85rem', fontWeight: 600, marginBottom: '12px' }}>
          <Sparkles size={14} /> Customer Sign Up
        </div>
        <h1 style={{ fontSize: '2rem', marginBottom: '8px' }}>Create <span className="gradient-text-customer">Customer</span> Account</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem' }}>
          Register with email & password to discover top rated service providers in Sri Lanka
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
            <User size={16} color="var(--accent-customer)" /> Full Name
          </label>
          <input
            type="text"
            className="form-control"
            placeholder="e.g. Saman Perera"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        </div>

        {/* Grid: Email & Phone */}
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">
              <Mail size={16} color="var(--accent-customer)" /> Email Address
            </label>
            <input
              type="email"
              className="form-control"
              placeholder="saman.perera@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              <Phone size={16} color="var(--accent-customer)" /> Phone Number
            </label>
            <input
              type="tel"
              className="form-control"
              placeholder="+94771234567"
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
              <Lock size={16} color="var(--accent-customer)" /> Account Password
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
              <Lock size={16} color="var(--accent-customer)" /> Confirm Password
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

        {/* Grid: District & City Dropdowns */}
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">
              <MapPin size={16} color="var(--accent-customer)" /> Sri Lankan District
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
              <MapPin size={16} color="var(--accent-customer)" /> City / Town
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

        {/* Customer Image Upload */}
        <ImageUploader
          label="Customer Profile Image"
          imageValue={customerImage}
          onChange={setCustomerImage}
          accentColor="var(--accent-customer)"
        />

        {/* Preferred Languages */}
        <div className="form-group" style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label className="form-label">
              <Globe size={16} color="var(--accent-customer)" /> Preferred Languages (Select Multiple)
            </label>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {preferredLanguages.length} selected
            </span>
          </div>
          <div className="language-options">
            {[
              { id: 'Sinhala', label: '🇱🇰 Sinhala (සිංහල)' },
              { id: 'English', label: '🇬🇧 English' },
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
          className="btn btn-customer"
          style={{ width: '100%', padding: '14px', marginTop: '16px', fontSize: '1.05rem' }}
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 size={18} className="spin" /> Registering in Firebase Auth & RTDB...
            </>
          ) : (
            'Complete Customer Registration'
          )}
        </button>

        <div style={{ textAlign: 'center', marginTop: '18px', fontSize: '0.88rem', color: 'var(--text-muted)' }}>
          Already have an account?{' '}
          <span 
            onClick={onSwitchToLogin} 
            style={{ color: 'var(--accent-customer)', cursor: 'pointer', fontWeight: 600, textDecoration: 'underline' }}
          >
            Log in here
          </span>
        </div>

      </form>
    </div>
  );
};
