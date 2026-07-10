import type { CSSProperties } from "react";
import type { RecommendationItem } from "../types";

const scorePalette = [
  { label: "Hybrid", key: "hybrid", color: "#0f766e" },
  { label: "TF-IDF", key: "tfidf", color: "#0ea5e9" },
  { label: "BERT", key: "bert", color: "#f97316" },
  { label: "CF", key: "cf", color: "#22c55e" },
] as const;

type RecommendationCardProps = {
  item: RecommendationItem;
};

function formatCurrency(amount: number) {
  return new Intl.NumberFormat("en-LK", {
    style: "currency",
    currency: "LKR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function RecommendationCard({ item }: RecommendationCardProps) {
  return (
    <article style={styles.card}>
      <header style={styles.header}>
        <div>
          <p style={styles.rank}>Rank #{item.rank}</p>
          <h4 style={styles.name}>{item.provider_name}</h4>
          <p style={styles.meta}>
            {item.service} · {item.location}
          </p>
        </div>
        <div style={styles.price}>{formatCurrency(item.price)}</div>
      </header>

      <div style={styles.metrics}>
        <div>
          <p style={styles.metricLabel}>Rating</p>
          <p style={styles.metricValue}>{item.rating.toFixed(1)} / 5</p>
        </div>
        <div>
          <p style={styles.metricLabel}>Experience</p>
          <p style={styles.metricValue}>{item.experience_years} yrs</p>
        </div>
        <div>
          <p style={styles.metricLabel}>Interactions</p>
          <p style={styles.metricValue}>{item.engagement.interaction_count}</p>
        </div>
        <div>
          <p style={styles.metricLabel}>Booking success</p>
          <p style={styles.metricValue}>{Math.round(item.engagement.booking_success_rate * 100)}%</p>
        </div>
      </div>

      <div style={styles.scoreStack}>
        {scorePalette.map((score) => {
          const value = item.scores[score.key];
          return (
            <div key={score.key} style={styles.scoreRow}>
              <span style={styles.scoreLabel}>{score.label}</span>
              <div style={styles.scoreTrack}>
                <div
                  style={{
                    ...styles.scoreFill,
                    width: `${Math.min(value * 100, 100)}%`,
                    backgroundColor: score.color,
                  }}
                />
              </div>
              <span style={styles.scoreValue}>{value.toFixed(3)}</span>
            </div>
          );
        })}
      </div>
    </article>
  );
}

const styles: Record<string, CSSProperties> = {
  card: {
    background: "#ffffff",
    borderRadius: "18px",
    border: "1px solid #e2e8f0",
    padding: "16px",
    display: "grid",
    gap: "14px",
    boxShadow: "0 12px 30px rgba(15, 23, 42, 0.08)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    gap: "12px",
    flexWrap: "wrap",
  },
  rank: {
    margin: 0,
    fontSize: "12px",
    fontWeight: 600,
    color: "#0f766e",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  name: {
    margin: "6px 0 4px",
    fontSize: "20px",
    color: "#0f172a",
  },
  meta: {
    margin: 0,
    color: "#475569",
    fontSize: "14px",
  },
  price: {
    fontWeight: 700,
    fontSize: "18px",
    color: "#0f172a",
    alignSelf: "flex-start",
  },
  metrics: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: "10px",
    background: "#f8fafc",
    borderRadius: "14px",
    padding: "12px",
  },
  metricLabel: {
    margin: 0,
    fontSize: "12px",
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  metricValue: {
    margin: "6px 0 0",
    fontSize: "16px",
    fontWeight: 600,
    color: "#0f172a",
  },
  scoreStack: {
    display: "grid",
    gap: "8px",
  },
  scoreRow: {
    display: "grid",
    gridTemplateColumns: "70px 1fr 54px",
    alignItems: "center",
    gap: "10px",
    fontSize: "13px",
  },
  scoreLabel: {
    color: "#1f2937",
    fontWeight: 600,
  },
  scoreTrack: {
    height: "8px",
    borderRadius: "999px",
    background: "#e2e8f0",
    overflow: "hidden",
  },
  scoreFill: {
    height: "100%",
    borderRadius: "999px",
    transition: "width 400ms ease",
  },
  scoreValue: {
    textAlign: "right",
    fontWeight: 600,
    color: "#0f172a",
    fontFamily: "\"IBM Plex Mono\", monospace",
    fontSize: "12px",
  },
};
