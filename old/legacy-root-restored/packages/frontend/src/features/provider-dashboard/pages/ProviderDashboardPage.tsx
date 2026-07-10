import type { CSSProperties } from "react";
import { SectionCard, StatCard } from "../../../common/components/ui";

const teamBoard = [
  { tech: "Nimal", assigned: 8, completed: 6, utilization: "75%" },
  { tech: "Kasun", assigned: 6, completed: 6, utilization: "100%" },
  { tech: "Dinithi", assigned: 9, completed: 7, utilization: "78%" },
];

export function ProviderDashboardPage() {
  return (
    <div style={styles.page}>
      <div>
        <h2 style={styles.title}>Provider Dashboard</h2>
        <p style={styles.subtitle}>Manage team capacity, SLA commitments, and active jobs.</p>
      </div>

      <div style={styles.stats}>
        <StatCard label="Active Jobs" value="31" note="11 high priority" />
        <StatCard label="SLA Compliance" value="94%" note="Target 95%" />
        <StatCard label="Available Technicians" value="7" note="3 on leave" />
      </div>

      <SectionCard title="Team Capacity Board" actionText="Open planner">
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.tableHead}>Technician</th>
              <th style={styles.tableHead}>Assigned</th>
              <th style={styles.tableHead}>Completed</th>
              <th style={styles.tableHead}>Utilization</th>
            </tr>
          </thead>
          <tbody>
            {teamBoard.map((row) => (
              <tr key={row.tech}>
                <td style={styles.tableCell}>{row.tech}</td>
                <td style={styles.tableCell}>{row.assigned}</td>
                <td style={styles.tableCell}>{row.completed}</td>
                <td style={styles.tableCell}>{row.utilization}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: {
    display: "grid",
    gap: "14px",
  },
  title: {
    margin: 0,
    color: "#0f172a",
  },
  subtitle: {
    margin: "5px 0 0",
    color: "#475569",
    fontSize: "14px",
  },
  stats: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "10px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  tableHead: {
    textAlign: "left",
    color: "#334155",
    fontSize: "12px",
    borderBottom: "1px solid #cbd5e1",
    padding: "8px",
  },
  tableCell: {
    padding: "10px 8px",
    borderBottom: "1px solid #e2e8f0",
    fontSize: "14px",
    color: "#0f172a",
  },
};
