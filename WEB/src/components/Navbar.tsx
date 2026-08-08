import React from 'react';
import { UserCheck, Briefcase, LogIn, LogOut, Shield, Sun, Moon } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

interface NavbarProps {
  activeTab: 'customer' | 'provider' | 'login' | 'dashboard';
  setActiveTab: (tab: 'customer' | 'provider' | 'login' | 'dashboard') => void;
  currentUser: any | null;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  currentUser,
  onLogout
}) => {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="glass-panel" style={{ borderRadius: 0, borderTop: 0, borderLeft: 0, borderRight: 0, marginBottom: '30px', position: 'sticky', top: 0, zIndex: 100 }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '16px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        
        {/* Brand / Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', cursor: 'pointer' }} onClick={() => setActiveTab(currentUser?.role === 'admin' ? 'dashboard' : 'customer')}>
          <img 
            src="/logo.png" 
            alt="weda.lk Logo" 
            style={{ 
              height: '46px', 
              width: 'auto', 
              objectFit: 'contain',
              filter: 'drop-shadow(0 0 10px rgba(39, 98, 33, 0.3))'
            }} 
          />
          <div>
            <h2 style={{ fontSize: '1.25rem', lineHeight: 1.1 }}><span className="gradient-text">weda.lk</span></h2>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sri Lanka Rating & Service Network</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Registration buttons are ONLY displayed when NO user is logged in */}
          {!currentUser && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'var(--bg-secondary)', padding: '6px', borderRadius: '14px', border: '1px solid var(--input-border)' }}>
              <button
                className={`btn ${activeTab === 'customer' ? 'btn-customer' : 'btn-outline'}`}
                style={{ padding: '8px 16px', fontSize: '0.88rem' }}
                onClick={() => setActiveTab('customer')}
              >
                <UserCheck size={16} />
                Customer Register
              </button>

              <button
                className={`btn ${activeTab === 'provider' ? 'btn-provider' : 'btn-outline'}`}
                style={{ padding: '8px 16px', fontSize: '0.88rem' }}
                onClick={() => setActiveTab('provider')}
              >
                <Briefcase size={16} />
                Provider Register
              </button>
            </div>
          )}

          {/* Database View Access Granted ONLY to Admin User */}
          {currentUser?.role === 'admin' && (
            <button
              className={`btn ${activeTab === 'dashboard' ? 'btn-primary' : 'btn-outline'}`}
              style={{ 
                padding: '8px 16px', 
                fontSize: '0.88rem',
                borderColor: '#fca5a5',
                background: activeTab === 'dashboard' ? '#dc2626' : 'rgba(239, 68, 68, 0.1)',
                color: activeTab === 'dashboard' ? '#ffffff' : '#dc2626'
              }}
              onClick={() => setActiveTab('dashboard')}
            >
              <Shield size={16} />
              Admin Database View
            </button>
          )}
        </nav>

        {/* User Session Info / Theme Switcher / Login & Logout Action Area */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Theme Switcher Toggle */}
          <button
            onClick={toggleTheme}
            className="theme-toggle-btn"
            title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} Mode`}
            aria-label="Toggle Theme"
            style={{
              padding: '8px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '0.82rem',
              fontWeight: 600,
              borderRadius: '20px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--input-border)',
              color: 'var(--text-main)',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            {theme === 'light' ? (
              <>
                <Moon size={16} style={{ color: '#6366f1' }} />
                <span>Dark Mode</span>
              </>
            ) : (
              <>
                <Sun size={16} style={{ color: '#f59e0b' }} />
                <span>Light Mode</span>
              </>
            )}
          </button>

          {currentUser ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: 'var(--bg-secondary)', padding: '6px 14px', borderRadius: '24px', border: '1px solid var(--input-border)' }}>
              <img 
                src={(currentUser.role === 'provider' ? currentUser.providerImage || currentUser.customerImage : currentUser.customerImage || currentUser.providerImage) || 'https://via.placeholder.com/40'} 
                alt={currentUser.fullName}
                style={{ width: '32px', height: '32px', borderRadius: '50%', objectFit: 'cover', border: `2px solid ${currentUser.role === 'admin' ? '#ef4444' : currentUser.role === 'customer' ? 'var(--accent-customer)' : 'var(--accent-provider)'}`, flexShrink: 0, aspectRatio: '1 / 1' }}
                onError={(e) => {
                  (e.target as HTMLElement).setAttribute('src', 'https://api.dicebear.com/7.x/bottts/svg?seed=' + currentUser.fullName);
                }}
              />
              <div style={{ fontSize: '0.82rem' }}>
                <span style={{ fontWeight: 600, display: 'block', maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {currentUser.fullName}
                </span>
                <span style={{ color: currentUser.role === 'admin' ? '#ef4444' : currentUser.role === 'customer' ? 'var(--accent-customer)' : 'var(--accent-provider)', fontSize: '0.72rem', textTransform: 'capitalize', fontWeight: 600 }}>
                  {currentUser.role === 'admin' ? '🛡️ Administrator' : currentUser.role}
                </span>
              </div>
              <button 
                onClick={onLogout} 
                className="btn"
                style={{ 
                  padding: '5px 12px', 
                  fontSize: '0.78rem',
                  background: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: '#dc2626',
                  borderRadius: '14px'
                }}
                title="Logout Session"
              >
                <LogOut size={13} /> Logout
              </button>
            </div>
          ) : (
            <button
              className={`btn ${activeTab === 'login' ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '8px 18px', fontSize: '0.88rem' }}
              onClick={() => setActiveTab('login')}
            >
              <LogIn size={16} />
              Login
            </button>
          )}
        </div>

      </div>
    </header>
  );
};
