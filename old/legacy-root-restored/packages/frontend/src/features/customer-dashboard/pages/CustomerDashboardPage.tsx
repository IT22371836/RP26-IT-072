import type { CSSProperties } from "react";
import { SectionCard, StatCard } from "../../../common/components/ui";

const recentRequests = [
  { id: "REQ-1023", item: "Water Pump", status: "In progress", eta: "2 days" },
  { id: "REQ-1022", item: "Air Conditioner", status: "Awaiting provider", eta: "3 days" },
  { id: "REQ-1019", item: "Generator", status: "Completed", eta: "Done" },
];

export function CustomerDashboardPage() {
  return (
    <div style={styles.page}>
      <div>
        <h2 style={styles.title}>Customer Dashboard</h2>
        <p style={styles.subtitle}>Track submitted requests, service status, and monthly spending.</p>
      </div>

      <div style={styles.stats}>
        <StatCard label="Open Requests" value="12" note="3 escalated" />
        <StatCard label="Completed This Month" value="29" note="92% on time" />
        <StatCard label="Monthly Spend" value="LKR 240,000" note="Within budget" />
      </div>

      <SectionCard title="Recent Service Requests" actionText="View all">
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.tableHead}>Request ID</th>
              <th style={styles.tableHead}>Asset</th>
              <th style={styles.tableHead}>Status</th>
              <th style={styles.tableHead}>ETA</th>
            </tr>
          </thead>
          <tbody>
            {recentRequests.map((request) => (
              <tr key={request.id}>
                <td style={styles.tableCell}>{request.id}</td>
                <td style={styles.tableCell}>{request.item}</td>
                <td style={styles.tableCell}>{request.status}</td>
                <td style={styles.tableCell}>{request.eta}</td>
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
