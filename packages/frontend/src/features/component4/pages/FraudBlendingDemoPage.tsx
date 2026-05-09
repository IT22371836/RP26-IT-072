import { useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { SectionCard, StatCard } from "../../../common/components/ui";
import type { ProviderCredibility, ProviderRankEntry, ReviewCredibilityResponse } from "../types";
import { analyzeReviewCredibility, getProviderCredibility, rankProviders } from "../services/aspectAnalysisService";
import { DemoReviewPicker } from "../components/DemoReviewPicker";
import { TokenHighlighter } from "../components/TokenHighlighter";
import { AspectScorePanel } from "../components/AspectScorePanel";

type DemoSample = {
  id: string;
  label: string;
  text: string;
  rating?: number;
  user_total_reviews?: number;
  days_since_prev_review?: number;
  user_provider_diversity?: number;
};

const DEMO_SAMPLES: DemoSample[] = [
  {
    id: "verified",
    label: "Verified-looking",
    text: "Excellent service , very professional and the price was fair .",
    rating: 5,
    user_total_reviews: 12,
    days_since_prev_review: 18,
    user_provider_diversity: 4,
  },
  {
    id: "suspicious",
    label: "Suspicious burst",
    text: "Amazing amazing amazing !!! BEST SERVICE EVER !!!",
    rating: 5,
    user_total_reviews: 28,
    days_since_prev_review: 1,
    user_provider_diversity: 1,
  },
  {
    id: "mixed",
    label: "Mixed feedback",
    text: "Fixed the gas leak perfectly but arrived two hours late without calling .",
    rating: 3,
    user_total_reviews: 6,
    days_since_prev_review: 32,
    user_provider_diversity: 2,
  },
];

const SAMPLE_PROVIDERS = ["P1", "P10", "P10174", "P10239", "P1003"];

const TRUST_COLORS: Record<string, string> = {
  Verified: "#16a34a",
  Unverified: "#d97706",
  Suspicious: "#dc2626",
};

const TRUST_BG: Record<string, string> = {
  Verified: "#ecfdf3",
  Unverified: "#fff7ed",
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

function ProviderMiniCard({ data }: { data: ProviderCredibility }) {
  return (
    <div style={styles.providerCard}>
      <div style={styles.providerHeader}>
        <span style={styles.providerId}>{data.provider_id}</span>
        <span style={styles.providerTier}>{data.tier}</span>
      </div>
      <div style={styles.providerScoreRow}>
        <span style={styles.providerScoreLabel}>S_final</span>
        <span style={styles.providerScoreValue}>{data.S_final.toFixed(3)}</span>
      </div>
      <div style={styles.providerMeta}>
        <span>Fraud ratio: {data.fraud_ratio != null ? (data.fraud_ratio * 100).toFixed(1) + "%" : "-"}</span>
        <span>Avg rating: {data.avg_rating != null ? data.avg_rating.toFixed(2) + " ★" : "-"}</span>
        <span>Total reviews: {data.total_reviews ?? "-"}</span>
      </div>
    </div>
  );
}

export function FraudBlendingDemoPage() {
  const [text, setText] = useState("");
  const [selectedSample, setSelectedSample] = useState<DemoSample | null>(null);
  const [result, setResult] = useState<ReviewCredibilityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [providerLookupId, setProviderLookupId] = useState("");
  const [providerResult, setProviderResult] = useState<ProviderCredibility | null>(null);
  const [providerLoading, setProviderLoading] = useState(false);
  const [providerError, setProviderError] = useState<string | null>(null);

  const [rankResult, setRankResult] = useState<ProviderRankEntry[] | null>(null);
  const [rankLoading, setRankLoading] = useState(false);
  const [rankError, setRankError] = useState<string | null>(null);

  const demoIds = useMemo(() => SAMPLE_PROVIDERS.join(", "), []);

  async function handleAnalyze(payload: DemoSample) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeReviewCredibility(payload.text, {
        rating: payload.rating,
        user_total_reviews: payload.user_total_reviews,
        days_since_prev_review: payload.days_since_prev_review,
        user_provider_diversity: payload.user_provider_diversity,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  function handleSampleSelect(reviewText: string) {
    const sample = DEMO_SAMPLES.find((item) => item.text === reviewText) ?? null;
    setText(reviewText);
    setSelectedSample(sample);
    void handleAnalyze(sample ?? { id: "demo", label: "Demo", text: reviewText });
  }

  async function handleManualAnalyze(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    await handleAnalyze({
      id: "manual",
      label: "Manual entry",
      text: trimmed,
      rating: selectedSample?.rating ?? 4,
      user_total_reviews: selectedSample?.user_total_reviews ?? 5,
      days_since_prev_review: selectedSample?.days_since_prev_review ?? 30,
      user_provider_diversity: selectedSample?.user_provider_diversity ?? 3,
    });
  }

  async function handleProviderLookup(e: React.FormEvent) {
    e.preventDefault();
    const id = providerLookupId.trim();
    if (!id) return;
    setProviderLoading(true);
    setProviderError(null);
    setProviderResult(null);
    try {
      const data = await getProviderCredibility(id.toUpperCase());
      setProviderResult(data);
    } catch (err) {
      setProviderError(err instanceof Error ? err.message : "Lookup failed.");
    } finally {
      setProviderLoading(false);
    }
  }

  async function handleRankSamples() {
    setRankLoading(true);
    setRankError(null);
    setRankResult(null);
    try {
      const data = await rankProviders(SAMPLE_PROVIDERS);
      setRankResult(data.ranked);
    } catch (err) {
      setRankError(err instanceof Error ? err.message : "Ranking failed.");
    } finally {
      setRankLoading(false);
    }
  }

  const trustColor = result ? TRUST_COLORS[result.trust_label] ?? "#334155" : "#334155";
  const trustBg = result ? TRUST_BG[result.trust_label] ?? "#f8fafc" : "#f8fafc";
  const trustBorder = result ? TRUST_BORDER[result.trust_label] ?? "#e2e8f0" : "#e2e8f0";

  return (
    <div style={styles.page}>
      <div style={styles.hero}>
        <div>
          <p style={styles.eyebrow}>Component 4</p>
          <h2 style={styles.title}>Fraud Detection + Credibility Blending</h2>
          <p style={styles.subtitle}>
            Quick sandbox to validate the Isolation Forest fraud score and the blended S_final provider credibility.
          </p>
        </div>
        <div style={styles.statRow}>
          <StatCard label="Fraud model" value="Isolation Forest" note="13 features · 120k reviews" />
          <StatCard label="Blending" value="S_final" note="40% cred · 35% overall · 15% fraud · 10% recency" />
          <StatCard label="Sample providers" value="5" note={demoIds} />
        </div>
      </div>

      <div style={styles.grid}>
        <SectionCard title="Review Credibility (demo samples)">
          <div style={styles.sampleBlock}>
            <div>
              <DemoReviewPicker selected={text} onSelect={handleSampleSelect} />
              <p style={styles.sampleHint}>Tap a sample to run the credibility analysis instantly.</p>
            </div>
            <div style={styles.sampleMeta}>
              <div style={styles.sampleMetaCard}>
                <span style={styles.metaLabel}>Selected scenario</span>
                <strong style={styles.metaValue}>{selectedSample?.label ?? "None"}</strong>
              </div>
              <div style={styles.sampleMetaCard}>
                <span style={styles.metaLabel}>Rating</span>
                <strong style={styles.metaValue}>{selectedSample?.rating ?? "-"}</strong>
              </div>
              <div style={styles.sampleMetaCard}>
                <span style={styles.metaLabel}>User reviews</span>
                <strong style={styles.metaValue}>{selectedSample?.user_total_reviews ?? "-"}</strong>
              </div>
              <div style={styles.sampleMetaCard}>
                <span style={styles.metaLabel}>Days since prev</span>
                <strong style={styles.metaValue}>{selectedSample?.days_since_prev_review ?? "-"}</strong>
              </div>
            </div>
          </div>

          <form onSubmit={handleManualAnalyze} style={styles.manualForm}>
            <textarea
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setSelectedSample(null);
              }}
              placeholder="Or type your own review text here..."
              rows={3}
              style={styles.textarea}
            />
            <button type="submit" style={styles.btn} disabled={loading || text.trim().length === 0}>
              {loading ? "Analysing..." : "Analyse"}
            </button>
          </form>

          {loading && <p style={styles.loadingText}>Running ALSA + fraud scoring...</p>}
          {error && <div style={styles.errorBox}><strong>Error:</strong> {error}</div>}

          {result && !loading && (
            <div style={{ marginTop: "16px" }}>
              <div style={{ ...styles.trustBadge, backgroundColor: trustBg, borderColor: trustBorder }}>
                <span style={{ ...styles.trustLabel, color: trustColor }}>{result.trust_label}</span>
                <div style={styles.fraudRow}>
                  <span style={styles.fraudTitle}>Fraud Score</span>
                  <FraudScoreBar score={result.fraud_score} />
                </div>
              </div>
              <div style={{ marginTop: "16px" }}>
                <TokenHighlighter tokens={result.tokens} />
                <div style={{ marginTop: "12px" }}>
                  <AspectScorePanel aspects={result.aspects} />
                </div>
              </div>
            </div>
          )}
        </SectionCard>

        <SectionCard title="Provider Credibility (quick checks)">
          <form onSubmit={handleProviderLookup} style={styles.lookupRow}>
            <input
              type="text"
              value={providerLookupId}
              onChange={(e) => setProviderLookupId(e.target.value)}
              placeholder="Try P1, P10, P10174"
              style={styles.input}
            />
            <button type="submit" style={styles.btn} disabled={providerLoading || !providerLookupId.trim()}>
              {providerLoading ? "Looking..." : "Look up"}
            </button>
          </form>

          <div style={styles.sampleProviders}>
            {SAMPLE_PROVIDERS.map((id) => (
              <button
                key={id}
                type="button"
                style={styles.sampleChip}
                onClick={() => {
                  setProviderLookupId(id);
                  setProviderLoading(true);
                  setProviderError(null);
                  setProviderResult(null);
                  void getProviderCredibility(id)
                    .then(setProviderResult)
                    .catch((err) => {
                      setProviderError(err instanceof Error ? err.message : "Lookup failed.");
                    })
                    .finally(() => setProviderLoading(false));
                }}
              >
                {id}
              </button>
            ))}
          </div>

          {providerError && <div style={styles.errorBox}><strong>Error:</strong> {providerError}</div>}
          {providerResult && !providerLoading && (
            <div style={{ marginTop: "14px" }}>
              <ProviderMiniCard data={providerResult} />
            </div>
          )}

          <div style={styles.rankBlock}>
            <div>
              <h4 style={styles.rankTitle}>Rank the sample set</h4>
              <p style={styles.rankHint}>Uses provider IDs: {demoIds}</p>
            </div>
            <button type="button" style={styles.btnSecondary} onClick={() => void handleRankSamples()}>
              {rankLoading ? "Ranking..." : "Rank Samples"}
            </button>
          </div>

          {rankError && <div style={styles.errorBox}><strong>Error:</strong> {rankError}</div>}
          {rankResult && !rankLoading && (
            <div style={styles.rankTable}>
              <div style={styles.rankHeader}>
                {"Rank | Provider | S_final | Tier".split(" | ").map((label) => (
                  <span key={label} style={styles.rankHeaderCell}>{label}</span>
                ))}
              </div>
              {rankResult.map((entry) => (
                <div key={entry.provider_id} style={styles.rankRow}>
                  <span style={styles.rankCell}>#{entry.rank}</span>
                  <span style={{ ...styles.rankCell, fontWeight: 600 }}>{entry.provider_id}</span>
                  <span style={styles.rankCell}>{entry.S_final != null ? entry.S_final.toFixed(3) : "-"}</span>
                  <span style={styles.rankCell}>{entry.tier}</span>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    display: "grid",
    gap: "16px",
    fontFamily: "'Space Grotesk', sans-serif",
  },
  hero: {
    display: "grid",
    gap: "12px",
    padding: "18px",
    borderRadius: "16px",
    background:
      "radial-gradient(circle at top left, rgba(14, 116, 144, 0.18), transparent 55%), radial-gradient(circle at 20% 20%, rgba(16, 185, 129, 0.2), transparent 50%), #ffffff",
    border: "1px solid #e2e8f0",
  },
  eyebrow: { textTransform: "uppercase", letterSpacing: "0.28em", fontSize: "11px", color: "#0f766e" },
  title: { margin: 0, color: "#0f172a", fontSize: "24px" },
  subtitle: { margin: 0, color: "#475569", fontSize: "14px" },
  statRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "10px",
  },
  grid: { display: "grid", gap: "16px" },
  sampleBlock: { display: "grid", gap: "16px" },
  sampleHint: { fontSize: "12px", color: "#64748b", marginTop: "8px" },
  sampleMeta: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: "8px",
  },
  sampleMetaCard: {
    padding: "10px 12px",
    borderRadius: "10px",
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    display: "grid",
    gap: "4px",
  },
  metaLabel: { fontSize: "11px", color: "#64748b", textTransform: "uppercase" },
  metaValue: { fontSize: "14px", color: "#0f172a" },
  loadingText: { fontSize: "13px", color: "#0f766e", marginTop: "12px" },
  trustBadge: {
    padding: "14px",
    borderRadius: "12px",
    border: "1px solid",
    display: "grid",
    gap: "10px",
  },
  trustLabel: { fontSize: "16px", fontWeight: 700 },
  fraudRow: { display: "grid", gap: "6px" },
  fraudTitle: { fontSize: "12px", color: "#64748b" },
  scoreBarWrap: { display: "flex", alignItems: "center", gap: "8px" },
  scoreBarTrack: {
    flex: 1,
    height: "8px",
    backgroundColor: "#e2e8f0",
    borderRadius: "999px",
    overflow: "hidden",
  },
  scoreBarFill: { height: "100%", borderRadius: "999px" },
  scoreBarLabel: { fontSize: "12px", fontWeight: 700, minWidth: "36px" },
  lookupRow: { display: "flex", gap: "10px", alignItems: "center" },
  manualForm: { marginTop: "14px", display: "grid", gap: "10px" },
  textarea: {
    width: "100%",
    padding: "12px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    color: "#0f172a",
    resize: "vertical",
    lineHeight: "1.5",
  },
  input: {
    flex: 1,
    padding: "10px 14px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    color: "#0f172a",
  },
  btn: {
    padding: "10px 18px",
    borderRadius: "10px",
    border: "none",
    backgroundColor: "#0f766e",
    color: "#ffffff",
    fontWeight: 600,
  },
  btnSecondary: {
    padding: "10px 18px",
    borderRadius: "10px",
    border: "1px solid #0f766e",
    backgroundColor: "transparent",
    color: "#0f766e",
    fontWeight: 600,
  },
  errorBox: {
    marginTop: "12px",
    padding: "10px 12px",
    borderRadius: "10px",
    backgroundColor: "#fef2f2",
    border: "1px solid #fecaca",
    color: "#991b1b",
    fontSize: "13px",
  },
  sampleProviders: { display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "12px" },
  sampleChip: {
    padding: "6px 12px",
    borderRadius: "999px",
    border: "1px solid #cbd5e1",
    backgroundColor: "#ffffff",
    color: "#0f172a",
    fontSize: "12px",
    fontWeight: 600,
  },
  providerCard: {
    padding: "14px",
    borderRadius: "12px",
    border: "1px solid #e2e8f0",
    backgroundColor: "#f8fafc",
    display: "grid",
    gap: "10px",
  },
  providerHeader: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  providerId: { fontSize: "16px", fontWeight: 700, color: "#0f172a" },
  providerTier: {
    fontSize: "11px",
    padding: "3px 10px",
    borderRadius: "999px",
    backgroundColor: "#ecfeff",
    color: "#0e7490",
    fontWeight: 700,
  },
  providerScoreRow: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  providerScoreLabel: { fontSize: "12px", color: "#64748b" },
  providerScoreValue: { fontSize: "18px", fontWeight: 700, color: "#0f172a" },
  providerMeta: { display: "grid", gap: "4px", fontSize: "12px", color: "#475569" },
  rankBlock: {
    marginTop: "16px",
    padding: "12px",
    borderRadius: "12px",
    backgroundColor: "#f1f5f9",
    border: "1px solid #e2e8f0",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
  },
  rankTitle: { margin: 0, fontSize: "14px", color: "#0f172a" },
  rankHint: { margin: "4px 0 0", fontSize: "12px", color: "#64748b" },
  rankTable: { marginTop: "12px", display: "grid", gap: "6px" },
  rankHeader: {
    display: "grid",
    gridTemplateColumns: "60px 1fr 90px 90px",
    padding: "8px 10px",
    backgroundColor: "#f1f5f9",
    borderRadius: "10px",
    fontSize: "12px",
    color: "#64748b",
  },
  rankHeaderCell: { textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.08em" },
  rankRow: {
    display: "grid",
    gridTemplateColumns: "60px 1fr 90px 90px",
    padding: "8px 10px",
    backgroundColor: "#ffffff",
    borderRadius: "10px",
    border: "1px solid #e2e8f0",
    fontSize: "13px",
  },
  rankCell: { color: "#0f172a" },
};
