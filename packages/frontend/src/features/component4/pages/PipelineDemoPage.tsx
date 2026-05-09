import { useState } from "react";
import type { CSSProperties } from "react";
import { SectionCard, StatCard } from "../../../common/components/ui";
import type { PipelineRunResponse, ProviderRankEntry } from "../types";
import { runPipeline } from "../services/aspectAnalysisService";

const TIER_COLOR: Record<string, string> = {
  Elite: "#7c3aed",
  Trusted: "#0f766e",
  Verified: "#1d4ed8",
  Unknown: "#64748b",
};
const TIER_BG: Record<string, string> = {
  Elite: "#f5f3ff",
  Trusted: "#f0fdfa",
  Verified: "#eff6ff",
  Unknown: "#f8fafc",
};

function TierBadge({ tier }: { tier: string }) {
  return (
    <span style={{ ...styles.tierBadge, backgroundColor: TIER_BG[tier] ?? "#f8fafc", color: TIER_COLOR[tier] ?? "#64748b" }}>
      {tier}
    </span>
  );
}

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? "#7c3aed" : value >= 0.65 ? "#0f766e" : "#1d4ed8";
  return (
    <div style={styles.scoreBarRow}>
      <div style={styles.scoreBarTrack}>
        <div style={{ ...styles.scoreBarFill, width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span style={{ ...styles.scoreBarNum, color }}>{value.toFixed(3)}</span>
    </div>
  );
}

function BreakdownPill({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.pill}>
      <span style={styles.pillLabel}>{label}</span>
      <span style={styles.pillValue}>{value}</span>
    </div>
  );
}

function ProviderResultCard({ entry, isTop }: { entry: ProviderRankEntry; isTop: boolean }) {
  const tierColor = TIER_COLOR[entry.tier] ?? "#64748b";
  return (
    <div style={{ ...styles.resultCard, borderColor: isTop ? tierColor : "#e2e8f0", borderWidth: isTop ? 2 : 1 }}>
      <div style={styles.resultCardHeader}>
        <div style={styles.rankBadge}>#{entry.rank}</div>
        <span style={styles.resultProviderId}>{entry.provider_id}</span>
        <TierBadge tier={entry.tier} />
      </div>

      {entry.S_final != null && <ScoreBar value={entry.S_final} />}

      {entry.explanation && (
        <p style={styles.explanation}>{entry.explanation}</p>
      )}

      <div style={styles.pillRow}>
        {entry.S_cred != null && <BreakdownPill label="S_cred" value={entry.S_cred.toFixed(3)} />}
        {entry.S_overall != null && <BreakdownPill label="S_overall" value={entry.S_overall.toFixed(3)} />}
        {entry.fraud_ratio != null && (
          <BreakdownPill
            label="Fraud ratio"
            value={`${(entry.fraud_ratio * 100).toFixed(1)}%`}
          />
        )}
        {entry.recency_boost != null && (
          <BreakdownPill label="Recency" value={entry.recency_boost.toFixed(3)} />
        )}
        {entry.avg_rating != null && (
          <BreakdownPill label="Avg rating" value={`${entry.avg_rating.toFixed(2)} ★`} />
        )}
        {entry.total_reviews != null && (
          <BreakdownPill label="Reviews" value={String(entry.total_reviews)} />
        )}
      </div>
    </div>
  );
}

function PipelineFlowDiagram({ source }: { source: "random" | "component3" | null }) {
  const c3Active = source === "component3";
  return (
    <div style={styles.flow}>
      <div style={{ ...styles.flowBox, borderColor: c3Active ? "#0f766e" : "#94a3b8", color: c3Active ? "#0f766e" : "#94a3b8" }}>
        <span style={styles.flowLabel}>Component 3</span>
        <span style={styles.flowSub}>{c3Active ? "Provider IDs received" : "Not integrated yet"}</span>
      </div>
      <div style={styles.flowArrow}>→</div>
      <div style={{ ...styles.flowBox, borderColor: "#0f766e", color: "#0f766e" }}>
        <span style={styles.flowLabel}>Component 4</span>
        <span style={styles.flowSub}>Fraud · ALSA · S_final</span>
      </div>
      <div style={styles.flowArrow}>→</div>
      <div style={{ ...styles.flowBox, borderColor: "#7c3aed", color: "#7c3aed" }}>
        <span style={styles.flowLabel}>Top-5 Ranked</span>
        <span style={styles.flowSub}>S_final + explanation</span>
      </div>
    </div>
  );
}

