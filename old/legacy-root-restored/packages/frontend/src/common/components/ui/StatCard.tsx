import type { CSSProperties } from "react";

type StatCardProps = {
  label: string;
  value: string;
  note?: string;
};

export function StatCard({ label, value, note }: StatCardProps) {
  return (
    <article style={styles.card}>
      <p style={styles.label}>{label}</p>
      <p style={styles.value}>{value}</p>
      {note ? <p style={styles.note}>{note}</p> : null}
    </article>
  );
}

const styles: Record<string, CSSProperties> = {
  card: {
    border: "1px solid #cbd5e1",
    borderRadius: "12px",
    backgroundColor: "#ffffff",
    padding: "14px",
    minWidth: "180px",
  },
  label: {
    margin: 0,
    color: "#475569",
    fontSize: "13px",
  },
  value: {
    margin: "6px 0",
    fontSize: "24px",
    fontWeight: 700,
    color: "#0f172a",
  },
  note: {
    margin: 0,
    color: "#64748b",
    fontSize: "12px",
  },
};
