import {
  ArrowRight,
  Check,
  ChevronRight,
  CircleUserRound,
  Clock3,
  LoaderCircle,
  LogOut,
  MapPin,
  Search,
  ShieldCheck,
  Sparkles,
  Star,
  Wrench,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ApiError, api } from "./api";
import type {
  ProviderRecommendation,
  ProviderProfile,
  ProviderProfileInput,
  RecommendationResponse,
  ServiceRequestInput,
  User,
  UserRole,
} from "./types";

const SESSION_KEY = "weda-session";
const categories = [
  { label: "Electrician", value: "Electricians" },
  { label: "Plumber", value: "Plumbers" },
  { label: "AC Repair", value: "A/C" },
  { label: "CCTV", value: "CCTV" },
  { label: "Carpenter", value: "Carpenters" },
  { label: "Painter", value: "Painters" },
];
const districts = ["Colombo", "Gampaha", "Kalutara", "Galle", "Kandy", "Kurunegala"];

interface Session {
  token: string;
  user: User;
}

function getStoredSession(): Session | null {
  try {
    const value = localStorage.getItem(SESSION_KEY);
    return value ? (JSON.parse(value) as Session) : null;
  } catch {
    return null;
  }
}

function Logo() {
  return (
    <div className="logo" aria-label="weda.lk home">
      <span className="logo-mark"><Wrench size={19} strokeWidth={2.4} /></span>
      <span>weda<span>.lk</span></span>
    </div>
  );
}

function Header({ session, onLogout }: { session: Session | null; onLogout: () => void }) {
  return (
    <header className="site-header">
      <Logo />
      <div className="header-copy"><span className="live-dot" /> Trusted professionals, intelligently matched</div>
      {session && (
        <div className="user-menu">
          <div className="avatar">{session.user.full_name.charAt(0).toUpperCase()}</div>
          <div><strong>{session.user.full_name}</strong><span>{session.user.role}</span></div>
          <button className="icon-button" onClick={onLogout} aria-label="Log out"><LogOut size={18} /></button>
        </div>
      )}
    </header>
  );
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: (session: Session) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [role, setRole] = useState<Exclude<UserRole, "admin">>("customer");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);
    try {
      if (mode === "register") {
        await api.register(role, fullName, email, password);
        setMode("login");
        setNotice("Account created. Sign in to continue.");
      } else {
        const response = await api.login(email, password);
        onAuthenticated({ token: response.access_token, user: response.user });
      }
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to connect to the service.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-story">
        <div className="eyebrow"><Sparkles size={15} /> AI-powered matching for Sri Lanka</div>
        <h1>The right professional.<br /><em>Right when you need them.</em></h1>
        <p>Describe the job once. Our hybrid recommendation engine evaluates thousands of providers and gives you the 20 strongest matches.</p>
        <div className="trust-row">
          <div><strong>10K+</strong><span>providers analysed</span></div>
          <div><strong>3-way</strong><span>intelligent scoring</span></div>
          <div><strong>Top 20</strong><span>tailored matches</span></div>
        </div>
        <div className="story-card">
          <div className="mini-avatar">RK</div>
          <div><div className="stars">★★★★★</div><p>“Found a reliable electrician nearby in minutes. The score breakdown made the choice easy.”</p><span>Ruwani K. · Colombo</span></div>
        </div>
      </section>
      <section className="auth-card-wrap">
        <div className="auth-card">
          <div className="auth-heading">
            <span className="auth-icon"><CircleUserRound size={24} /></span>
            <div><h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2><p>{mode === "login" ? "Sign in to find your next professional." : "Join Sri Lanka’s smarter service network."}</p></div>
          </div>
          <div className="tab-list">
            <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Sign in</button>
            <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Register</button>
          </div>
          <form onSubmit={submit} className="form-stack">
            {mode === "register" && (
              <>
                <fieldset className="account-type"><legend>Account type</legend><div className="role-picker">
                  <button type="button" className={role === "customer" ? "selected" : ""} onClick={() => setRole("customer")}>I need a service</button>
                  <button type="button" className={role === "provider" ? "selected" : ""} onClick={() => setRole("provider")}>I provide services</button>
                </div></fieldset>
                <label>Full name<input required minLength={2} value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your full name" /></label>
              </>
            )}
            <label>Email address<input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></label>
            <label>Password<input required type="password" minLength={mode === "register" ? 8 : 1} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" /></label>
            {notice && <div className="notice success"><Check size={16} />{notice}</div>}
            {error && <div className="notice error">{error}</div>}
            <button className="primary-button" disabled={loading}>{loading ? <LoaderCircle className="spin" size={18} /> : mode === "login" ? "Sign in" : "Create account"}<ArrowRight size={18} /></button>
          </form>
          <div className="secure-note"><ShieldCheck size={16} /> Secure authentication · Your data stays protected</div>
        </div>
      </section>
    </main>
  );
}

