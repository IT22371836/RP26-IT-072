import { Outlet } from "react-router-dom";
import type { CSSProperties } from "react";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export function LayoutShell() {
  return (
    <div style={styles.root}>
      <Sidebar />
      <main style={styles.main}>
        <Header />
        <section style={styles.content}>
          <Outlet />
        </section>
      </main>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  root: {
    minHeight: "100vh",
    display: "flex",
  },
  main: {
    flex: 1,
    padding: "18px",
    display: "grid",
    gap: "16px",
  },
  content: {
    backgroundColor: "#ffffff",
    border: "1px solid #d4dae2",
    borderRadius: "14px",
    padding: "18px",
  },
};