export function PipelineDemoPage() {
  const [result, setResult] = useState<PipelineRunResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [mode, setMode] = useState<"random" | "custom">("random");
  const [customInput, setCustomInput] = useState("");
  const [customIds, setCustomIds] = useState<string[]>([]);

  function addCustomId() {
    const id = customInput.trim().toUpperCase();
    if (!id || customIds.includes(id) || customIds.length >= 20) return;
    setCustomIds((prev) => [...prev, id]);
    setCustomInput("");
  }

  function removeCustomId(id: string) {
    setCustomIds((prev) => prev.filter((x) => x !== id));
  }

  async function handleRun() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const ids = mode === "custom" && customIds.length > 0 ? customIds : undefined;
      const data = await runPipeline(ids, 5);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pipeline failed.");
    } finally {
      setLoading(false);
    }
  }

  const canRun = mode === "random" || customIds.length >= 2;

  return (
    <div style={styles.page}>
      {/* Hero */}
      <div style={styles.hero}>
        <div>
          <p style={styles.eyebrow}>Component 3 → Component 4</p>
          <h2 style={styles.title}>Provider Ranking Pipeline</h2>
          <p style={styles.subtitle}>
            Receives filtered provider IDs from Component 3, scores each with the S_final credibility formula
            (fraud detection + ALSA sentiment + recency), and returns the Top‑5 ranked providers with explanations.
          </p>
        </div>
        <div style={styles.statRow}>
          <StatCard label="Formula" value="S_final" note="40% cred · 35% overall · 15% fraud · 10% recency" />
          <StatCard label="Component 3" value={result?.source === "component3" ? "Active" : "Pending"} note={result?.source === "component3" ? "IDs received" : "Using random sample"} />
          <StatCard label="Output" value="Top-5" note="Ranked with explanations" />
        </div>
      </div>

      {/* Pipeline diagram */}
      <SectionCard title="Pipeline Flow">
        <PipelineFlowDiagram source={result?.source ?? null} />
        {result && (
          <div style={styles.noteBox}>
            <span style={styles.noteIcon}>{result.source === "random" ? "ℹ" : "✓"}</span>
            <span style={styles.noteText}>{result.note}</span>
          </div>
        )}
      </SectionCard>

      {/* Run controls */}
      <SectionCard title="Run Pipeline">
        <div style={styles.modeRow}>
          {(["random", "custom"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              style={{
                ...styles.modeBtn,
                backgroundColor: mode === m ? "#0f766e" : "#ffffff",
                color: mode === m ? "#ffffff" : "#475569",
                borderColor: mode === m ? "#0f766e" : "#cbd5e1",
              }}
            >
              {m === "random" ? "Random sample (C3 not ready)" : "Custom provider IDs (C3 ready)"}
            </button>
          ))}
        </div>

        {mode === "custom" && (
          <div style={{ marginTop: "14px" }}>
            <div style={styles.customInputRow}>
              <input
                type="text"
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustomId())}
                placeholder="Type a provider ID from Component 3 and press Add (e.g. P42)"
                style={styles.input}
                disabled={customIds.length >= 20}
              />
              <button
                type="button"
                onClick={addCustomId}
                disabled={!customInput.trim() || customIds.length >= 20}
                style={styles.addBtn}
              >
                Add
              </button>
            </div>
            {customIds.length > 0 && (
              <div style={styles.chipRow}>
                {customIds.map((id) => (
                  <span key={id} style={styles.chip}>
                    {id}
                    <button type="button" onClick={() => removeCustomId(id)} style={styles.chipX}>×</button>
                  </span>
                ))}
              </div>
            )}
            {customIds.length < 2 && (
              <p style={styles.hint}>Add at least 2 provider IDs to run.</p>
            )}
          </div>
        )}

        <div style={{ marginTop: "16px" }}>
          <button
            type="button"
            onClick={() => void handleRun()}
            disabled={loading || !canRun}
            style={{
              ...styles.runBtn,
              opacity: loading || !canRun ? 0.5 : 1,
              cursor: loading || !canRun ? "not-allowed" : "pointer",
            }}
          >
            {loading
              ? "Running pipeline…"
              : mode === "random"
              ? "Run with random sample"
              : `Run with ${customIds.length} provider${customIds.length !== 1 ? "s" : ""}`}
          </button>
        </div>

        {error && (
          <div style={styles.errorBox}><strong>Error:</strong> {error}</div>
        )}
      </SectionCard>

      {/* Results */}
      {result && !loading && (
        <SectionCard title={`Top-${result.top_n} Results — ${result.providers_evaluated} providers evaluated`}>
          <div style={styles.resultGrid}>
            {result.ranked.map((entry) => (
              <ProviderResultCard key={entry.provider_id} entry={entry} isTop={entry.rank === 1} />
            ))}
          </div>
          <p style={styles.timestamp}>
            Run at {new Date(result.timestamp).toLocaleTimeString()} ·{" "}
            source: <strong>{result.source}</strong>
          </p>
        </SectionCard>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: { display: "grid", gap: "16px" },
  hero: {
    display: "grid",
    gap: "14px",
    padding: "20px",
    borderRadius: "16px",
    background:
      "radial-gradient(circle at top left, rgba(124,58,237,0.12), transparent 55%), radial-gradient(circle at 80% 20%, rgba(14,116,144,0.15), transparent 50%), #ffffff",
    border: "1px solid #e2e8f0",
  },
  eyebrow: { margin: 0, textTransform: "uppercase", letterSpacing: "0.28em", fontSize: "11px", color: "#7c3aed" },
  title: { margin: "4px 0 0", color: "#0f172a", fontSize: "22px" },
  subtitle: { margin: "6px 0 0", color: "#475569", fontSize: "14px", lineHeight: "1.5" },
  statRow: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "10px" },

  // Pipeline flow
  flow: { display: "flex", alignItems: "center", flexWrap: "wrap" as const, gap: "12px" },
  flowBox: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    padding: "12px 18px",
    borderRadius: "12px",
    border: "2px solid",
    minWidth: "130px",
    flex: "1 1 130px",
  },
  flowLabel: { fontSize: "13px", fontWeight: 700 },
  flowSub: { fontSize: "11px", marginTop: "2px", opacity: 0.75 },
  flowArrow: { fontSize: "20px", color: "#94a3b8", flexShrink: 0 },

  noteBox: {
    display: "flex",
    alignItems: "flex-start",
    gap: "8px",
    marginTop: "14px",
    padding: "10px 14px",
    borderRadius: "10px",
    backgroundColor: "#f0fdf4",
    border: "1px solid #bbf7d0",
  },
  noteIcon: { fontSize: "15px", color: "#16a34a", flexShrink: 0 },
  noteText: { fontSize: "13px", color: "#14532d", lineHeight: "1.5" },

  // Mode toggle
  modeRow: { display: "flex", gap: "8px", flexWrap: "wrap" as const },
  modeBtn: {
    padding: "9px 16px",
    borderRadius: "10px",
    border: "1px solid",
    fontSize: "13px",
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 120ms ease",
  },

  // Custom input
  customInputRow: { display: "flex", gap: "8px" },
  input: {
    flex: 1,
    padding: "10px 14px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    color: "#0f172a",
    outline: "none",
  },
  addBtn: {
    padding: "10px 16px",
    borderRadius: "10px",
    border: "1px solid #0f766e",
    backgroundColor: "transparent",
    color: "#0f766e",
    fontSize: "14px",
    fontWeight: 600,
    cursor: "pointer",
  },
  chipRow: { display: "flex", flexWrap: "wrap" as const, gap: "6px", marginTop: "10px" },
  chip: {
    display: "inline-flex",
    alignItems: "center",
    gap: "4px",
    padding: "4px 10px",
    borderRadius: "20px",
    backgroundColor: "#f0fdfa",
    border: "1px solid #99f6e4",
    color: "#0f766e",
    fontSize: "13px",
    fontWeight: 600,
  },
  chipX: { background: "none", border: "none", color: "#0f766e", cursor: "pointer", fontSize: "15px", lineHeight: 1, padding: "0 2px" },
  hint: { margin: "8px 0 0", fontSize: "12px", color: "#94a3b8" },

  runBtn: {
    padding: "12px 28px",
    borderRadius: "12px",
    border: "none",
    backgroundColor: "#7c3aed",
    color: "#ffffff",
    fontSize: "15px",
    fontWeight: 700,
    transition: "opacity 150ms ease",
  },
  errorBox: {
    marginTop: "14px",
    padding: "12px 16px",
    borderRadius: "10px",
    backgroundColor: "#fef2f2",
    border: "1px solid #fecaca",
    color: "#991b1b",
    fontSize: "14px",
  },

  // Result cards
  resultGrid: { display: "grid", gap: "14px" },
  resultCard: {
    padding: "16px",
    borderRadius: "14px",
    border: "1px solid",
    backgroundColor: "#ffffff",
    display: "grid",
    gap: "12px",
  },
  resultCardHeader: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  rankBadge: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    backgroundColor: "#f1f5f9",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "12px",
    fontWeight: 800,
    color: "#475569",
    flexShrink: 0,
  },
  resultProviderId: { fontSize: "16px", fontWeight: 700, color: "#0f172a", flex: 1 },
  tierBadge: {
    display: "inline-block",
    padding: "2px 10px",
    borderRadius: "20px",
    fontSize: "12px",
    fontWeight: 700,
  },

  scoreBarRow: { display: "flex", alignItems: "center", gap: "10px" },
  scoreBarTrack: {
    flex: 1,
    height: "8px",
    backgroundColor: "#f1f5f9",
    borderRadius: "4px",
    overflow: "hidden",
  },
  scoreBarFill: { height: "100%", borderRadius: "4px", transition: "width 500ms ease" },
  scoreBarNum: { fontSize: "14px", fontWeight: 700, minWidth: "44px", textAlign: "right" as const },

  explanation: {
    margin: 0,
    fontSize: "13px",
    color: "#475569",
    lineHeight: "1.6",
    padding: "10px 14px",
    backgroundColor: "#f8fafc",
    borderRadius: "8px",
    borderLeft: "3px solid #0f766e",
  },

  pillRow: { display: "flex", flexWrap: "wrap" as const, gap: "6px" },
  pill: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    padding: "6px 12px",
    borderRadius: "10px",
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    minWidth: "64px",
  },
  pillLabel: { fontSize: "10px", color: "#94a3b8", textTransform: "uppercase" as const, letterSpacing: "0.06em" },
  pillValue: { fontSize: "13px", fontWeight: 700, color: "#0f172a", marginTop: "2px" },

  timestamp: { margin: "14px 0 0", fontSize: "12px", color: "#94a3b8", textAlign: "right" as const },
};
