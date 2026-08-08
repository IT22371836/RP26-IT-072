import {
  ArrowRight,
  BarChart3,
  CalendarCheck,
  Check,
  ChevronRight,
  CircleUserRound,
  Clock3,
  LoaderCircle,
  LogOut,
  ClipboardList,
  Heart,
  MessageSquare,
  MapPin,
  Search,
  ShieldCheck,
  UserRound,
  Sparkles,
  Star,
  Wrench,
} from "lucide-react";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, api } from "./api";
import {
  COMPONENT2_HANDOFF_READINESS,
  buildComponent2IntegrationFixture,
  validateComponent4CandidateHandoff,
} from "./component2-handoff";
import type {
  Component4RankedProvider,
  Component4RankResponse,
  ProviderRecommendation,
  ProviderProfile,
  ProviderProfileInput,
  ProviderTrustProfile,
  CustomerProfile,
  CustomerProfileUpdate,
  Interaction,
  ServiceRequest,
  RecommendationResponse,
  ServiceRequestInput,
  User,
  UserRole,
  AdminOverview,
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
        onAuthenticated({ token: response.access_token ?? "", user: response.user });
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
        <p>Describe the job once. Our relevance and review-intelligence pipeline evaluates thousands of providers and returns five trust-aware matches.</p>
        <div className="trust-row">
          <div><strong>10K+</strong><span>providers analysed</span></div>
          <div><strong>3-way</strong><span>intelligent scoring</span></div>
          <div><strong>Top 5</strong><span>trust-aware matches</span></div>
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

function ProviderTrustProfileView({ profile }: { profile: ProviderTrustProfile }) {
  const aspects = [
    ["Quality", profile.aspect_performance.quality, "#0f766e"],
    ["Communication", profile.aspect_performance.communication, "#2563eb"],
    ["Professionalism", profile.aspect_performance.professionalism, "#7c3aed"],
    ["Punctuality", profile.aspect_performance.punctuality, "#d97706"],
  ] as const;

  return (
    <section className="trust-profile" aria-label={`${profile.provider_name} trust profile`}>
      <div className="trust-profile-heading">
        <div>
          <div className="eyebrow"><ShieldCheck size={15} /> Verified trust profile</div>
          <h2>{profile.provider_name}</h2>
          <p><MapPin size={14} />{profile.city}, {profile.district}<span />{profile.category}</p>
        </div>
        <span className={`evidence-pill ${profile.evidence_status}`}>{profile.evidence_status} evidence</span>
      </div>

      <div className="trust-metric-grid">
        <article><Star size={19} fill="currentColor" /><strong>{profile.average_rating.toFixed(1)}</strong><span>Average Rating</span></article>
        <article><MessageSquare size={19} /><strong>{profile.review_count}</strong><span>Review Count</span></article>
        <article><ShieldCheck size={19} /><strong>{Math.round(profile.overall_trust_score * 100)}%</strong><span>Overall Trust Score</span></article>
      </div>

      <div className="trust-profile-section">
        <div className="trust-section-heading"><div><h3>Aspect Performance</h3><p>Review intelligence across the four service-quality aspects.</p></div></div>
        <div className="aspect-performance-grid">
          {aspects.map(([label, value, tone]) => (
            <ScoreBar key={label} label={label} value={value} tone={tone} />
          ))}
        </div>
        <div className="trust-evidence-note">
          <ShieldCheck size={16} />
          <span>{profile.analyzed_review_count} reviews analysed · {Math.round(profile.mean_review_credibility * 100)}% mean credibility · {profile.score_source === "category_prior" ? "Category-prior fallback" : "CATF evidence score"}</span>
        </div>
      </div>

      <div className="trust-profile-section">
        <div className="trust-section-heading"><div><h3>Customer Reviews</h3><p>Latest verified platform feedback and credible research evidence.</p></div></div>
        {profile.customer_reviews.length ? (
          <div className="customer-review-list">
            {profile.customer_reviews.map((review, index) => (
              <article className="customer-review" key={`${review.reviewed_at}-${index}`}>
                <div className="customer-review-meta">
                  <strong><Star size={14} fill="currentColor" />{review.rating.toFixed(1)}</strong>
                  <span>{new Date(review.reviewed_at).toLocaleDateString()}</span>
                  <span>{review.source === "platform" ? "Verified platform booking" : "Credible research review"}</span>
                </div>
                <p>{review.review_text ?? "Rating submitted without a written comment."}</p>
              </article>
            ))}
          </div>
        ) : <div className="empty-reviews"><MessageSquare size={21} /><span>No customer reviews yet.</span></div>}
      </div>
    </section>
  );
}

function ProviderCard({ provider, rank }: { provider: ProviderRecommendation; rank: number }) {
  return (
    <article className="provider-card">
      <div className="rank">{String(rank).padStart(2, "0")}</div>
      <div className="provider-main">
        <div className="provider-title"><div><h3>{provider.provider_name}</h3><p><MapPin size={14} />{provider.city}, {provider.district}<span />{provider.category}</p></div><div className="match-pill"><Sparkles size={14} />{Math.round(provider.hybrid_score * 100)}% match</div></div>
        <p className="provider-description">{provider.description}</p>
        <div className="provider-meta"><span><Star size={15} fill="currentColor" />{provider.rating.toFixed(1)} <small>({provider.review_count})</small></span><span><Clock3 size={15} />{provider.experience_years} years</span><span><ShieldCheck size={15} />{Math.round(provider.booking_success_rate * 100)}% success</span></div>
        <span className="preview-only"><ShieldCheck size={13} />Component 1 preview only</span>
      </div>
      <div className="score-panel">
        <ScoreBar label="Semantic" value={provider.bert_score} tone="#0f766e" />
        <ScoreBar label="Content" value={provider.tfidf_score} tone="#d97706" />
        <ScoreBar label="History" value={provider.cf_score} tone="#7c3aed" />
      </div>
    </article>
  );
}

function TrustProviderCard({
  provider,
  selected,
  selecting,
  profileLoading,
  onSelect,
  onViewProfile,
}: {
  provider: Component4RankedProvider;
  selected: boolean;
  selecting: boolean;
  profileLoading: boolean;
  onSelect: () => Promise<void>;
  onViewProfile: () => Promise<void>;
}) {
  const aspectValues = [
    ["Quality", provider.aspect_scores.quality, "#0f766e"],
    ["Punctuality", provider.aspect_scores.punctuality, "#d97706"],
    ["Communication", provider.aspect_scores.communication, "#2563eb"],
    ["Professionalism", provider.aspect_scores.professionalism, "#7c3aed"],
  ] as const;

  return (
    <article className="provider-card trust-provider-card">
      <div className="rank">{String(provider.rank).padStart(2, "0")}</div>
      <div className="provider-main">
        <div className="provider-title">
          <div>
            <h3>{provider.provider_name}</h3>
            <p><MapPin size={14} />{provider.city}, {provider.district}<span />{provider.category}</p>
          </div>
          <div className="match-pill trust-pill"><ShieldCheck size={14} />{Math.round(provider.final_score * 100)}% trust</div>
        </div>
        <div className="provider-meta trust-meta">
          <span><Star size={15} fill="currentColor" />{provider.platform_rating.toFixed(1)} <small>({provider.platform_review_count})</small></span>
          <span><ShieldCheck size={15} />{Math.round(provider.mean_credibility * 100)}% review credibility</span>
          <span>{provider.review_count} analysed reviews</span>
        </div>
        <div className="evidence-row">
          <span className={`evidence-pill ${provider.evidence_status}`}>{provider.evidence_status} evidence</span>
          <small>Effective reviews {provider.effective_review_count.toFixed(1)} · Reliability {Math.round(provider.reliability_factor * 100)}%</small>
        </div>
        <div className="provider-actions">
          <button type="button" className="view-provider" disabled={profileLoading} onClick={onViewProfile}>
            {profileLoading ? <LoaderCircle className="spin" size={14} /> : <CircleUserRound size={14} />}
            {profileLoading ? "Loading profile..." : "View full profile"}
          </button>
          <button type="button" className="select-provider" disabled={selected || selecting} onClick={onSelect}>
            {selected ? <Check size={14} /> : selecting ? <LoaderCircle className="spin" size={14} /> : <Heart size={14} />}
            {selected ? "Selected" : selecting ? "Saving..." : "Select this provider"}
          </button>
        </div>
      </div>
      <div className="score-panel trust-score-panel">
        {aspectValues.map(([label, value, tone]) => (
          <ScoreBar
            key={label}
            label={label}
            value={(value + 1) / 2}
            tone={tone}
          />
        ))}
      </div>
    </article>
  );
}

function HistoryPage({ title, subtitle, icon, empty, children }: { title: string; subtitle: string; icon: ReactNode; empty: string; children: ReactNode }) {
  const hasChildren = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return <section className="history-page"><div className="page-heading"><span>{icon}</span><div><h1>{title}</h1><p>{subtitle}</p></div></div>{hasChildren ? <div className="history-list">{children}</div> : <div className="empty-state"><ClipboardList size={28} /><h3>{empty}</h3></div>}</section>;
}

function HistoryCard({ title, meta, status, date, action }: { title: string; meta: string; status: string; date: string; action?: ReactNode }) {
  return <article className="history-card"><div><h3>{title}</h3><p>{meta}</p><time>{new Date(date).toLocaleString()}</time></div><div className="history-card-side"><span className={`status-tag ${status}`}>{status.replaceAll("_", " ")}</span>{action}</div></article>;
}

function InteractionPage({ title, subtitle, interactions, empty, onAction, actionLabel, renderAction }: { title: string; subtitle: string; interactions: Interaction[]; empty: string; onAction?: (item: Interaction) => Promise<void>; actionLabel?: string; renderAction?: (item: Interaction) => ReactNode }) {
  return <HistoryPage title={title} subtitle={subtitle} icon={<Heart size={24} />} empty={empty}>{interactions.map((item) => <HistoryCard key={item.interaction_id} title={item.provider_name ?? item.provider_id} meta={`${item.category} · Request ${item.request_id}`} status={item.interaction_type} date={item.timestamp} action={renderAction?.(item) ?? (onAction && <button className="small-action" onClick={() => onAction(item)}>{actionLabel}<ChevronRight size={13} /></button>)} />)}</HistoryPage>;
}

function RatingAction({ interaction, token, onSaved }: { interaction: Interaction; token: string; onSaved: () => Promise<void> }) {
  const [rating, setRating] = useState(5);
  const [reviewText, setReviewText] = useState("");
  const [saving, setSaving] = useState(false);
  return (
    <div className="rating-action">
      <select aria-label="Rating" value={rating} onChange={(event) => setRating(Number(event.target.value))}>
        {[5, 4, 3, 2, 1].map((value) => <option key={value} value={value}>{value} stars</option>)}
      </select>
      <input aria-label="Written review" maxLength={2000} value={reviewText} onChange={(event) => setReviewText(event.target.value)} placeholder="Share your experience (optional)" />
      <button className="small-action" disabled={saving} onClick={async () => {
        setSaving(true);
        try {
          await api.rateBooking(interaction.interaction_id, rating, reviewText, token);
          await onSaved();
        } finally { setSaving(false); }
      }}>{saving ? "Saving..." : "Submit review"}</button>
    </div>
  );
}

function CustomerDashboard({ session }: { session: Session }) {
  type CustomerSection = "find" | "requests" | "selected" | "bookings" | "ratings" | "profile";
  const [section, setSection] = useState<CustomerSection>("find");
  const [form, setForm] = useState<ServiceRequestInput>({ request_text: "", category: "Electricians", district: "Colombo", city: "", urgency: "normal" });
  const [recommendations, setRecommendations] = useState<RecommendationResponse | null>(null);
  const [finalRanking, setFinalRanking] = useState<Component4RankResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState<"component1" | "component4">("component1");
  const [selectingProviderId, setSelectingProviderId] = useState<string | null>(null);
  const [profileLoadingProviderId, setProfileLoadingProviderId] = useState<string | null>(null);
  const [viewingProvider, setViewingProvider] = useState<ProviderTrustProfile | null>(null);
  const [error, setError] = useState("");
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileForm, setProfileForm] = useState<CustomerProfileUpdate>({ phone: null, district: null, city: null, preferred_language: "English" });
  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [interactions, setInteractions] = useState<Interaction[]>([]);

  const refreshHistory = useCallback(async () => {
    const [requestHistory, interactionHistory] = await Promise.all([
      api.listServiceRequests(session.token),
      api.listInteractions(session.token),
    ]);
    setRequests(requestHistory);
    setInteractions(interactionHistory);
  }, [session.token]);

  useEffect(() => {
    api.getCustomerProfile(session.token).then((value) => {
      setProfile(value);
      setProfileForm({ phone: value.phone, district: value.district, city: value.city, preferred_language: value.preferred_language });
      setProfileOpen(!value.city || !value.phone);
    }).catch(() => setError("Unable to load your customer profile."));
  }, [session.token]);

  useEffect(() => { refreshHistory().catch(() => setError("Unable to load account history.")); }, [refreshHistory]);

  function update<K extends keyof ServiceRequestInput>(key: K, value: ServiceRequestInput[K]) { setForm((current) => ({ ...current, [key]: value })); }

  async function findProviders(event: FormEvent) {
    event.preventDefault();
    if (!COMPONENT2_HANDOFF_READINESS.ready) {
      setError(COMPONENT2_HANDOFF_READINESS.detail);
      return;
    }
    setLoading(true); setLoadingStage("component1"); setError(""); setRecommendations(null); setFinalRanking(null);
    try {
      const created = await api.createServiceRequest(form, session.token);
      const component1Result = await api.recommend(created, session.token);
      setRecommendations(component1Result);
      const handoff = buildComponent2IntegrationFixture(component1Result);
      const candidateIds = validateComponent4CandidateHandoff(
        handoff,
        component1Result,
        import.meta.env.PROD,
      );
      if (!candidateIds.length) return;
      setLoadingStage("component4");
      setFinalRanking(
        await api.rankComponent4(
          { ...handoff, provider_ids: candidateIds },
          session.token,
        ),
      );
      await refreshHistory();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to generate recommendations.");
    } finally { setLoading(false); }
  }

  async function selectProvider(provider: Component4RankedProvider) {
    if (!finalRanking) return;
    setSelectingProviderId(provider.provider_id);
    setError("");
    try {
      await api.logInteraction(
        {
          request_id: finalRanking.request_id,
          provider_id: provider.provider_id,
          provider_name: provider.provider_name,
          category: provider.category,
          interaction_type: "selected",
        },
        session.token,
      );
      await refreshHistory();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to save provider selection.");
    } finally {
      setSelectingProviderId(null);
    }
  }

  async function viewProviderProfile(providerId: string) {
    setProfileLoadingProviderId(providerId);
    setError("");
    try {
      setViewingProvider(await api.getProviderTrustProfile(providerId, session.token));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to load provider profile.");
    } finally {
      setProfileLoadingProviderId(null);
    }
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault(); setProfileSaving(true); setError("");
    try { setProfile(await api.updateCustomerProfile(profileForm, session.token)); setProfileOpen(false); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Unable to save your profile."); }
    finally { setProfileSaving(false); }
  }

  return (
    <main className="workspace">
      <aside className="workspace-sidebar">
        <div><small>Customer workspace</small><h2>{session.user.full_name}</h2></div>
        <nav>
          {([
            ["find", Search, "Find Providers"], ["requests", ClipboardList, "My Requests"],
            ["selected", Heart, "Selected Providers"], ["bookings", CalendarCheck, "My Bookings"],
            ["ratings", MessageSquare, "Ratings & Reviews"], ["profile", UserRound, "My Profile"],
          ] as const).map(([key, Icon, label]) => <button key={key} className={section === key ? "active" : ""} onClick={() => setSection(key)}><Icon size={17} />{label}</button>)}
        </nav>
        <div className="sidebar-engine"><span className="live-dot" /><div><strong>Trust ranking online</strong><small>Top-20 → fixture Top-10 → final Top-5</small></div></div>
      </aside>
      <div className="workspace-content">
      {section === "find" && <>
      <section className="dashboard-intro">
        <div><div className="eyebrow"><Sparkles size={15} /> Components 1 + 4 · Relevance and trust ranking</div><h1>What needs fixing today?</h1><p>Tell us about the job. We’ll find relevant providers, then apply review intelligence to return the final five.</p></div>
        <div className="engine-badge"><span className="pulse" /><div><strong>Recommendation engine</strong><small>Online · 10,000 providers</small></div></div>
      </section>
      <section className="customer-profile-strip">
        <div><CircleUserRound size={20} /><div><strong>{profile?.city ? `${profile.city}, ${profile.district}` : "Complete your customer profile"}</strong><span>{profile?.preferred_language ?? "English"} · Request and selection history enabled</span></div></div>
        <button onClick={() => setProfileOpen((value) => !value)}>{profileOpen ? "Close" : "Edit profile"}</button>
      </section>
      {profileOpen && <section className="profile-editor"><form onSubmit={saveProfile}>
        <label>Phone number<input required minLength={7} value={profileForm.phone ?? ""} onChange={(e) => setProfileForm((current) => ({ ...current, phone: e.target.value }))} placeholder="+94 77 123 4567" /></label>
        <label>Home district<select value={profileForm.district ?? ""} onChange={(e) => setProfileForm((current) => ({ ...current, district: e.target.value }))}><option value="" disabled>Select district</option>{districts.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>Home city<input required value={profileForm.city ?? ""} onChange={(e) => setProfileForm((current) => ({ ...current, city: e.target.value }))} placeholder="e.g. Kottawa" /></label>
        <label>Preferred language<select value={profileForm.preferred_language} onChange={(e) => setProfileForm((current) => ({ ...current, preferred_language: e.target.value }))}><option>English</option><option>Sinhala</option><option>Tamil</option></select></label>
        <button className="primary-button" disabled={profileSaving}>{profileSaving ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />}Save profile</button>
      </form></section>}
      <section className="request-panel">
        <form onSubmit={findProviders}>
          <label className="wide">Describe the work<textarea required minLength={10} value={form.request_text} onChange={(e) => update("request_text", e.target.value)} placeholder="e.g. My living room power sockets stopped working after last night's rain..." /></label>
          <label>Service category<select value={form.category} onChange={(e) => update("category", e.target.value)}>{categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label>District<select value={form.district} onChange={(e) => update("district", e.target.value)}>{districts.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label>City<input required value={form.city} onChange={(e) => update("city", e.target.value)} placeholder="e.g. Kottawa" /></label>
          <label>Urgency<select value={form.urgency} onChange={(e) => update("urgency", e.target.value as ServiceRequestInput["urgency"])}><option value="normal">Normal</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option></select></label>
          <button className="find-button" disabled={loading || !COMPONENT2_HANDOFF_READINESS.ready}>{loading ? <LoaderCircle className="spin" size={19} /> : <Search size={19} />}{loading ? "Analysing providers..." : "Find my best matches"}<ChevronRight size={19} /></button>
        </form>
        {!COMPONENT2_HANDOFF_READINESS.ready && <div className="notice error request-error">{COMPONENT2_HANDOFF_READINESS.detail}</div>}
        {error && <div className="notice error request-error">{error}</div>}
      </section>
      {loading && <section className="loading-panel"><div className="loader-orbit"><Sparkles size={25} /></div><h2>{loadingStage === "component1" ? "Finding relevant providers" : "Building your trust-aware Top 5"}</h2><p>{loadingStage === "component1" ? "Comparing semantic relevance, content signals and your service history…" : "Fusing aspect sentiment, review credibility and evidence reliability…"}</p></section>}
      {finalRanking && (
        <section className="results-section">
          <div className="pipeline-preview fixture"><Sparkles size={17} /><div><strong>Component 2 integration fixture</strong><small>Component 2 is not merged yet. This development handoff passes the first 10 unique Component 1 IDs to the real Component 4 CATF ranker; it is not presented as Component 2 output.</small></div></div>
          <div className="results-heading"><div><span className="result-count">{finalRanking.output_count}</span><div><h2>Your trust-aware final matches</h2><p>CATF-ranked for request {finalRanking.request_id} · Run {finalRanking.run_id}</p></div></div><span className="model-version">CATF {finalRanking.versions.catf_version}</span></div>
          <div className="provider-list">
            {finalRanking.providers.map((provider) => (
              <TrustProviderCard
                key={provider.provider_id}
                provider={provider}
                selected={interactions.some(
                  (item) =>
                    item.request_id === finalRanking.request_id
                    && item.provider_id === provider.provider_id
                    && item.interaction_type === "selected",
                )}
                selecting={selectingProviderId === provider.provider_id}
                profileLoading={profileLoadingProviderId === provider.provider_id}
                onSelect={() => selectProvider(provider)}
                onViewProfile={() => viewProviderProfile(provider.provider_id)}
              />
            ))}
          </div>
        </section>
      )}
      {recommendations && (
        <details className="component1-details" open={!finalRanking}>
          <summary>Inspect Component 1 candidates ({recommendations.results.length})</summary>
          <div className="pipeline-preview"><Sparkles size={17} /><div><strong>Component 1 Top-20 preview</strong><small>These are relevance candidates. Only the Component 4 results above are the final selectable providers.</small></div></div>
          {recommendations.results.length ? <div className="provider-list">{recommendations.results.map((provider, index) => <ProviderCard key={provider.provider_id} provider={provider} rank={index + 1} />)}</div> : <div className="empty-state"><Search size={28} /><h3>No providers matched these filters</h3><p>Try a nearby city or broaden the category.</p></div>}
        </details>
      )}
      </>}
      {section === "requests" && <HistoryPage title="My Requests" subtitle="Every service request you have submitted." icon={<ClipboardList size={24} />} empty="No service requests yet.">{requests.map((request) => <HistoryCard key={request.request_id} title={request.request_text} meta={`${request.category} · ${request.city}, ${request.district}`} status={request.urgency} date={request.created_at} />)}</HistoryPage>}
      {section === "selected" && <InteractionPage title="Selected Providers" subtitle="Provider selection starts after Component 4 returns the final Top-5." interactions={interactions.filter((item) => item.interaction_type === "selected")} empty="No final Top-5 provider has been selected yet." renderAction={(item) => <button className="small-action" onClick={() => viewProviderProfile(item.provider_id)}>View profile<ChevronRight size={13} /></button>} />}
      {section === "bookings" && <InteractionPage title="My Bookings" subtitle="Track booking requests and completed service history." interactions={interactions.filter((item) => item.interaction_type.startsWith("booking_"))} empty="No booking activity yet." renderAction={(item) => item.interaction_type === "booking_completed" && !interactions.some((event) => event.interaction_type === "rated" && event.request_id === item.request_id && event.provider_id === item.provider_id) ? <RatingAction interaction={item} token={session.token} onSaved={refreshHistory} /> : undefined} />}
      {section === "ratings" && <InteractionPage title="Ratings & Reviews" subtitle="Your provider feedback history." interactions={interactions.filter((item) => item.interaction_type === "rated")} empty="You have not rated a provider yet." renderAction={(item) => <button className="small-action" onClick={() => viewProviderProfile(item.provider_id)}>View profile<ChevronRight size={13} /></button>} />}
      {section === "profile" && <HistoryPage title="My Profile" subtitle="Contact and location preferences used across your requests." icon={<UserRound size={24} />} empty=""><section className="profile-editor standalone"><form onSubmit={saveProfile}><label>Phone number<input required minLength={7} value={profileForm.phone ?? ""} onChange={(e) => setProfileForm((current) => ({ ...current, phone: e.target.value }))} /></label><label>District<select value={profileForm.district ?? ""} onChange={(e) => setProfileForm((current) => ({ ...current, district: e.target.value }))}>{districts.map((item) => <option key={item}>{item}</option>)}</select></label><label>City<input required value={profileForm.city ?? ""} onChange={(e) => setProfileForm((current) => ({ ...current, city: e.target.value }))} /></label><label>Language<select value={profileForm.preferred_language} onChange={(e) => setProfileForm((current) => ({ ...current, preferred_language: e.target.value }))}><option>English</option><option>Sinhala</option><option>Tamil</option></select></label><button className="primary-button" disabled={profileSaving}>Save profile</button></form></section></HistoryPage>}
      {error && section !== "find" && <div className="notice error request-error">{error}</div>}
      </div>
      {viewingProvider && (
        <div className="profile-modal" role="dialog" aria-modal="true" aria-label="Provider trust profile">
          <div className="profile-modal-panel">
            <button type="button" className="profile-modal-close" onClick={() => setViewingProvider(null)} aria-label="Close provider profile">×</button>
            <ProviderTrustProfileView profile={viewingProvider} />
          </div>
        </div>
      )}
    </main>
  );
}

function ProviderProfilePage({ session }: { session: Session }) {
  const [profile, setProfile] = useState<ProviderProfile | null>(null);
  const [trustProfile, setTrustProfile] = useState<ProviderTrustProfile | null>(null);
  const [trustLoading, setTrustLoading] = useState(false);
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

  const loadTrustProfile = useCallback(async (providerId: string) => {
    setTrustLoading(true);
    try {
      setTrustProfile(await api.getProviderTrustProfile(providerId, session.token));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to load your trust profile.");
    } finally {
      setTrustLoading(false);
    }
  }, [session.token]);

  useEffect(() => {
    api.getProviderProfile(session.token)
      .then((value) => {
        setProfile(value);
        void loadTrustProfile(value.provider_id);
      })
      .catch((reason) => {
        if (!(reason instanceof ApiError) || reason.status !== 404) {
          setError(reason instanceof ApiError ? reason.message : "Unable to load your profile.");
        }
      })
      .finally(() => setLoading(false));
  }, [loadTrustProfile, session.token]);

  function update<K extends keyof ProviderProfileInput>(key: K, value: ProviderProfileInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function createProfile(event: FormEvent) {
    event.preventDefault();
    setSaving(true); setError("");
    try {
      const skills = skillsText.split(",").map((skill) => skill.trim()).filter(Boolean);
      const created = await api.createProviderProfile({ ...form, skills }, session.token);
      setProfile(created);
      await loadTrustProfile(created.provider_id);
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
      {trustLoading && <section className="loading-panel compact"><LoaderCircle className="spin" /><h2>Loading trust intelligence</h2></section>}
      {trustProfile && <ProviderTrustProfileView profile={trustProfile} />}
      {error && <div className="notice error request-error">{error}</div>}
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

function ProviderDashboard({ session }: { session: Session }) {
  const [section, setSection] = useState("profile");
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [error, setError] = useState("");
  const items = [["overview", BarChart3, "Overview"], ["jobs", ClipboardList, "Job Offers"], ["bookings", CalendarCheck, "My Bookings"], ["reviews", MessageSquare, "Reviews & Ratings"], ["profile", UserRound, "Provider Profile"]] as const;
  const refresh = useCallback(async () => { try { setInteractions(await api.listProviderInteractions(session.token)); setError(""); } catch (reason) { if (!(reason instanceof ApiError) || reason.status !== 404) setError(reason instanceof ApiError ? reason.message : "Unable to load provider activity."); } }, [session.token]);
  useEffect(() => { refresh(); }, [refresh]);
  const closedKeys = new Set(interactions.filter((item) => item.interaction_type === "booking_completed" || item.interaction_type === "booking_cancelled").map((item) => `${item.request_id}:${item.provider_id}`));
  const offers = interactions.filter((item) => item.interaction_type === "booking_requested" && !closedKeys.has(`${item.request_id}:${item.provider_id}`));
  const bookings = interactions.filter((item) => item.interaction_type.startsWith("booking_"));
  const reviews = interactions.filter((item) => item.interaction_type === "rated");
  const handleBooking = async (item: Interaction, action: "complete" | "cancel") => { try { if (action === "complete") await api.completeBooking(item.interaction_id, session.token); else await api.cancelBooking(item.interaction_id, session.token); await refresh(); } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Unable to update booking."); } };
  const activityPage = section === "jobs" ? <InteractionPage title="Job Offers" subtitle="Customer booking requests waiting for your action." interactions={offers} empty="No pending job offers." renderAction={(item) => <div className="card-actions"><button className="small-action" onClick={() => handleBooking(item, "complete")}>Complete</button><button className="small-action secondary" onClick={() => handleBooking(item, "cancel")}>Decline</button></div>} /> : section === "bookings" ? <InteractionPage title="My Bookings" subtitle="Your complete booking activity." interactions={bookings} empty="No bookings yet." /> : section === "reviews" ? <InteractionPage title="Reviews & Ratings" subtitle="Ratings submitted by your customers." interactions={reviews} empty="No customer ratings yet." /> : <HistoryPage title="Provider Overview" subtitle="A live summary of your service activity." icon={<BarChart3 size={24} />} empty="Create your provider profile to start receiving work."><div className="metric-grid"><article><strong>{offers.length}</strong><span>Pending jobs</span></article><article><strong>{interactions.filter((item) => item.interaction_type === "booking_completed").length}</strong><span>Completed</span></article><article><strong>{reviews.length ? (reviews.reduce((total, item) => total + (item.rating ?? 0), 0) / reviews.length).toFixed(1) : "—"}</strong><span>Average rating</span></article></div></HistoryPage>;
  return <main className="workspace"><aside className="workspace-sidebar"><div><small>Provider workspace</small><h2>{session.user.full_name}</h2></div><nav>{items.map(([key, Icon, label]) => <button key={key} className={section === key ? "active" : ""} onClick={() => setSection(key)}><Icon size={17} />{label}</button>)}</nav></aside><div className="workspace-content">{section === "profile" ? <ProviderProfilePage session={session} /> : activityPage}{error && <div className="notice error request-error">{error}</div>}</div></main>;
}

function AdminDashboard({ session }: { session: Session }) {
  const [section, setSection] = useState("overview");
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [providers, setProviders] = useState<ProviderProfile[]>([]);
  const [requests, setRequests] = useState<ServiceRequest[]>([]);
  const [error, setError] = useState("");
  const items = [["overview", BarChart3, "Platform Overview"], ["users", CircleUserRound, "Manage Users"], ["providers", Wrench, "Manage Providers"], ["requests", ClipboardList, "Service Requests"]] as const;
  const refresh = useCallback(async () => { try { const [summary, userList, providerList, requestList] = await Promise.all([api.getAdminOverview(session.token), api.listAdminUsers(session.token), api.listAdminProviders(session.token), api.listAdminRequests(session.token)]); setOverview(summary); setUsers(userList); setProviders(providerList); setRequests(requestList); setError(""); } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Unable to load administration data."); } }, [session.token]);
  useEffect(() => { refresh(); }, [refresh]);
  const content = section === "users" ? <HistoryPage title="Manage Users" subtitle="Activate or suspend customer and provider accounts." icon={<CircleUserRound size={24} />} empty="No users found.">{users.map((user) => <HistoryCard key={user.user_id} title={user.full_name} meta={`${user.email} · ${user.role}`} status={user.is_active ? "active" : "suspended"} date={user.created_at} action={user.user_id !== session.user.user_id && <button className={`small-action ${user.is_active ? "secondary" : ""}`} onClick={async () => { await api.setUserActive(user.user_id, !user.is_active, session.token); await refresh(); }}>{user.is_active ? "Suspend" : "Activate"}</button>} />)}</HistoryPage> : section === "providers" ? <HistoryPage title="Manage Providers" subtitle="Registered service profiles visible to Component 1." icon={<Wrench size={24} />} empty="No provider profiles found.">{providers.map((provider) => <HistoryCard key={provider.provider_id} title={provider.provider_name} meta={`${provider.category} · ${provider.city}, ${provider.district}`} status={`${provider.rating.toFixed(1)} rating`} date={provider.created_at} />)}</HistoryPage> : section === "requests" ? <HistoryPage title="Service Requests" subtitle="Monitor customer demand across the platform." icon={<ClipboardList size={24} />} empty="No service requests found.">{requests.map((request) => <HistoryCard key={request.request_id} title={request.request_text} meta={`${request.category} · ${request.city}, ${request.district}`} status={request.urgency} date={request.created_at} />)}</HistoryPage> : <HistoryPage title="Platform Overview" subtitle="Live administrative monitoring across core platform records." icon={<ShieldCheck size={24} />} empty="No platform metrics available.">{overview && <div className="metric-grid admin-metrics"><article><strong>{overview.users}</strong><span>Users</span></article><article><strong>{overview.providers}</strong><span>Providers</span></article><article><strong>{overview.service_requests}</strong><span>Requests</span></article><article><strong>{overview.interactions}</strong><span>Interactions</span></article></div>}</HistoryPage>;
  return <main className="workspace"><aside className="workspace-sidebar admin"><div><small>Admin workspace</small><h2>{session.user.full_name}</h2></div><nav>{items.map(([key, Icon, label]) => <button key={key} className={section === key ? "active" : ""} onClick={() => setSection(key)}><Icon size={17} />{label}</button>)}</nav></aside><div className="workspace-content">{content}{error && <div className="notice error request-error">{error}</div>}</div></main>;
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
  function logout() {
    void api.logout().finally(() => {
      localStorage.removeItem(SESSION_KEY);
      setSession(null);
    });
  }

  if (checking) return <div className="app-loading"><Logo /><LoaderCircle className="spin" /></div>;
  return <div className="app-shell"><Header session={session} onLogout={logout} />{!session ? <AuthScreen onAuthenticated={authenticated} /> : session.user.role === "customer" ? <CustomerDashboard session={session} /> : session.user.role === "provider" ? <ProviderDashboard session={session} /> : <AdminDashboard session={session} />}</div>;
}