function ScoreBar({ label, value, tone }: { label: string; value: number; tone: string }) {
  return <div className="score-item"><div><span>{label}</span><strong>{Math.round(value * 100)}</strong></div><div className="score-track"><i style={{ width: `${value * 100}%`, background: tone }} /></div></div>;
}

function ProviderCard({ provider, rank }: { provider: ProviderRecommendation; rank: number }) {
  return (
    <article className="provider-card">
      <div className="rank">{String(rank).padStart(2, "0")}</div>
      <div className="provider-main">
        <div className="provider-title"><div><h3>{provider.provider_name}</h3><p><MapPin size={14} />{provider.city}, {provider.district}<span />{provider.category}</p></div><div className="match-pill"><Sparkles size={14} />{Math.round(provider.hybrid_score * 100)}% match</div></div>
        <p className="provider-description">{provider.description}</p>
        <div className="provider-meta"><span><Star size={15} fill="currentColor" />{provider.rating.toFixed(1)} <small>({provider.review_count})</small></span><span><Clock3 size={15} />{provider.experience_years} years</span><span><ShieldCheck size={15} />{Math.round(provider.booking_success_rate * 100)}% success</span></div>
      </div>
      <div className="score-panel">
        <ScoreBar label="Semantic" value={provider.bert_score} tone="#0f766e" />
        <ScoreBar label="Content" value={provider.tfidf_score} tone="#d97706" />
        <ScoreBar label="History" value={provider.cf_score} tone="#7c3aed" />
      </div>
    </article>
  );
}

