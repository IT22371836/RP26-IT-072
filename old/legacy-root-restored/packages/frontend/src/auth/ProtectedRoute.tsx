import { Navigate } from "react-router-dom";
import type { UserRole } from "./types";
import { useAuth } from "./AuthContext";

type ProtectedRouteProps = {
  children: JSX.Element;
  allowedRoles?: UserRole[];
};

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated || !user) {
    return <Navigate to="/login/customer" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={user.role === "customer" ? "/dashboard/customer" : "/dashboard/provider"} replace />;
  }

  return children;
}
