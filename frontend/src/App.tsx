import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AppLayout } from "./layouts/AppLayout";
import { auth, clearSession, saveSession, token } from "./services/api";
import { navigate, useRoute } from "./router";
import { AuthPage } from "./pages/AuthPage";
import { Loader } from "./components/ui";
import { HomePage } from "./pages/HomePage";
import { AskPage } from "./pages/AskPage";
import { RegulationsPage } from "./pages/RegulationsPage";
import { LibraryPage } from "./pages/LibraryPage";
import { BusinessPage } from "./pages/BusinessPage";
import { AssessmentsPage } from "./pages/AssessmentsPage";
import { RiskPage } from "./pages/RiskPage";
import { RemindersPage } from "./pages/RemindersPage";
import { ReportsPage } from "./pages/ReportsPage";
import { AlertsPage } from "./pages/AlertsPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SettingsPage } from "./pages/SettingsPage";
import { HelpPage } from "./pages/HelpPage";
import { SearchPage } from "./pages/SearchPage";
import type { AuthResult, User } from "./types/api";

function renderPage(route: string, user: User, setUser: (u: User) => void, onSignOut: () => void): ReactNode {
  switch (route) {
    case "search": return <SearchPage />;
    case "ask": return <AskPage />;
    case "regulations": return <RegulationsPage user={user} />;
    case "library": return <LibraryPage />;
    case "business": case "onboarding": return <BusinessPage />;
    case "assessments": return <AssessmentsPage />;
    case "risk": return <RiskPage />;
    case "reminders": return <RemindersPage />;
    case "reports": return <ReportsPage />;
    case "alerts": case "notifications": return <NotificationsPage />;
    case "profile": return <ProfilePage user={user} onUserChange={setUser} onSignOut={onSignOut} />;
    case "settings": return <SettingsPage user={user} onWorkspaceRenamed={(name) => setUser({ ...user, workspace_name: name })} />;
    case "help": return <HelpPage />;
    default: return <HomePage user={user} />;
  }
}

export default function App() {
  const route = useRoute();
  const [user, setUser] = useState<User>();
  const [checking, setChecking] = useState(() => !!token());

  // Restore the session once on load.
  useEffect(() => {
    if (!token()) { setChecking(false); return; }
    auth.me().then(setUser).catch(() => clearSession()).finally(() => setChecking(false));
  }, []);

  // Any 401 from the API clears the session and returns to sign-in without a page reload.
  useEffect(() => {
    const onExpired = () => { setUser(undefined); navigate("signin"); };
    window.addEventListener("rl:unauthorized", onExpired);
    return () => window.removeEventListener("rl:unauthorized", onExpired);
  }, []);

  const onAuth = useCallback((result: AuthResult) => { saveSession(result); setUser(result.user); navigate("home"); }, []);
  const signOut = useCallback(() => { clearSession(); setUser(undefined); navigate("signin"); }, []);

  // Keep the URL honest: signed-out users live on #/signin or #/signup, signed-in users never see them.
  useEffect(() => {
    if (checking) return;
    if (!user && route !== "signin" && route !== "signup") navigate("signin");
    if (user && route === "filings") navigate("home");
    if (user && (route === "signin" || route === "signup" || route === "")) navigate("home");
  }, [checking, user, route]);

  if (checking) return <main className="page"><Loader /></main>;
  if (!user) return <AuthPage key={route} signUp={route === "signup"} onSuccess={onAuth} />;
  return <AppLayout user={user} onSignOut={signOut}>{renderPage(route, user, setUser, signOut)}</AppLayout>;
}
