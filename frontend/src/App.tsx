import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { useAuth } from "./hooks/useAuth";
import { LandingPage } from "./pages/LandingPage";
import { HomePage } from "./pages/HomePage";
import { EditorPage } from "./pages/EditorPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ApiDocsPage } from "./pages/ApiDocsPage";
import { SuperAdminPage } from "./pages/SuperAdminPage";
import { OrgSettingsPage } from "./pages/OrgSettingsPage";
import { NotFoundPage } from "./pages/NotFoundPage";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function SmartHome() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-primary)] border-t-transparent" />
      </div>
    );
  }

  return user ? <HomePage /> : <LandingPage />;
}

export default function App() {
  const { fetchUser } = useAuth();

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SmartHome />} />
        <Route path="/login" element={<SmartHome />} />
        <Route
          path="/edit/:id"
          element={
            <ProtectedRoute>
              <EditorPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />
        <Route path="/api-docs" element={<ApiDocsPage />} />
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <SuperAdminPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/org/:orgId/settings"
          element={
            <ProtectedRoute>
              <OrgSettingsPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
