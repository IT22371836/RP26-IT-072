import { useState, useEffect, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../../../auth/AuthContext";
import type { UserRole } from "../../../auth/types";

const SERVICE_TYPES = [
  "Masons",
  "Carpenters",
  "Tile",
  "Plumbers",
  "Electricians",
  "Technicians",
  "Painters",
  "Landscaping",
  "Welding",
  "Air Conditioning",
  "Cleaners",
  "Vehicle Repairs",
  "Equipment Repairs",
  "CCTV",
  "Ceiling",
  "Cushion Works",
  "Movers",
  "Well",
  "Aluminium",
  "Solar Panel Fixing",
];

function getPasswordStrength(pw: string): { level: number; label: string; cls: string } {
  if (pw.length === 0) return { level: 0, label: "", cls: "" };
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  if (score <= 1) return { level: 1, label: "Weak", cls: "weak" };
  if (score === 2) return { level: 2, label: "Fair", cls: "fair" };
  if (score === 3) return { level: 3, label: "Good", cls: "good" };
  return { level: 4, label: "Strong", cls: "strong" };
}

export function SignUpPage() {
  const params = useParams<{ role: string }>();
  const role: UserRole = params.role === "provider" ? "provider" : "customer";

  const { register } = useAuth();
  const navigate = useNavigate();

  // Shared fields
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [agreedToTerms, setAgreedToTerms] = useState(false);

  // Provider-only fields
  const [businessName, setBusinessName] = useState("");
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [address, setAddress] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState("");

  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const strength = getPasswordStrength(password);

  // Clear form when role changes
  useEffect(() => {
    setFullName("");
    setEmail("");
    setPhone("");
    setPassword("");
    setConfirmPassword("");
    setShowPassword(false);
    setAgreedToTerms(false);
    setBusinessName("");
    setSelectedServices([]);
    setAddress("");
    setDescription("");
    setSkills("");
    setError("");
  }, [role]);

  function toggleService(svc: string) {
    setSelectedServices((prev) =>
      prev.includes(svc) ? prev.filter((s) => s !== svc) : [...prev, svc]
    );
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (!agreedToTerms) {
      setError("Please accept the Terms of Service to continue.");
      return;
    }
    if (role === "provider" && selectedServices.length === 0) {
      setError("Please select at least one service type.");
      return;
    }
    if (role === "provider" && !description.trim()) {
      setError("Please provide a professional summary of your work experience and background.");
      return;
    }
    if (role === "provider" && !skills.trim()) {
      setError("Please list the skills you specialize in.");
      return;
    }

    setSubmitting(true);
    try {
      await register(role, {
        email,
        password,
        full_name: fullName,
        phone: phone || undefined,
        ...(role === "provider" && {
          business_name: businessName || undefined,
          service_types: selectedServices,
          address: address || undefined,
          description: description,
          skills: skills,
        }),
      });
      navigate(role === "customer" ? "/dashboard/customer" : "/dashboard/provider", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const accent = role === "customer" ? "customer" : "provider";
  const accentColor = role === "customer" ? "var(--customer-400)" : "var(--provider-400)";

  return (
    <div style={{ position: "relative", minHeight: "100vh", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "40px 20px" }}>
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
          maxWidth: role === "provider" ? "520px" : "460px",
          padding: "40px 36px",
          animation: "cardIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both",
        }}
      >
        {/* Header */}
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
            {role === "customer" ? "🏠" : "🔧"}
          </div>
          <h1 style={{ fontSize: "22px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "4px" }}>
            Create your account
          </h1>
          <p style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
            {role === "customer"
              ? "Get access to trusted maintenance services"
              : "Join our network of service professionals"}
          </p>
        </div>

        {/* Role tabs */}
        <div className="role-tabs" style={{ marginBottom: "28px" }}>
          <Link to="/signup/customer" style={{ display: "contents" }}>
            <button type="button" className={`role-tab ${role === "customer" ? "active customer" : ""}`}>
              🏠 Customer
            </button>
          </Link>
          <Link to="/signup/provider" style={{ display: "contents" }}>
            <button type="button" className={`role-tab ${role === "provider" ? "active provider" : ""}`}>
              🔧 Provider
            </button>
          </Link>
        </div>

        {/* Form */}
        <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>

          {/* ── Full Name ── */}
          <div className="field-group">
            <label className="field-label" htmlFor="su-fullname">Full name *</label>
            <input
              id="su-fullname"
              className={`auth-input ${accent}`}
              type="text"
              placeholder="Nimal Perera"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              autoComplete="name"
            />
          </div>

          {/* ── Email ── */}
          <div className="field-group">
            <label className="field-label" htmlFor="su-email">Email address *</label>
            <input
              id="su-email"
              className={`auth-input ${accent}`}
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          {/* ── Phone ── */}
          <div className="field-group">
            <label className="field-label" htmlFor="su-phone">Phone number *</label>
            <input
              id="su-phone"
              className={`auth-input ${accent}`}
              type="tel"
              placeholder="+94 71 234 5678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoComplete="tel"
              required
            />
          </div>

          {/* ── Provider-specific section ── */}
          {role === "provider" && (
            <>
              <div style={{
                padding: "16px",
                borderRadius: "var(--radius-md)",
                background: "rgba(99,102,241,0.06)",
                border: "1px solid rgba(99,102,241,0.15)",
                display: "flex",
                flexDirection: "column",
                gap: "14px",
              }}>
                <p style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  If you are an employee from any business organization
                </p>

                <div className="field-group">
                  <label className="field-label" htmlFor="su-bizname">Business name</label>
                  <input
                    id="su-bizname"
                    className="auth-input provider"
                    type="text"
                    placeholder="Perera Maintenance Services"
                    value={businessName}
                    onChange={(e) => setBusinessName(e.target.value)}
                  />
                </div>

                <div className="field-group">
                  <label className="field-label" htmlFor="su-address">Service area / Address</label>
                  <input
                    id="su-address"
                    className="auth-input provider"
                    type="text"
                    placeholder="Colombo 03, Western Province"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                  />
                </div>
              </div>

              <div className="field-group">
                <label className="field-label">Service types * <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(select all that apply)</span></label>
                <div className="chips-wrap">
                  {SERVICE_TYPES.map((svc) => (
                    <button
                      key={svc}
                      type="button"
                      className={`chip ${selectedServices.includes(svc) ? "selected" : ""}`}
                      onClick={() => toggleService(svc)}
                      aria-pressed={selectedServices.includes(svc)}
                    >
                      {svc}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field-group">
                <label className="field-label" htmlFor="su-description">Professional Summary *</label>
                <textarea
                  id="su-description"
                  className="auth-input provider"
                  placeholder="Describe your work experience, background, and expertise in your field of service..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                  rows={4}
                  style={{ fontFamily: "inherit", resize: "vertical", minHeight: "100px" }}
                />
              </div>

              <div className="field-group">
                <label className="field-label" htmlFor="su-skills">Core Skills *</label>
                <textarea
                  id="su-skills"
                  className="auth-input provider"
                  placeholder="List the key skills and specializations you offer (e.g., Plumbing repairs, Water system maintenance, Emergency leak fixes)..."
                  value={skills}
                  onChange={(e) => setSkills(e.target.value)}
                  required
                  rows={3}
                  style={{ fontFamily: "inherit", resize: "vertical", minHeight: "80px" }}
                />
              </div>
            </>
          )}

          {/* ── Password ── */}
          <div className="field-group">
            <label className="field-label" htmlFor="su-password">Password *</label>
            <div style={{ position: "relative" }}>
              <input
                id="su-password"
                className={`auth-input ${accent}`}
                type={showPassword ? "text" : "password"}
                placeholder="Min. 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
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
            {/* Strength indicator */}
            {password.length > 0 && (
              <>
                <div className="strength-bar">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className={`strength-segment ${strength.level >= i ? `active ${strength.cls}` : ""}`}
                    />
                  ))}
                </div>
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  Strength: <span style={{
                    color: strength.cls === "weak" ? "var(--error)" : strength.cls === "fair" ? "var(--warning)" : "var(--success)",
                    fontWeight: 600,
                  }}>{strength.label}</span>
                </span>
              </>
            )}
          </div>

          {/* ── Confirm Password ── */}
          <div className="field-group">
            <label className="field-label" htmlFor="su-confirm">Confirm password *</label>
            <input
              id="su-confirm"
              className={`auth-input ${accent}`}
              type={showPassword ? "text" : "password"}
              placeholder="Re-enter your password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
            {confirmPassword.length > 0 && password !== confirmPassword && (
              <span style={{ fontSize: "12px", color: "var(--error)" }}>Passwords don't match</span>
            )}
          </div>

          {/* ── Terms ── */}
          <label style={{ display: "flex", alignItems: "flex-start", gap: "10px", cursor: "pointer" }}>
            <input
              id="su-terms"
              type="checkbox"
              checked={agreedToTerms}
              onChange={(e) => setAgreedToTerms(e.target.checked)}
              style={{ marginTop: "2px", accentColor: accentColor, flexShrink: 0 }}
            />
            <span style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
              I agree to the{" "}
              <span style={{ color: accentColor, fontWeight: 600 }}>Terms of Service</span>
              {" "}and{" "}
              <span style={{ color: accentColor, fontWeight: 600 }}>Privacy Policy</span>
            </span>
          </label>

          {/* ── Error ── */}
          {error && (
            <div className="auth-alert error" role="alert">
              ⚠️ {error}
            </div>
          )}

          {/* ── Submit ── */}
          <button
            type="submit"
            className={`auth-btn ${accent}`}
            disabled={submitting}
            style={{ marginTop: "4px" }}
            id="signup-submit-btn"
          >
            {submitting ? (
              <><span className="spinner" />Creating account…</>
            ) : (
              `Create ${role === "customer" ? "Customer" : "Provider"} Account`
            )}
          </button>
        </form>

        {/* Footer link */}
        <div style={{ marginTop: "24px", textAlign: "center" }}>
          <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
            Already have an account?{" "}
            <Link
              to={`/login/${role}`}
              style={{ color: accentColor, fontWeight: 600 }}
            >
              Sign in
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
