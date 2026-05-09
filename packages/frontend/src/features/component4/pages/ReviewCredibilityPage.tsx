import { useState } from "react";
import type { CSSProperties } from "react";
import { SectionCard, StatCard } from "../../../common/components/ui";
import type { ReviewCredibilityResponse } from "../types";
import { analyzeReviewCredibility } from "../services/aspectAnalysisService";
import { DemoReviewPicker } from "../components/DemoReviewPicker";
import { TokenHighlighter } from "../components/TokenHighlighter";
import { AspectScorePanel } from "../components/AspectScorePanel";

type DemoSample = {
  text: string;
  label: string;
  rating: string;
  userTotalReviews: string;
  daysSincePrev: string;
  providerDiversity: string;
};

const DEMO_SAMPLES: DemoSample[] = [
  {
    label: "Verified-looking",
    text: "Excellent service , very professional and the price was fair .",
    rating: "5",
    userTotalReviews: "12",
    daysSincePrev: "18",
    providerDiversity: "4",
  },
  {
    label: "Suspicious burst",
    text: "Amazing amazing amazing !!! BEST SERVICE EVER !!!",
    rating: "5",
    userTotalReviews: "28",
    daysSincePrev: "1",
    providerDiversity: "1",
  },
  {
    label: "Mixed feedback",
    text: "Fixed the gas leak perfectly but arrived two hours late without calling .",
    rating: "3",
    userTotalReviews: "6",
    daysSincePrev: "32",
    providerDiversity: "2",
  },
  {
    label: "Negative quality",
    text: "Not satisfied with the repair quality , the AC stopped working again .",
    rating: "2",
    userTotalReviews: "4",
    daysSincePrev: "45",
    providerDiversity: "3",
  },
  {
    label: "Communication focus",
    text: "Very professional attitude , explained everything clearly before starting .",
    rating: "5",
    userTotalReviews: "8",
    daysSincePrev: "22",
    providerDiversity: "5",
  },
];

const TRUST_COLORS: Record<string, string> = {
  Verified: "#16a34a",
  Unverified: "#d97706",
  Suspicious: "#dc2626",
};

const TRUST_BG: Record<string, string> = {
  Verified: "#f0fdf4",
  Unverified: "#fffbeb",
  Suspicious: "#fef2f2",
};

const TRUST_BORDER: Record<string, string> = {
  Verified: "#bbf7d0",
  Unverified: "#fed7aa",
  Suspicious: "#fecaca",
};

function FraudScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score < 0.35 ? "#16a34a" : score < 0.6 ? "#d97706" : "#dc2626";
  return (
    <div style={styles.scoreBarWrap}>
      <div style={styles.scoreBarTrack}>
        <div style={{ ...styles.scoreBarFill, width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span style={{ ...styles.scoreBarLabel, color }}>{pct}%</span>
    </div>
  );
}

function LinguisticsTable({ features }: { features: ReviewCredibilityResponse["linguistic_features"] }) {
  const rows: [string, string | number][] = [
    ["Word count", features.word_count],
    ["Unique word ratio", (features.unique_word_ratio * 100).toFixed(1) + "%"],
    ["Pronoun count", features.pronoun_count],
    ["Adjective density", (features.adj_density * 100).toFixed(1) + "%"],
    ["Exclamation marks", features.exclamation_count],
    ["Caps ratio", (features.caps_ratio * 100).toFixed(1) + "%"],
    ["Rating–text mismatch", features.rating_text_mismatch.toFixed(3)],
  ];
  return (
    <table style={styles.table}>
      <tbody>
        {rows.map(([label, val]) => (
          <tr key={label}>
            <td style={styles.tdLabel}>{label}</td>
            <td style={styles.tdVal}>{val}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ReviewCredibilityPage() {
  const [text, setText] = useState("");
  const [rating, setRating] = useState<string>("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [userTotalReviews, setUserTotalReviews] = useState("5");
  const [daysSincePrev, setDaysSincePrev] = useState("30");
  const [providerDiversity, setProviderDiversity] = useState("3");
  const [daysSinceReview, setDaysSinceReview] = useState("30");
  const [bookingStatus, setBookingStatus] = useState<1 | 0>(1);
  const [result, setResult] = useState<ReviewCredibilityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    const trimmed = text.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const behavioral = {
        rating: rating ? parseFloat(rating) : undefined,
        user_total_reviews: parseInt(userTotalReviews, 10) || 5,
        days_since_prev_review: parseFloat(daysSincePrev) || 30,
        user_provider_diversity: parseFloat(providerDiversity) || 3,
        days_since_review: parseFloat(daysSinceReview) || 30,
        booking_status: bookingStatus,
      };
      const data = await analyzeReviewCredibility(trimmed, behavioral);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  function handleDemoSelect(reviewText: string) {
    const sample = DEMO_SAMPLES.find((s) => s.text === reviewText);
    setText(reviewText);
    if (sample) {
      setRating(sample.rating);
      setUserTotalReviews(sample.userTotalReviews);
      setDaysSincePrev(sample.daysSincePrev);
      setProviderDiversity(sample.providerDiversity);
    }
    setLoading(true);
    setError(null);
    setResult(null);
    const behavioral = sample
      ? {
          rating: parseFloat(sample.rating),
          user_total_reviews: parseInt(sample.userTotalReviews, 10),
          days_since_prev_review: parseFloat(sample.daysSincePrev),
          user_provider_diversity: parseFloat(sample.providerDiversity),
          days_since_review: parseFloat(daysSinceReview) || 30,
          booking_status: bookingStatus,
        }
      : undefined;
    analyzeReviewCredibility(reviewText.trim(), behavioral)
      .then(setResult)
      .catch((e) => setError(e instanceof Error ? e.message : "An unexpected error occurred."))
      .finally(() => setLoading(false));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void handleAnalyze();
  }

  const trustColor = result ? TRUST_COLORS[result.trust_label] ?? "#64748b" : "#64748b";
  const trustBg = result ? TRUST_BG[result.trust_label] ?? "#f8fafc" : "#f8fafc";
  const trustBorder = result ? TRUST_BORDER[result.trust_label] ?? "#e2e8f0" : "#e2e8f0";

  return (
    <div style={styles.page}>
      <div>
        <h2 style={styles.title}>Review Credibility Analyser</h2>
        <p style={styles.subtitle}>
          Combines BiLSTM-CRF aspect extraction with Isolation Forest fraud detection to assess review authenticity.
        </p>
      </div>

      <div style={styles.stats}>
        <StatCard label="Fraud Model"    value="IF"    note="Isolation Forest · 120k reviews" />
        <StatCard label="Features"       value="13"    note="7 linguistic · 6 behavioral" />
        <StatCard label="Aspects"        value="4"     note="QUAL · PRICE · TIME · COMM" />
      </div>

      <SectionCard title="Try a Sample Review">
        <DemoReviewPicker selected={text} onSelect={handleDemoSelect} />
        <p style={{ margin: "10px 0 0", fontSize: "12px", color: "#64748b" }}>
          Each sample preloads matching behavioral metadata (rating, review frequency, days since last review).
        </p>
      </SectionCard>

      <SectionCard title="Analyse a Review">
        <form onSubmit={handleSubmit} style={styles.form}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste a service review to assess its credibility…"
            style={styles.textarea}
            rows={4}
          />

          <div style={styles.ratingRow}>
            <label style={styles.label}>Star rating (optional)</label>
            <select
              value={rating}
              onChange={(e) => setRating(e.target.value)}
              style={styles.select}
            >
              <option value="">-- not provided --</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{n} ★</option>
              ))}
            </select>
          </div>

          <button
            type="button"
            style={styles.advancedToggle}
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? "▲ Hide" : "▼ Show"} behavioral features
          </button>

          {showAdvanced && (
            <div style={styles.advancedGrid}>
              {[
                { label: "User's total reviews", value: userTotalReviews, setter: setUserTotalReviews },
                { label: "Days since previous review", value: daysSincePrev, setter: setDaysSincePrev },
                { label: "Provider diversity (# unique)", value: providerDiversity, setter: setProviderDiversity },
                { label: "Days since this review was posted", value: daysSinceReview, setter: setDaysSinceReview },
              ].map(({ label, value, setter }) => (
                <label key={label} style={styles.advancedLabel}>
                  {label}
                  <input
                    type="number"
                    value={value}
                    min={0}
                    onChange={(e) => setter(e.target.value)}
                    style={styles.input}
                  />
                </label>
              ))}
              <label style={styles.advancedLabel}>
                Booking verified
                <div style={styles.toggleRow}>
                  {([1, 0] as const).map((val) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => setBookingStatus(val)}
                      style={{
                        ...styles.toggleBtn,
                        backgroundColor: bookingStatus === val ? "#0f766e" : "#ffffff",
                        color: bookingStatus === val ? "#ffffff" : "#475569",
                        borderColor: bookingStatus === val ? "#0f766e" : "#cbd5e1",
                      }}
                    >
                      {val === 1 ? "Yes (confirmed)" : "No (unverified)"}
                    </button>
                  ))}
                </div>
              </label>
            </div>
          )}

          <div style={styles.formFooter}>
            <span style={styles.charHint}>{text.length} characters</span>
            <button
              type="submit"
              disabled={loading || text.trim().length === 0}
              style={{
                ...styles.btn,
                opacity: loading || text.trim().length === 0 ? 0.5 : 1,
                cursor: loading || text.trim().length === 0 ? "not-allowed" : "pointer",
              }}
            >
              {loading ? "Analysing…" : "Analyse Credibility"}
            </button>
          </div>
        </form>
      </SectionCard>

      {loading && (
        <div style={styles.spinnerWrap}>
          <div style={styles.spinner} />
          <span style={styles.spinnerText}>Running ALSA + Fraud Detection…</span>
        </div>
      )}

      {error && (
        <div style={styles.errorBox}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {result && !loading && (
        <>
          <SectionCard title="Credibility Verdict">
            <div style={{ ...styles.trustBadge, backgroundColor: trustBg, borderColor: trustBorder }}>
              <span style={{ ...styles.trustLabel, color: trustColor }}>
                {result.trust_label}
              </span>
              <div style={styles.fraudRow}>
                <span style={styles.fraudTitle}>Fraud Score</span>
                <FraudScoreBar score={result.fraud_score} />
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Aspect Analysis">
            <TokenHighlighter tokens={result.tokens} />
            <div style={{ marginTop: "12px" }}>
              <AspectScorePanel aspects={result.aspects} />
            </div>
          </SectionCard>

          <SectionCard title="Linguistic Feature Breakdown">
            <LinguisticsTable features={result.linguistic_features} />
          </SectionCard>
        </>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: { display: "grid", gap: "16px" },
  title: { margin: 0, color: "#0f172a" },
  subtitle: { margin: "5px 0 0", color: "#475569", fontSize: "14px" },
  stats: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "10px",
  },
  form: { display: "flex", flexDirection: "column", gap: "10px" },
  textarea: {
    width: "100%",
    padding: "12px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    color: "#0f172a",
    resize: "vertical",
    fontFamily: "inherit",
    lineHeight: "1.5",
    outline: "none",
  },
  ratingRow: { display: "flex", alignItems: "center", gap: "12px" },
  label: { fontSize: "13px", color: "#475569", whiteSpace: "nowrap" },
  select: {
    padding: "6px 10px",
    borderRadius: "8px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    color: "#0f172a",
    backgroundColor: "#fff",
  },
  advancedToggle: {
    alignSelf: "flex-start",
    background: "none",
    border: "none",
    color: "#0f766e",
    fontSize: "13px",
    cursor: "pointer",
    padding: "2px 0",
  },
  advancedGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "10px",
    padding: "12px",
    backgroundColor: "#f8fafc",
    borderRadius: "10px",
    border: "1px solid #e2e8f0",
  },
  advancedLabel: {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    fontSize: "13px",
    color: "#475569",
  },
  toggleRow: {
    display: "flex",
    gap: "6px",
    marginTop: "2px",
  },
  toggleBtn: {
    flex: 1,
    padding: "6px 8px",
    borderRadius: "8px",
    border: "1px solid",
    fontSize: "12px",
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 120ms ease",
  },
  input: {
    padding: "6px 10px",
    borderRadius: "8px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    color: "#0f172a",
    outline: "none",
  },
  formFooter: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  charHint: { fontSize: "12px", color: "#94a3b8" },
  btn: {
    padding: "10px 24px",
    borderRadius: "10px",
    border: "none",
    backgroundColor: "#0f766e",
    color: "#ffffff",
    fontSize: "14px",
    fontWeight: 600,
    transition: "opacity 150ms ease",
  },
  spinnerWrap: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "16px",
    backgroundColor: "#f8fafc",
    borderRadius: "10px",
    border: "1px solid #e2e8f0",
  },
  spinner: {
    width: "20px",
    height: "20px",
    borderRadius: "50%",
    border: "3px solid #e2e8f0",
    borderTopColor: "#0f766e",
    animation: "spin 0.8s linear infinite",
  },
  spinnerText: { fontSize: "14px", color: "#475569" },
  errorBox: {
    padding: "12px 16px",
    borderRadius: "10px",
    backgroundColor: "#fef2f2",
    border: "1px solid #fecaca",
    color: "#991b1b",
    fontSize: "14px",
  },
  trustBadge: {
    padding: "16px 20px",
    borderRadius: "10px",
    border: "1px solid",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  trustLabel: {
    fontSize: "20px",
    fontWeight: 700,
  },
  fraudRow: { display: "flex", alignItems: "center", gap: "12px" },
  fraudTitle: { fontSize: "13px", color: "#475569", whiteSpace: "nowrap", minWidth: "80px" },
  scoreBarWrap: { display: "flex", alignItems: "center", gap: "8px", flex: 1 },
  scoreBarTrack: {
    flex: 1,
    height: "8px",
    backgroundColor: "#e2e8f0",
    borderRadius: "4px",
    overflow: "hidden",
  },
  scoreBarFill: { height: "100%", borderRadius: "4px", transition: "width 400ms ease" },
  scoreBarLabel: { fontSize: "13px", fontWeight: 600, minWidth: "36px", textAlign: "right" },
  table: { width: "100%", borderCollapse: "collapse" },
  tdLabel: {
    padding: "7px 12px 7px 0",
    fontSize: "13px",
    color: "#475569",
    borderBottom: "1px solid #f1f5f9",
    width: "55%",
  },
  tdVal: {
    padding: "7px 0",
    fontSize: "13px",
    fontWeight: 600,
    color: "#0f172a",
    borderBottom: "1px solid #f1f5f9",
  },
};
