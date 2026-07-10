import type { CSSProperties } from "react";

export function Header() {
  return (
    <header style={styles.header}>
      <div>
        <h1 style={styles.title}>Maintenance Operations</h1>
        <p style={styles.subtitle}>Central view for service teams and coordinators</p>
      </div>
      <div style={styles.badge}>Live</div>
    </header>
  );
}

const styles: Record<string, CSSProperties> = {
  header: {
    background: "linear-gradient(120deg, #ffffff, #f1f5f9)",
    border: "1px solid #cbd5e1",
    borderRadius: "14px",
    padding: "18px 20px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  title: {
    margin: 0,
    fontSize: "20px",
    color: "#0f172a",
  },
  subtitle: {
    margin: "4px 0 0",
    color: "#334155",
    fontSize: "13px",
  },
  badge: {
    backgroundColor: "#e6f6f1",
    color: "#0f766e",
    padding: "5px 10px",
    borderRadius: "999px",
    fontWeight: 700,
    fontSize: "12px",
  },
};
