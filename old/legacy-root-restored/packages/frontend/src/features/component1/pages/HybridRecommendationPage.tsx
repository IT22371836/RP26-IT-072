import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import { SectionCard, StatCard } from "../../../common/components/ui";
import { RecommendationCard } from "../components/RecommendationCard";
import type { Component1Status, RecommendResponse } from "../types";
import { getComponent1Status, recommendProviders } from "../services/recommendationService";

const SAMPLE_QUERIES = [
  "AC repair",
  "plumbing emergency",
  "solar panel fixing",
  "interior painting",
  "web development",
];

export function HybridRecommendationPage() {
  const [status, setStatus] = useState<Component1Status | null>(null);
  const [query, setQuery] = useState("");
  const [userId, setUserId] = useState(1);
  const [topK, setTopK] = useState(5);
  const [minRating, setMinRating] = useState(0);
  const [maxPrice, setMaxPrice] = useState<number | "">("");
  const [location, setLocation] = useState("");
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getComponent1Status()
      .then((data) => {
        if (active) {
          setStatus(data);
        }
      })
      .catch(() => {
        if (active) {
          setStatus(null);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const weightsLabel = useMemo(() => {
    if (!status?.weights) return "-";
    return `TF-IDF ${status.weights.tfidf ?? 0} | BERT ${status.weights.bert ?? 0} | CF ${status.weights.cf ?? 0}`;
  }, [status]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const payload = {
        query: trimmed,
        user_id: Number(userId),
        top_k: Number(topK),
        min_rating: Number(minRating),
        max_price: maxPrice === "" ? null : Number(maxPrice),
        location: location.trim() ? location.trim() : null,
      };

      const data = await recommendProviders(payload);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to fetch recommendations.");
    } finally {
      setLoading(false);
    }
  }

  function applySample(sample: string) {
    setQuery(sample);
  }

  return (
    <div style={styles.page}>
      <section style={styles.hero} className="component1-hero">
        <div>
          <p style={styles.kicker}>Component 1 - Hybrid Recommender</p>
          <h2 style={styles.title}>Provider ranking with signal blending</h2>
          <p style={styles.subtitle}>
            Blend TF-IDF keywords, BERT semantics, and collaborative signals to deliver top providers fast.
          </p>
          <div style={styles.badges}>
            <span style={styles.badge}>100k providers ready</span>
            <span style={styles.badge}>Weights: {weightsLabel}</span>
          </div>
        </div>
        <div style={styles.heroPanel}>
          <div style={styles.heroStat}>
            <p style={styles.heroStatLabel}>Status</p>
            <p style={styles.heroStatValue}>{status?.recommender_loaded ? "Loaded" : "Warming"}</p>
          </div>
          <div style={styles.heroStat}>
            <p style={styles.heroStatLabel}>Providers</p>
            <p style={styles.heroStatValue}>{status?.total_providers ?? "-"}</p>
          </div>
          <div style={styles.heroStat}>
            <p style={styles.heroStatLabel}>Last check</p>
            <p style={styles.heroStatValue}>{status?.timestamp ? status.timestamp.slice(11, 19) : "-"}</p>
          </div>
        </div>
        <div className="component1-orb component1-orb--one" />
        <div className="component1-orb component1-orb--two" />
      </section>

      <div style={styles.stats}>
        <StatCard label="Hybrid weights" value="0.30 / 0.35 / 0.35" note="TF-IDF / BERT / CF" />
        <StatCard label="Max results" value="100" note="Per request" />
        <StatCard label="Confidence bands" value="Score 0-1" note="Normalized" />
        <StatCard label="Latency target" value="< 250ms" note="Warm cache" />
      </div>

      <SectionCard title="Recommendation request" actionText="POST /api/v1/component1/recommend">
        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.formRow}>
            <label style={styles.label}>
              Search query
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="e.g. emergency plumbing in Colombo"
                style={styles.input}
              />
            </label>
            <label style={styles.label}>
              Location
              <input
                value={location}
                onChange={(event) => setLocation(event.target.value)}
                placeholder="Optional"
                style={styles.input}
              />
            </label>
          </div>

          <div style={styles.formRow}>
            <label style={styles.labelSmall}>
              User ID
              <input
                type="number"
                value={userId}
                onChange={(event) => setUserId(Number(event.target.value))}
                style={styles.inputSmall}
              />
            </label>
            <label style={styles.labelSmall}>
              Top K
              <input
                type="number"
                min={1}
                max={100}
                value={topK}
                onChange={(event) => setTopK(Number(event.target.value))}
                style={styles.inputSmall}
              />
            </label>
            <label style={styles.labelSmall}>
              Min rating
              <input
                type="number"
                min={0}
                max={5}
                step={0.1}
                value={minRating}
                onChange={(event) => setMinRating(Number(event.target.value))}
                style={styles.inputSmall}
              />
            </label>
            <label style={styles.labelSmall}>
              Max price (LKR)
              <input
                type="number"
                min={0}
                value={maxPrice}
                onChange={(event) => setMaxPrice(event.target.value ? Number(event.target.value) : "")}
                style={styles.inputSmall}
              />
            </label>
          </div>

          <div style={styles.sampleRow}>
            {SAMPLE_QUERIES.map((sample) => (
              <button
                type="button"
                key={sample}
                onClick={() => applySample(sample)}
                style={styles.sampleChip}
              >
                {sample}
              </button>
            ))}
          </div>

          <div style={styles.formFooter}>
            <span style={styles.helperText}>Tip: choose a user id that exists in the interaction data.</span>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              style={{
                ...styles.primaryButton,
                opacity: loading || !query.trim() ? 0.5 : 1,
                cursor: loading || !query.trim() ? "not-allowed" : "pointer",
              }}
            >
              {loading ? "Scoring..." : "Get recommendations"}
            </button>
          </div>
        </form>
      </SectionCard>

      {loading && (
        <div style={styles.loadingBox}>
          <div style={styles.loadingDot} />
          <span>Running TF-IDF, BERT, and CF blending...</span>
        </div>
      )}

      {error && (
        <div style={styles.errorBox}>
          <strong>Error:</strong> {error}
        </div>
      )}

      <SectionCard title="Ranked providers" actionText={result ? `${result.total_results} results` : "Waiting"}>
        {result ? (
          <div style={styles.resultsGrid}>
            {result.recommendations.map((item) => (
              <RecommendationCard key={`${item.provider_id}-${item.rank}`} item={item} />
            ))}
          </div>
        ) : (
          <div style={styles.emptyState}>
            <p style={styles.emptyTitle}>No recommendations yet</p>
            <p style={styles.emptyText}>Submit a query to see the ranked provider list.</p>
          </div>
        )}
      </SectionCard>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    display: "grid",
    gap: "18px",
    fontFamily: "\"Space Grotesk\", \"Sora\", sans-serif",
    color: "#0f172a",
  },
  hero: {
    position: "relative",
    overflow: "hidden",
    borderRadius: "24px",
    padding: "24px",
    border: "1px solid #f2e8d5",
    background:
      "radial-gradient(circle at 10% 10%, #fef3c7 0%, transparent 45%), radial-gradient(circle at 80% 0%, #a7f3d0 0%, transparent 40%), linear-gradient(135deg, #fffaf0 0%, #fef9c3 45%, #ecfeff 100%)",
    boxShadow: "0 16px 35px rgba(15, 23, 42, 0.12)",
    display: "grid",
    gap: "16px",
  },
  kicker: {
    margin: 0,
    textTransform: "uppercase",
    letterSpacing: "0.2em",
    fontSize: "11px",
    fontWeight: 700,
    color: "#0f766e",
  },
  title: {
    margin: "8px 0 4px",
    fontSize: "30px",
    fontWeight: 700,
  },
  subtitle: {
    margin: 0,
    maxWidth: "540px",
    color: "#475569",
    fontSize: "15px",
  },
  badges: {
    display: "flex",
    flexWrap: "wrap",
    gap: "10px",
    marginTop: "10px",
  },
  badge: {
    padding: "6px 12px",
    borderRadius: "999px",
    backgroundColor: "rgba(15, 118, 110, 0.1)",
    color: "#0f766e",
    fontSize: "12px",
    fontWeight: 600,
  },
  heroPanel: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: "12px",
    backgroundColor: "rgba(255, 255, 255, 0.7)",
    borderRadius: "16px",
    padding: "14px",
  },
  heroStat: {
    display: "grid",
    gap: "4px",
  },
  heroStatLabel: {
    margin: 0,
    fontSize: "11px",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#64748b",
  },
  heroStatValue: {
    margin: 0,
    fontSize: "18px",
    fontWeight: 700,
    color: "#0f172a",
    fontFamily: "\"IBM Plex Mono\", monospace",
  },
  stats: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
  },
  form: {
    display: "grid",
    gap: "12px",
  },
  formRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
  },
  label: {
    display: "grid",
    gap: "6px",
    fontWeight: 600,
    color: "#0f172a",
    fontSize: "13px",
  },
  labelSmall: {
    display: "grid",
    gap: "6px",
    fontWeight: 600,
    color: "#334155",
    fontSize: "12px",
  },
  input: {
    padding: "10px 12px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    outline: "none",
  },
  inputSmall: {
    padding: "10px 12px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    fontSize: "13px",
    outline: "none",
  },
  sampleRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
  },
  sampleChip: {
    padding: "6px 12px",
    borderRadius: "999px",
    border: "1px dashed #94a3b8",
    background: "#ffffff",
    color: "#475569",
    fontSize: "12px",
  },
  formFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
  },
  helperText: {
    fontSize: "12px",
    color: "#64748b",
  },
  primaryButton: {
    padding: "12px 20px",
    borderRadius: "12px",
    border: "none",
    backgroundColor: "#0f766e",
    color: "#ffffff",
    fontSize: "14px",
    fontWeight: 600,
  },
  loadingBox: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "12px 16px",
    borderRadius: "12px",
    backgroundColor: "#f1f5f9",
    border: "1px solid #e2e8f0",
    color: "#475569",
  },
  loadingDot: {
    width: "10px",
    height: "10px",
    borderRadius: "999px",
    backgroundColor: "#0f766e",
    animation: "component1Pulse 1.2s ease-in-out infinite",
  },
  errorBox: {
    padding: "12px 16px",
    borderRadius: "10px",
    border: "1px solid #fecaca",
    backgroundColor: "#fef2f2",
    color: "#991b1b",
  },
  resultsGrid: {
    display: "grid",
    gap: "14px",
  },
  emptyState: {
    padding: "20px",
    borderRadius: "14px",
    border: "1px dashed #cbd5e1",
    textAlign: "center",
    backgroundColor: "#f8fafc",
  },
  emptyTitle: {
    margin: 0,
    fontWeight: 600,
    fontSize: "16px",
  },
  emptyText: {
    margin: "6px 0 0",
    color: "#64748b",
    fontSize: "13px",
  },
};
