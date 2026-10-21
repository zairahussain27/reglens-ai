
import { useState, type FormEvent } from "react";
import { Link } from "../router";
import { navigate } from "../router";
import { Icon } from "./Icon";

type TopNavbarProps = {
  unread?: number;
  onSearch?: (query: string) => void;
};

export function TopNavbar({
  unread = 0,
  onSearch,
}: TopNavbarProps) {
  const [query, setQuery] = useState("");

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    if (!value) return;
    if (onSearch) onSearch(value);
    else navigate(`search?q=${encodeURIComponent(value)}`);
  }

  return (
    <header className="top-navbar">
      <form
        className="top-navbar__search"
        role="search"
        onSubmit={handleSearch}
      >
        <Icon name="search" />

        <input
          type="search"
          placeholder="Search regulations, documents, assessments..."
          aria-label="Search regulations, documents, and assessments"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />

        <span className="top-navbar__shortcut">
          <kbd>Ctrl</kbd>
          <kbd>K</kbd>
        </span>
      </form>

      <div className="top-navbar__actions">
        <Link
          href="#/notifications"
          className="top-navbar__icon-button"
          aria-label={`Notifications${unread ? `, ${unread} unread reminders` : ""}`}
        >
          <Icon name="alerts" />

          {unread > 0 && (
            <span className="top-navbar__notification-dot" />
          )}
        </Link>

        <Link
          className="top-navbar__icon-button"
          href="#/help"
          aria-label="Help and support"
        >
          <Icon name="help" />
        </Link>

        <Link
          href="#/profile"
          className="top-navbar__avatar"
          aria-label="View profile"
        >
          Z
        </Link>
      </div>
    </header>
  );
}
