import { useEffect, useState, type PropsWithChildren } from "react";
import { useRoute } from "../router";
import type { User } from "../types/api";
import { Sidebar } from "../components/Sidebar";
import { TopNavbar } from "../components/Navbar";
import { api } from "../services/api";

/** Authenticated shell. Polls the unread-alert count (cheap endpoint) so the badge stays fresh. */
export function AppLayout({ user, children, onSignOut }: PropsWithChildren<{ user: User; onSignOut: () => void }>) {
  const [unread, setUnread] = useState(0);
  const [openReminders, setOpenReminders] = useState(0);
  const route = useRoute();
  useEffect(() => {
    let live = true;
    const loadUnread = () => api<{ count: number }>("/alerts/unread-count").then((r) => live && setUnread(r.count)).catch(() => undefined);
    const loadOpenReminders = () => api<{ count: number }>("/reminders/open-count").then((r) => live && setOpenReminders(r.count)).catch(() => undefined);
    const load = () => { loadUnread(); loadOpenReminders(); };
    load();
    const timer = window.setInterval(load, 60_000);
    window.addEventListener("rl:reminders-changed", loadOpenReminders);
    window.addEventListener("rl:notifications-seen", loadUnread);
    return () => { live = false; window.clearInterval(timer); window.removeEventListener("rl:reminders-changed", loadOpenReminders); window.removeEventListener("rl:notifications-seen", loadUnread); };
  }, [route]);
  return (
    <div className="app-shell">
      <Sidebar user={user} openReminders={openReminders} onSignOut={onSignOut} />
      <div className="main-column">
        <TopNavbar unread={unread} />
        {children}
      </div>
    </div>
  );
}
