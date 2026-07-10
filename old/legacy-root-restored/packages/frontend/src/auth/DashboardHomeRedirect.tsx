import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function DashboardHomeRedirect() {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login/customer" replace />;
  }

  return <Navigate to={user.role === "customer" ? "/dashboard/customer" : "/dashboard/provider"} replace />;
}
