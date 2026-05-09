import { NavLink } from "react-router-dom";
import type { CSSProperties } from "react";
import { useAuth } from "../../../auth/AuthContext";

const customerNavItems = [
  { to: "/dashboard/customer", label: "Customer Dashboard" },
  { to: "/maintenance", label: "Maintenance" },
  { to: "/component1/recommendations", label: "Hybrid Recommendations" },
  { to: "/component4/aspect-analysis", label: "Aspect Analyser" },
  { to: "/component4/review-credibility", label: "Review Credibility" },
  { to: "/component4/provider-credibility", label: "Provider Credibility" },
  { to: "/component4/fraud-blending", label: "Fraud + Blending Demo" },
  { to: "/component4/pipeline", label: "C3 → C4 Pipeline" },
];

const providerNavItems = [
  { to: "/dashboard/provider", label: "Provider Dashboard" },
  { to: "/maintenance", label: "Maintenance" },
  { to: "/component1/recommendations", label: "Hybrid Recommendations" },
  { to: "/component4/aspect-analysis", label: "Aspect Analyser" },
  { to: "/component4/review-credibility", label: "Review Credibility" },
  { to: "/component4/provider-credibility", label: "Provider Credibility" },
  { to: "/component4/fraud-blending", label: "Fraud + Blending Demo" },
  { to: "/component4/pipeline", label: "C3 → C4 Pipeline" },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const navItems = user?.role === "provider" ? providerNavItems : customerNavItems;

  return (
    <aside style={styles.sidebar}>
      <div style={styles.brand}>MSP Platform</div>
      <p style={styles.role}>{user?.role === "provider" ? "Service Provider" : "Customer"}</p>
      <nav style={styles.nav}>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              ...styles.link,
              backgroundColor: isActive ? "#0b6e4f" : "transparent",
              color: isActive ? "#ffffff" : "#deebe7",
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <button type="button" style={styles.logoutButton} onClick={logout}>
        Log out
      </button>
    </aside>
  );
}

const styles: Record<string, CSSProperties> = {
  sidebar: {
    width: "250px",
    minHeight: "100vh",
    backgroundColor: "#13312a",
    padding: "20px 14px",
  },
  brand: {
    fontWeight: 700,
    color: "#ecf3f1",
    letterSpacing: "0.2px",
    marginBottom: "4px",
  },
  role: {
    margin: "0 0 18px",
    color: "#9fc3b7",
    fontSize: "12px",
  },
  nav: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  link: {
    borderRadius: "10px",
    padding: "10px 12px",
    fontSize: "14px",
    transition: "all 180ms ease",
  },
  logoutButton: {
    marginTop: "18px",
    width: "100%",
    border: "1px solid #3f5f56",
    borderRadius: "10px",
    padding: "10px 12px",
    color: "#deebe7",
    backgroundColor: "transparent",
    cursor: "pointer",
    textAlign: "left",
  },
};
