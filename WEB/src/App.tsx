import { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { CustomerRegisterForm } from './components/CustomerRegisterForm';
import { ProviderRegisterForm } from './components/ProviderRegisterForm';
import { LoginForm } from './components/LoginForm';
import { Dashboard } from './components/Dashboard';
import { CustomerDashboard } from './components/CustomerDashboard';
import { ProviderDashboard } from './components/ProviderDashboard';
import { subscribeAuthState, logoutFirebaseUser, ACTIVE_SESSION_KEY } from './config/firebase';
import {
  backendUserToWebUser,
  logoutBackendSession,
  restoreBackendUser
} from './config/backendSession';
import { runtimeConfig } from './config/runtime';
import { syncCustomerProfileFromConfiguredSource } from './services/customer-service';
import { syncProviderProfileFromConfiguredSource } from './services/provider-service';
import { ThemeProvider } from './context/ThemeContext';

export function AppContent() {
  const [activeTab, setActiveTab] = useState<'customer' | 'provider' | 'login' | 'dashboard'>('login');
  const [currentUser, setCurrentUser] = useState<any | null>(null);

  // Restore and maintain active user session via Firebase Auth state & localStorage
  useEffect(() => {
    if (runtimeConfig.authSource === 'fastapi') {
      void restoreBackendUser().then((user) => {
        if (!user) return;
        const restored = backendUserToWebUser(user);
        setCurrentUser(restored);
        localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(restored));
        setActiveTab('dashboard');
      });
      return;
    }
    const unsubscribe = subscribeAuthState((user) => {
      if (user) {
        setCurrentUser(user);
        localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(user));
        setActiveTab((prevTab) => (prevTab === 'login' ? 'dashboard' : prevTab));
      }
    });

    return () => unsubscribe();
  }, []);

  const handleRegisterSuccess = (registeredUser: any) => {
    setCurrentUser(registeredUser);
    localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(registeredUser));
    setActiveTab('dashboard');
  };

  const handleLoginSuccess = async (user: any) => {
    const synchronizedUser = user.role === 'customer'
      ? await syncCustomerProfileFromConfiguredSource(user)
      : user.role === 'provider'
        ? await syncProviderProfileFromConfiguredSource(user)
        : user;
    setCurrentUser(synchronizedUser);
    localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(synchronizedUser));
    setActiveTab('dashboard');
  };

  const handleLogout = async () => {
    if (runtimeConfig.authSource !== 'fastapi') await logoutFirebaseUser();
    await logoutBackendSession();
    setCurrentUser(null);
    setActiveTab('login');
  };

  return (
    <div style={{ minHeight: '100vh', paddingBottom: '60px' }}>
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 20px' }}>
        {activeTab === 'customer' && (
          <CustomerRegisterForm
            onSuccess={handleRegisterSuccess}
            onSwitchToLogin={() => setActiveTab('login')}
          />
        )}

        {activeTab === 'provider' && (
          <ProviderRegisterForm
            onSuccess={handleRegisterSuccess}
            onSwitchToLogin={() => setActiveTab('login')}
          />
        )}

        {activeTab === 'login' && (
          <LoginForm
            onLoginSuccess={handleLoginSuccess}
            onSwitchToRegister={(role) => setActiveTab(role)}
          />
        )}

        {/* Dashboard View dynamically tailored to User Role */}
        {activeTab === 'dashboard' && currentUser && (
          <>
            {currentUser.role === 'customer' && (
              <CustomerDashboard
                currentUser={currentUser}
                onUpdateUser={(updatedUser) => {
                  setCurrentUser(updatedUser);
                  localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(updatedUser));
                }}
              />
            )}

            {currentUser.role === 'provider' && (
              <ProviderDashboard
                currentUser={currentUser}
                onUpdateUser={(updatedUser) => {
                  setCurrentUser(updatedUser);
                  localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(updatedUser));
                }}
              />
            )}

            {currentUser.role === 'admin' && (
              <Dashboard
                currentUser={currentUser}
                onUpdateUser={(updatedUser) => {
                  setCurrentUser(updatedUser);
                  localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(updatedUser));
                }}
                onNavigateRegister={(role) => setActiveTab(role)}
                onLogout={handleLogout}
              />
            )}
          </>
        )}

        {/* If no user is logged in and dashboard is clicked, render Login */}
        {activeTab === 'dashboard' && !currentUser && (
          <LoginForm
            onLoginSuccess={handleLoginSuccess}
            onSwitchToRegister={(role) => setActiveTab(role)}
          />
        )}
      </main>

      <footer style={{ marginTop: '60px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.82rem', padding: '20px' }}>
        weda.lk &copy; 2026 • Powered by React
      </footer>
    </div>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}

export default App;
