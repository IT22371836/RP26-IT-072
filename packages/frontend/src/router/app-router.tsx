import { createBrowserRouter } from "react-router-dom";
import { DashboardHomeRedirect } from "../auth/DashboardHomeRedirect";
import { ProtectedRoute } from "../auth/ProtectedRoute";
import { LayoutShell } from "../common/components/layout/LayoutShell";
import { LoginPage } from "../features/auth/pages/LoginPage";
import { SignUpPage } from "../features/auth/pages/SignUpPage";
import { CustomerDashboardPage } from "../features/customer-dashboard/pages/CustomerDashboardPage";
import { ProviderDashboardPage } from "../features/provider-dashboard/pages/ProviderDashboardPage";
import { MaintenancePage } from "../features/maintenance/pages/MaintenancePage";

export const appRouter = createBrowserRouter([
  // Auth routes (public)
  { path: "/login/:role", element: <LoginPage /> },
  { path: "/signup/:role", element: <SignUpPage /> },

  // Protected app routes
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <LayoutShell />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardHomeRedirect /> },
      {
        path: "dashboard/customer",
        element: (
          <ProtectedRoute allowedRoles={["customer"]}>
            <CustomerDashboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "dashboard/provider",
        element: (
          <ProtectedRoute allowedRoles={["provider"]}>
            <ProviderDashboardPage />
          </ProtectedRoute>
        ),
      },
      { path: "maintenance", element: <MaintenancePage /> },
    ],
  },
]);
