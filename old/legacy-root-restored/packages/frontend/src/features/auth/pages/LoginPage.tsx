import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../../auth/AuthContext";
import type { UserRole } from "../../../auth/types";

const ROLE_CONFIG = {
  customer: {
    label: "Customer",
    title: "Welcome back",
    subtitle: "Sign in to your customer account",
    icon: "🏠",
    accent: "customer",
    dashboard: "/dashboard/customer",
  },
  provider: {
    label: "Provider",
    title: "Welcome back",
    subtitle: "Sign in to your provider account",
    icon: "🔧",
    accent: "provider",
    dashboard: "/dashboard/provider",
  },
} as const;

export function LoginPage() {
  const params = useParams<{ role: string }>();
  const role: UserRole = params.role === "provider" ? "provider" : "customer";
  const config = ROLE_CONFIG[role];

  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      await login(role, { email, password });
      navigate(config.dashboard, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid credentials. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ position: "relative", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}>
      {/* Animated background */}
      <div className={`auth-bg ${role}`} />
      <div className={`auth-orb auth-orb-1 ${role}`} />
      <div className={`auth-orb auth-orb-2 ${role}`} />

      {/* Card */}
      <div
        className="glass-card"
        style={{
          position: "relative",
          zIndex: 1,
          width: "100%",
          maxWidth: "440px",
          padding: "40px 36px",
          animation: "cardIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both",
        }}
      >
        {/* Logo / Icon */}
        <div style={{ textAlign: "center", marginBottom: "28px" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 64,
              height: 64,
              borderRadius: "18px",
              fontSize: "28px",
              marginBottom: "16px",
              background: role === "customer"
                ? "linear-gradient(135deg, rgba(5,150,105,0.25), rgba(16,185,129,0.1))"
                : "linear-gradient(135deg, rgba(79,70,229,0.25), rgba(99,102,241,0.1))",
              border: `1px solid ${role === "customer" ? "rgba(16,185,129,0.3)" : "rgba(99,102,241,0.3)"}`,
              boxShadow: role === "customer" ? "var(--shadow-glow-customer)" : "var(--shadow-glow-provider)",
            }}
          >
            {config.icon}
          </div>
          <h1 style={{ fontSize: "22px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "4px" }}>
            {config.title}
          </h1>
          <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>{config.subtitle}</p>
        </div>

        {/* Role tabs */}
        <div className="role-tabs" style={{ marginBottom: "24px" }}>
          <Link to="/login/customer" style={{ display: "contents" }}>
            <button type="button" className={`role-tab ${role === "customer" ? "active customer" : ""}`}>
              🏠 Customer
            </button>
          </Link>
          <Link to="/login/provider" style={{ display: "contents" }}>
            <button type="button" className={`role-tab ${role === "provider" ? "active provider" : ""}`}>
              🔧 Provider
            </button>
          </Link>
        </div>

        {/* Form */}
        <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div className="field-group">
            <label className="field-label" htmlFor="login-email">Email address</label>
            <input
              id="login-email"
              className={`auth-input ${role}`}
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          <div className="field-group">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <label className="field-label" htmlFor="login-password">Password</label>
            </div>
            <div style={{ position: "relative" }}>
              <input
                id="login-password"
                className={`auth-input ${role}`}
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                style={{ paddingRight: "44px" }}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                style={{
                  position: "absolute",
                  right: "12px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "none",
                  border: "none",
                  color: "var(--text-muted)",
                  fontSize: "16px",
                  cursor: "pointer",
                  padding: "4px",
                }}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "🙈" : "👁️"}
              </button>
            </div>
          </div>

          {error && (
            <div className="auth-alert error" role="alert">
              ⚠️ {error}
            </div>
          )}

          <button
            type="submit"
            className={`auth-btn ${role}`}
            disabled={submitting}
            style={{ marginTop: "4px" }}
          >
            {submitting ? (
              <><span className="spinner" />Signing in…</>
            ) : (
              "Sign in"
            )}
          </button>
        </form>

        {/* Footer */}
        <div style={{ marginTop: "24px", textAlign: "center" }}>
          <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
            Don't have an account?{" "}
            <Link
              to={`/signup/${role}`}
              style={{
                color: role === "customer" ? "var(--customer-400)" : "var(--provider-400)",
                fontWeight: 600,
              }}
            >
              Sign up
            </Link>
          </p>
        </div>
      </div>

      <style>{`
        @keyframes cardIn {
          from { opacity: 0; transform: translateY(24px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </div>
  );
}
