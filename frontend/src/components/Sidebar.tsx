
import type { User } from "../types/api";
import { Link } from "../router";
import { Icon } from "./Icon";

type SidebarProps = {
  user: User;
  openReminders: number;
  onSignOut: () => void;
};

const navigationGroups = [
  {
    label: "OVERVIEW",
    items: [
      { id: "home", label: "Dashboard", href: "#/home", icon: "home" },
      { id: "ask", label: "AI Assistant", href: "#/ask", icon: "ask" },
    ],
  },
  {
    label: "COMPLIANCE",
    items: [
      {
        id: "regulations",
        label: "Regulatory Library",
        href: "#/regulations",
        icon: "regulations",
      },
      {
        id: "business",
        label: "Business Profile",
        href: "#/business",
        icon: "business",
      },
      {
        id: "assessments",
        label: "Assessments",
        href: "#/assessments",
        icon: "assessments",
      },
      {
        id: "risk",
        label: "Risk & Reports",
        href: "#/risk",
        icon: "risk",
      },
    ],
  },
  {
    label: "OPERATIONS",
    items: [
      {
        id: "reminders",
        label: "Reminders",
        href: "#/reminders",
        icon: "reminders",
      },
    ],
  },
];

export function Sidebar({
  user,
  openReminders,
  onSignOut,
}: SidebarProps) {
  const initial = (user.name || user.email)[0]?.toUpperCase() ?? "?";

  return (
    <aside className="sidebar">
      {/* Brand */}
      <Link href="#/home" className="brand">
        <span className="brand-mark">
          <Icon name="search" />
        </span>
        <span className="brand-name">RegLens AI</span>
      </Link>

      {/* Grouped navigation */}
      <nav className="sidebar-navigation" aria-label="Main navigation">
        {navigationGroups.map((group) => (
          <section className="sidebar-group" key={group.label}>
            <h2 className="sidebar-group-label">{group.label}</h2>

            <div className="sidebar-group-items">
              {group.items.map((item) => (
                <Link
                  key={item.id}
                  href={item.href}
                  className={`sidebar-link sidebar-link--${item.id}`}
                >
                  <Icon name={item.icon} />
                  <span>{item.label}</span>

                  {item.id === "reminders" && openReminders > 0 && (
                    <span className="count-badge">
                      {openReminders > 99 ? "99+" : openReminders}
                    </span>
                  )}
                </Link>
              ))}
            </div>
          </section>
        ))}
      </nav>

      {/* Account at the bottom — no dropdown arrow */}
      <div className="sidebar-account">
        <span className="avatar" aria-hidden="true">
          {initial}
        </span>

        <div className="sidebar-account-info">
          <b>{user.workspace_name || user.name || user.email}</b>
          <small>
            {user.name || user.email}
          </small>
        </div>
        <button
          type="button"
          className="icon-button"
          onClick={onSignOut}
          aria-label="Log out"
          title="Log out"
        >
          <Icon name="logout" />
        </button>
      </div>
    </aside>
  );
}
