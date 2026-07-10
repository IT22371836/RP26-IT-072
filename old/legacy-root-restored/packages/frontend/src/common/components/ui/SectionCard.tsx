import type { CSSProperties, ReactNode } from "react";

type SectionCardProps = {
  title: string;
  children: ReactNode;
  actionText?: string;
};

export function SectionCard({ title, children, actionText }: SectionCardProps) {
  return (
    <section style={styles.wrapper}>
      <header style={styles.header}>
        <h3 style={styles.title}>{title}</h3>
        {actionText ? <span style={styles.action}>{actionText}</span> : null}
      </header>
      <div>{children}</div>
    </section>
  );
}

const styles: Record<string, CSSProperties> = {
  wrapper: {
    border: "1px solid #cbd5e1",
    borderRadius: "12px",
    backgroundColor: "#ffffff",
    padding: "14px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "10px",
  },
  title: {
    margin: 0,
    fontSize: "16px",
    color: "#0f172a",
  },
  action: {
    fontSize: "12px",
    color: "#0f766e",
    fontWeight: 600,
  },
};