function CustomerDashboard({ session }: { session: Session }) {
  const [form, setForm] = useState<ServiceRequestInput>({ request_text: "", category: "Electricians", district: "Colombo", city: "", urgency: "normal" });
  const [recommendations, setRecommendations] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function update<K extends keyof ServiceRequestInput>(key: K, value: ServiceRequestInput[K]) { setForm((current) => ({ ...current, [key]: value })); }

  async function findProviders(event: FormEvent) {
    event.preventDefault();
    setLoading(true); setError(""); setRecommendations(null);
    try {
      const created = await api.createServiceRequest(form, session.token);
      setRecommendations(await api.recommend(created, session.token));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to generate recommendations.");
    } finally { setLoading(false); }
  }

  return (
    <main className="dashboard">
      <section className="dashboard-intro">
        <div><div className="eyebrow"><Sparkles size={15} /> Component 1 · Hybrid recommendation engine</div><h1>What needs fixing today?</h1><p>Tell us about the job. We’ll compare content, meaning and service history to rank your best 20 providers.</p></div>
        <div className="engine-badge"><span className="pulse" /><div><strong>Recommendation engine</strong><small>Online · 10,000 providers</small></div></div>
      </section>
      <section className="request-panel">
        <form onSubmit={findProviders}>
          <label className="wide">Describe the work<textarea required minLength={10} value={form.request_text} onChange={(e) => update("request_text", e.target.value)} placeholder="e.g. My living room power sockets stopped working after last night's rain..." /></label>
          <label>Service category<select value={form.category} onChange={(e) => update("category", e.target.value)}>{categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label>District<select value={form.district} onChange={(e) => update("district", e.target.value)}>{districts.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>City<input required value={form.city} onChange={(e) => update("city", e.target.value)} placeholder="e.g. Kottawa" /></label>
          <label>Urgency<select value={form.urgency} onChange={(e) => update("urgency", e.target.value as ServiceRequestInput["urgency"])}><option value="normal">Normal</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option></select></label>
          <button className="find-button" disabled={loading}>{loading ? <LoaderCircle className="spin" size={19} /> : <Search size={19} />}{loading ? "Analysing providers..." : "Find my best matches"}<ChevronRight size={19} /></button>
        </form>
        {error && <div className="notice error request-error">{error}</div>}
      </section>
      {loading && <section className="loading-panel"><div className="loader-orbit"><Sparkles size={25} /></div><h2>Building your Top 20</h2><p>Comparing semantic relevance, content signals and your service history…</p></section>}
      {recommendations && (
        <section className="results-section">
          <div className="results-heading"><div><span className="result-count">{recommendations.results.length}</span><div><h2>Your strongest matches</h2><p>Ranked for request {recommendations.request_id}</p></div></div><span className="model-version">Model {recommendations.model_version}</span></div>
          {recommendations.results.length ? <div className="provider-list">{recommendations.results.map((provider, index) => <ProviderCard key={provider.provider_id} provider={provider} rank={index + 1} />)}</div> : <div className="empty-state"><Search size={28} /><h3>No providers matched these filters</h3><p>Try a nearby city or broaden the category.</p></div>}
        </section>
      )}
    </main>
  );
}

function ProviderDashboard({ session }: { session: Session }) {
  const [profile, setProfile] = useState<ProviderProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<ProviderProfileInput>({
    provider_name: "",
    category: "Electricians",
    district: "Colombo",
    city: "",
    experience_years: 0,
    skills: [],
    description: "",
  });
  const [skillsText, setSkillsText] = useState("");

  useEffect(() => {
    api.getProviderProfile(session.token)
      .then(setProfile)
      .catch((reason) => {
        if (!(reason instanceof ApiError) || reason.status !== 404) {
          setError(reason instanceof ApiError ? reason.message : "Unable to load your profile.");
        }
      })
      .finally(() => setLoading(false));
  }, [session.token]);

  function update<K extends keyof ProviderProfileInput>(key: K, value: ProviderProfileInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function createProfile(event: FormEvent) {
    event.preventDefault();
    setSaving(true); setError("");
    try {
      const skills = skillsText.split(",").map((skill) => skill.trim()).filter(Boolean);
      setProfile(await api.createProviderProfile({ ...form, skills }, session.token));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to create your profile.");
    } finally { setSaving(false); }
  }

  if (loading) return <main className="dashboard"><section className="loading-panel"><LoaderCircle className="spin" /><h2>Loading provider workspace</h2></section></main>;
  if (profile) return (
    <main className="dashboard">
      <section className="provider-profile-card">
        <div className="profile-check"><Check size={24} /></div>
        <div><div className="eyebrow"><ShieldCheck size={15} /> Live in Component 1</div><h1>{profile.provider_name}</h1><p>{profile.description}</p>
          <div className="profile-tags"><span>{profile.category}</span><span><MapPin size={13} />{profile.city}, {profile.district}</span><span><Clock3 size={13} />{profile.experience_years} years</span></div>
          <div className="profile-index-note"><Sparkles size={17} /><div><strong>Your profile is recommendation-ready</strong><small>It is scored live alongside the 10,000 research providers. New profiles use a neutral history score until interactions are recorded.</small></div></div>
        </div>
      </section>
    </main>
  );

  return (
    <main className="dashboard">
      <section className="dashboard-intro"><div><div className="eyebrow"><Wrench size={15} /> Provider onboarding</div><h1>Build your service profile.</h1><p>These details are indexed by Component 1 so relevant customers can discover your business in their Top-20 results.</p></div></section>
      <section className="request-panel provider-form"><form onSubmit={createProfile}>
        <label>Business or display name<input required minLength={2} value={form.provider_name} onChange={(e) => update("provider_name", e.target.value)} placeholder="e.g. Nimali Electrical Care" /></label>
        <label>Service category<select value={form.category} onChange={(e) => update("category", e.target.value)}>{categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label>District<select value={form.district} onChange={(e) => update("district", e.target.value)}>{districts.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>City<input required value={form.city} onChange={(e) => update("city", e.target.value)} placeholder="e.g. Kottawa" /></label>
        <label>Experience in years<input required type="number" min={0} max={80} value={form.experience_years} onChange={(e) => update("experience_years", Number(e.target.value))} /></label>
        <label className="skills-field">Skills, separated by commas<input required value={skillsText} onChange={(e) => setSkillsText(e.target.value)} placeholder="house wiring, socket repair, safety inspection" /></label>
        <label className="wide">About your service<textarea required minLength={10} value={form.description} onChange={(e) => update("description", e.target.value)} placeholder="Describe the work you specialise in and the areas you serve..." /></label>
        <button className="find-button" disabled={saving}>{saving ? <LoaderCircle className="spin" size={19} /> : <Sparkles size={19} />}{saving ? "Creating profile..." : "Create and index my profile"}<ChevronRight size={19} /></button>
      </form>{error && <div className="notice error request-error">{error}</div>}</section>
    </main>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(() => getStoredSession());
  const [checking, setChecking] = useState(Boolean(session));

  useEffect(() => {
    const storedSession = getStoredSession();
    if (!storedSession) return;
    api.me(storedSession.token).then((user) => {
      const next = { ...storedSession, user }; setSession(next); localStorage.setItem(SESSION_KEY, JSON.stringify(next));
    }).catch(() => { localStorage.removeItem(SESSION_KEY); setSession(null); }).finally(() => setChecking(false));
  }, []);

  const authenticated = useMemo(() => (next: Session) => { localStorage.setItem(SESSION_KEY, JSON.stringify(next)); setSession(next); }, []);
  function logout() { localStorage.removeItem(SESSION_KEY); setSession(null); }

  if (checking) return <div className="app-loading"><Logo /><LoaderCircle className="spin" /></div>;
  return <div className="app-shell"><Header session={session} onLogout={logout} />{!session ? <AuthScreen onAuthenticated={authenticated} /> : session.user.role === "customer" ? <CustomerDashboard session={session} /> : <ProviderDashboard session={session} />}</div>;
}
