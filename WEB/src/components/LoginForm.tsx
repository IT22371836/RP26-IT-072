import React, { useState } from 'react';
import { Mail, Loader2, Lock, Eye, EyeOff } from 'lucide-react';
import { loginUser } from '../config/firebase';

interface LoginFormProps {
  onLoginSuccess: (user: any) => void | Promise<void>;
  onSwitchToRegister: (role: 'customer' | 'provider') => void;
}

export const LoginForm: React.FC<LoginFormProps> = ({
  onLoginSuccess,
  onSwitchToRegister
}) => {
  const [inputVal, setInputVal] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (!inputVal.trim()) {
      setErrorMsg('Please enter your email address or phone number.');
      return;
    }

    if (!password.trim()) {
      setErrorMsg('Please enter your account password.');
      return;
    }

    setLoading(true);
    try {
      const user = await loginUser(inputVal, password);
      if (user) {
        await onLoginSuccess(user);
      } else {
        setErrorMsg(`No registered account found for "${inputVal}". Please verify your credentials or register a new account.`);
      }
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || 'Login authentication failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel glass-panel-hover" style={{ maxWidth: '500px', margin: '0 auto', padding: '36px' }}>
      
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '28px' }}>
        <img 
          src="/logo.png" 
          alt="weda.lk Logo" 
          style={{ 
            height: '90px', 
            width: 'auto', 
            objectFit: 'contain',
            marginBottom: '10px',
            filter: 'drop-shadow(0 0 12px rgba(39, 98, 33, 0.3))'
          }} 
        />
        <h1 style={{ fontSize: '1.8rem', marginBottom: '6px' }}>Sign In to <span className="gradient-text">weda.lk</span></h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Enter email & password to authenticate
        </p>
      </div>

      {errorMsg && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', color: '#b91c1c', padding: '12px 16px', borderRadius: '12px', fontSize: '0.88rem', marginBottom: '20px' }}>
          ⚠️ {errorMsg}
        </div>
      )}

      <form onSubmit={handleLogin}>
        
        {/* Email or Phone */}
        <div className="form-group">
          <label className="form-label">
            <Mail size={16} color="var(--primary)" /> Email Address or Phone Number
          </label>
          <input
            type="text"
            className="form-control"
            placeholder="e.g. saman.perera@example.com"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            required
          />
        </div>

        {/* Password Field */}
        <div className="form-group">
          <label className="form-label">
            <Lock size={16} color="var(--primary)" /> Password
          </label>
          <div style={{ position: 'relative' }}>
            <input
              type={showPassword ? "text" : "password"}
              className="form-control"
              placeholder="Enter your account password"
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

        {/* Submit Button */}
        <button
          type="submit"
          className="btn btn-primary"
          style={{ width: '100%', padding: '14px', marginTop: '8px', fontSize: '1rem' }}
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 size={18} className="spin" /> Verifying Credentials...
            </>
          ) : (
            'Sign In & Load Profile'
          )}
        </button>

      </form>

      {/* Footer links to Register */}
      <div style={{ textAlign: 'center', marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #cbd5e1', fontSize: '0.88rem', color: 'var(--text-muted)' }}>
        Don't have an account yet?
        <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '10px' }}>
          <span 
            onClick={() => onSwitchToRegister('customer')} 
            style={{ color: 'var(--accent-customer)', cursor: 'pointer', fontWeight: 600, textDecoration: 'underline' }}
          >
            Register Customer
          </span>
          <span>•</span>
          <span 
            onClick={() => onSwitchToRegister('provider')} 
            style={{ color: 'var(--accent-provider)', cursor: 'pointer', fontWeight: 600, textDecoration: 'underline' }}
          >
            Register Provider
          </span>
        </div>
      </div>

    </div>
  );
};
