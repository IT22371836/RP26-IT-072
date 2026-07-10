import type { CSSProperties } from "react";
import type { AspectScores } from "../types";

type AspectKey = "QUAL" | "PRICE" | "TIME" | "COMM";

const ASPECT_CONFIG: Record<AspectKey, { label: string; color: string; bg: string; desc: string }> = {
  QUAL:  { label: "Quality",        color: "#065f46", bg: "#d1fae5", desc: "Workmanship & repair outcome" },
  PRICE: { label: "Price",          color: "#1e40af", bg: "#dbeafe", desc: "Cost & value for money" },
  TIME:  { label: "Time",           color: "#92400e", bg: "#fef3c7", desc: "Punctuality & response speed" },
  COMM:  { label: "Communication",  color: "#9d174d", bg: "#fce7f3", desc: "Clarity & professionalism" },
};

type Props = { aspects: AspectScores };

export function AspectScorePanel({ aspects }: Props) {
  return (
    <div style={styles.grid}>
      {(Object.entries(ASPECT_CONFIG) as [AspectKey, typeof ASPECT_CONFIG[AspectKey]][]).map(
        ([key, cfg]) => {
          const score = aspects[key];
          const pct = score !== null && score !== undefined ? Math.round(score * 100) : null;

          return (
            <div key={key} style={{ ...styles.card, borderLeftColor: cfg.color }}>
              <div style={styles.cardTop}>
                <span style={{ ...styles.badge, backgroundColor: cfg.bg, color: cfg.color }}>
                  {cfg.label}
                </span>
                <span style={{ ...styles.pctText, color: cfg.color }}>
                  {pct !== null ? `${pct}%` : "—"}
                </span>
              </div>
              <p style={styles.desc}>{cfg.desc}</p>
              <div style={styles.barTrack}>
                <div
                  style={{
                    ...styles.barFill,
                    width: `${pct ?? 0}%`,
                    backgroundColor: cfg.color,
                    opacity: pct !== null ? 1 : 0,
                  }}
                />
              </div>
              {pct === null && <p style={styles.notMentioned}>Not mentioned</p>}
            </div>
          );
        }
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "10px",
    marginTop: "18px",
  },
  card: {
    border: "1px solid #e2e8f0",
    borderLeft: "4px solid",
    borderRadius: "10px",
    backgroundColor: "#ffffff",
    padding: "14px",
  },
  cardTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "6px",
  },
  badge: {
    padding: "3px 8px",
    borderRadius: "20px",
    fontSize: "12px",
    fontWeight: 700,
  },
  pctText: {
    fontSize: "22px",
    fontWeight: 800,
  },
  desc: {
    margin: "0 0 10px",
    fontSize: "12px",
    color: "#64748b",
  },
  barTrack: {
    height: "6px",
    backgroundColor: "#f1f5f9",
    borderRadius: "4px",
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: "4px",
    transition: "width 500ms ease",
  },
  notMentioned: {
    margin: "6px 0 0",
    fontSize: "11px",
    color: "#94a3b8",
    fontStyle: "italic",
  },
};
