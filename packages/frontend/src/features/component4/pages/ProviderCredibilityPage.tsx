import { useState } from "react";
import type { CSSProperties } from "react";
import { SectionCard, StatCard } from "../../../common/components/ui";
import type { ProviderCredibility, ProviderRankEntry } from "../types";
import { getProviderCredibility, rankProviders } from "../services/aspectAnalysisService";

const SAMPLE_PROVIDERS = ["P1", "P10", "P10174", "P10239", "P1003"];

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
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: "20px",
        fontSize: "12px",
        fontWeight: 700,
        backgroundColor: TIER_BG[tier] ?? "#f8fafc",
        color: TIER_COLOR[tier] ?? "#64748b",
      }}
    >
      {tier}
    </span>
  );
}

function ScoreBar({ value, max = 1 }: { value: number; max?: number }) {
  const pct = Math.round((value / max) * 100);
  const color = value >= 0.8 ? "#7c3aed" : value >= 0.65 ? "#0f766e" : "#1d4ed8";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={styles.track}>
        <div style={{ ...styles.fill, width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span style={{ fontSize: "12px", fontWeight: 600, color, minWidth: "36px" }}>
        {value.toFixed(3)}
      </span>
    </div>
  );
}

function ProviderCard({ data }: { data: ProviderCredibility }) {
  const rows: [string, string | number | null | undefined][] = [
    ["S_final", data.S_final],
    ["Credibility score (S_cred)", data.S_cred ?? "—"],
    ["Overall score (S_overall)", data.S_overall ?? "—"],
    ["Fraud ratio", data.fraud_ratio != null ? (data.fraud_ratio * 100).toFixed(1) + "%" : "—"],
    ["Recency boost", data.recency_boost != null ? data.recency_boost.toFixed(4) : "—"],
    ["Avg. rating", data.avg_rating != null ? data.avg_rating.toFixed(2) + " ★" : "—"],
    ["Total reviews", data.total_reviews ?? "—"],
    ["Suspicious reviews", data.suspicious_count ?? "—"],
  ];
  return (
    <div style={styles.providerCard}>
      <div style={styles.cardHeader}>
        <span style={styles.providerId}>{data.provider_id}</span>
        <TierBadge tier={data.tier} />
      </div>
      {data.S_final != null && (
        <div style={{ marginBottom: "10px" }}>
          <ScoreBar value={data.S_final} />
        </div>
      )}
      {data.explanation && (
        <p style={styles.explanation}>{data.explanation}</p>
      )}
      <table style={styles.table}>
        <tbody>
          {rows.map(([label, val]) => (
            <tr key={label}>
              <td style={styles.tdLabel}>{label}</td>
              <td style={styles.tdVal}>{String(val)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RankTable({ entries }: { entries: ProviderRankEntry[] }) {
  return (
    <div style={styles.rankTable}>
      <div style={styles.rankHeader}>
        {["Rank", "Provider ID", "S_final", "Tier", "Fraud Ratio", "Avg Rating"].map((h) => (
          <span key={h} style={styles.rankHeaderCell}>{h}</span>
        ))}
      </div>
      {entries.map((e) => (
        <div key={e.provider_id} style={styles.rankRow}>
          <span style={styles.rankNum}>#{e.rank}</span>
          <span style={{ ...styles.rankCell, fontWeight: 600 }}>{e.provider_id}</span>
          <span style={styles.rankCell}>
            {e.S_final != null ? e.S_final.toFixed(4) : "—"}
          </span>
          <span style={styles.rankCell}><TierBadge tier={e.tier} /></span>
          <span style={styles.rankCell}>
            {e.fraud_ratio != null ? (e.fraud_ratio * 100).toFixed(1) + "%" : "—"}
          </span>
          <span style={styles.rankCell}>
            {e.avg_rating != null ? e.avg_rating.toFixed(2) + " ★" : "—"}
          </span>
        </div>
      ))}
    </div>
  );
}

export function ProviderCredibilityPage() {
  const [lookupId, setLookupId] = useState("");
  const [lookupResult, setLookupResult] = useState<ProviderCredibility | null>(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const [rankIds, setRankIds] = useState<string[]>([]);
  const [rankInput, setRankInput] = useState("");
  const [rankResult, setRankResult] = useState<ProviderRankEntry[] | null>(null);
  const [rankLoading, setRankLoading] = useState(false);
  const [rankError, setRankError] = useState<string | null>(null);

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    const id = lookupId.trim();
    if (!id) return;
    setLookupLoading(true);
    setLookupError(null);
    setLookupResult(null);
    try {
      const data = await getProviderCredibility(id);
      setLookupResult(data);
    } catch (err) {
      setLookupError(err instanceof Error ? err.message : "Lookup failed.");
    } finally {
      setLookupLoading(false);
    }
  }

  function addRankId() {
    const id = rankInput.trim();
    if (!id || rankIds.includes(id) || rankIds.length >= 10) return;
    setRankIds((prev) => [...prev, id]);
    setRankInput("");
  }

  function removeRankId(id: string) {
    setRankIds((prev) => prev.filter((x) => x !== id));
  }

  async function handleRank() {
    if (rankIds.length < 2) return;
    setRankLoading(true);
    setRankError(null);
    setRankResult(null);
    try {
      const data = await rankProviders(rankIds);
      setRankResult(data.ranked);
    } catch (err) {
      setRankError(err instanceof Error ? err.message : "Ranking failed.");
    } finally {
      setRankLoading(false);
    }
  }

  return (
    <div style={styles.page}>
      <div>
        <h2 style={styles.title}>Provider Credibility</h2>
        <p style={styles.subtitle}>
          Look up pre-computed S_final credibility scores and tiers for providers, or compare multiple providers.
        </p>
      </div>

      <div style={styles.stats}>
        <StatCard label="Formula"     value="S_final"  note="40% cred · 35% overall · 15% fraud · 10% recency" />
        <StatCard label="Tiers"       value="3"        note="Elite ≥ 0.80 · Trusted ≥ 0.65 · Verified" />
        <StatCard label="Providers"   value="69.7k"    note="Pre-computed in index" />
      </div>

      <SectionCard title="Provider Lookup">
        <p style={styles.sampleLabel}>Quick samples</p>
        <div style={styles.sampleChips}>
          {SAMPLE_PROVIDERS.map((id) => (
            <button
              key={id}
              type="button"
              style={{
                ...styles.sampleChip,
                borderColor: lookupId === id ? "#0f766e" : "#cbd5e1",
                backgroundColor: lookupId === id ? "#f0fdf9" : "#ffffff",
                color: lookupId === id ? "#0f766e" : "#334155",
                fontWeight: lookupId === id ? 700 : 400,
              }}
              onClick={() => {
                setLookupId(id);
                setLookupLoading(true);
                setLookupError(null);
                setLookupResult(null);
                getProviderCredibility(id)
                  .then(setLookupResult)
                  .catch((err) => setLookupError(err instanceof Error ? err.message : "Lookup failed."))
                  .finally(() => setLookupLoading(false));
              }}
            >
              {id}
            </button>
          ))}
        </div>

        <form onSubmit={handleLookup} style={{ ...styles.lookupForm, marginTop: "12px" }}>
          <input
            type="text"
            value={lookupId}
            onChange={(e) => setLookupId(e.target.value)}
            placeholder="Or type any provider ID  e.g. P42, P1000"
            style={styles.input}
          />
          <button
            type="submit"
            disabled={lookupLoading || lookupId.trim().length === 0}
            style={{
              ...styles.btn,
              opacity: lookupLoading || lookupId.trim().length === 0 ? 0.5 : 1,
              cursor: lookupLoading || lookupId.trim().length === 0 ? "not-allowed" : "pointer",
            }}
          >
            {lookupLoading ? "Looking up…" : "Look up"}
          </button>
        </form>
        {lookupError && <div style={{ ...styles.errorBox, marginTop: "12px" }}><strong>Error:</strong> {lookupError}</div>}
        {lookupResult && !lookupLoading && (
          <div style={{ marginTop: "14px" }}>
            <ProviderCard data={lookupResult} />
          </div>
        )}
      </SectionCard>

      <SectionCard title="Compare & Rank Providers">
        <div style={styles.rankTopRow}>
          <p style={styles.sampleLabel}>Load sample set</p>
          <button
            type="button"
            style={styles.btnSecondary}
            onClick={() => setRankIds(SAMPLE_PROVIDERS)}
          >
            Load {SAMPLE_PROVIDERS.join(", ")}
          </button>
        </div>

        <div style={{ ...styles.rankInputRow, marginTop: "12px" }}>
          <input
            type="text"
            value={rankInput}
            onChange={(e) => setRankInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addRankId())}
            placeholder="Or type a provider ID and press Add / Enter"
            style={{ ...styles.input, flex: 1 }}
            disabled={rankIds.length >= 10}
          />
          <button
            type="button"
            onClick={addRankId}
            disabled={!rankInput.trim() || rankIds.length >= 10}
            style={{
              ...styles.btnSecondary,
              opacity: !rankInput.trim() || rankIds.length >= 10 ? 0.5 : 1,
            }}
          >
            Add
          </button>
        </div>

        {rankIds.length > 0 && (
          <div style={styles.chipRow}>
            {rankIds.map((id) => (
              <span key={id} style={styles.chip}>
                {id}
                <button type="button" onClick={() => removeRankId(id)} style={styles.chipX}>×</button>
              </span>
            ))}
          </div>
        )}

        <div style={{ marginTop: "12px", display: "flex", gap: "10px", alignItems: "center" }}>
          <button
            type="button"
            onClick={() => void handleRank()}
            disabled={rankIds.length < 2 || rankLoading}
            style={{
              ...styles.btn,
              opacity: rankIds.length < 2 || rankLoading ? 0.5 : 1,
              cursor: rankIds.length < 2 || rankLoading ? "not-allowed" : "pointer",
            }}
          >
            {rankLoading ? "Ranking…" : "Rank Providers"}
          </button>
          {rankIds.length < 2 && (
            <span style={{ fontSize: "12px", color: "#94a3b8" }}>Add at least 2 providers to rank</span>
          )}
        </div>

        {rankError && <div style={{ ...styles.errorBox, marginTop: "12px" }}><strong>Error:</strong> {rankError}</div>}
        {rankResult && !rankLoading && (
          <div style={{ marginTop: "14px" }}>
            <RankTable entries={rankResult} />
          </div>
        )}
      </SectionCard>
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
  sampleLabel: { margin: "0 0 8px", fontSize: "12px", fontWeight: 600, color: "#64748b", textTransform: "uppercase" as const, letterSpacing: "0.04em" },
  sampleChips: { display: "flex", flexWrap: "wrap" as const, gap: "8px" },
  sampleChip: {
    padding: "5px 14px",
    borderRadius: "999px",
    border: "1px solid",
    fontSize: "13px",
    cursor: "pointer",
    transition: "all 120ms ease",
  },
  lookupForm: { display: "flex", gap: "10px", alignItems: "center" },
  rankTopRow: { display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" as const, gap: "8px" },
  rankInputRow: { display: "flex", gap: "10px", alignItems: "center" },
  input: {
    padding: "10px 14px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
    color: "#0f172a",
    outline: "none",
    flex: 1,
  },
  btn: {
    padding: "10px 20px",
    borderRadius: "10px",
    border: "none",
    backgroundColor: "#0f766e",
    color: "#ffffff",
    fontSize: "14px",
    fontWeight: 600,
    transition: "opacity 150ms ease",
    whiteSpace: "nowrap",
  },
  btnSecondary: {
    padding: "10px 16px",
    borderRadius: "10px",
    border: "1px solid #0f766e",
    backgroundColor: "transparent",
    color: "#0f766e",
    fontSize: "14px",
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  errorBox: {
    padding: "12px 16px",
    borderRadius: "10px",
    backgroundColor: "#fef2f2",
    border: "1px solid #fecaca",
    color: "#991b1b",
    fontSize: "14px",
  },
  chipRow: { display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" },
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
  chipX: {
    background: "none",
    border: "none",
    color: "#0f766e",
    cursor: "pointer",
    fontSize: "15px",
    lineHeight: 1,
    padding: "0 2px",
  },
  providerCard: {
    padding: "16px",
    borderRadius: "10px",
    border: "1px solid #e2e8f0",
    backgroundColor: "#f8fafc",
  },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "12px",
  },
  providerId: { fontSize: "16px", fontWeight: 700, color: "#0f172a" },
  explanation: {
    margin: "0 0 12px",
    fontSize: "13px",
    color: "#475569",
    lineHeight: "1.5",
    padding: "10px 12px",
    backgroundColor: "#f8fafc",
    borderRadius: "8px",
    borderLeft: "3px solid #0f766e",
  },
  table: { width: "100%", borderCollapse: "collapse" },
  tdLabel: {
    padding: "6px 12px 6px 0",
    fontSize: "13px",
    color: "#475569",
    borderBottom: "1px solid #f1f5f9",
    width: "55%",
  },
  tdVal: {
    padding: "6px 0",
    fontSize: "13px",
    fontWeight: 600,
    color: "#0f172a",
    borderBottom: "1px solid #f1f5f9",
  },
  track: {
    flex: 1,
    height: "6px",
    backgroundColor: "#e2e8f0",
    borderRadius: "3px",
    overflow: "hidden",
  },
  fill: { height: "100%", borderRadius: "3px", transition: "width 400ms ease" },
  rankTable: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: "4px",
  },
  rankHeader: {
    display: "grid",
    gridTemplateColumns: "50px 1fr 90px 90px 90px 90px",
    padding: "8px 12px",
    backgroundColor: "#f1f5f9",
    borderRadius: "8px",
    fontSize: "12px",
    fontWeight: 700,
    color: "#475569",
    gap: "8px",
  },
  rankHeaderCell: {},
  rankRow: {
    display: "grid",
    gridTemplateColumns: "50px 1fr 90px 90px 90px 90px",
    padding: "10px 12px",
    backgroundColor: "#ffffff",
    borderRadius: "8px",
    border: "1px solid #f1f5f9",
    fontSize: "13px",
    color: "#0f172a",
    alignItems: "center",
    gap: "8px",
  },
  rankNum: { fontWeight: 700, color: "#94a3b8", fontSize: "13px" },
  rankCell: { fontSize: "13px" },
};
