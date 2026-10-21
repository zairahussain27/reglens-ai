import type { FormEvent } from "react";
import { Button, Card, FormField, Input, Page, PageHeader } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { auth } from "../services/api";
import type { User } from "../types/api";

export function ProfilePage({ user, onUserChange, onSignOut }: {
  user: User;
  onUserChange: (user: User) => void;
  onSignOut: () => void;
}) {
  const { run } = useFeedback();

  async function saveName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = String(new FormData(event.currentTarget).get("name") || "").trim();
    const updated = await run(() => auth.updateProfile(name), "Profile updated");
    if (updated) onUserChange(updated);
  }
  async function password(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const f = new FormData(form);
    const ok = await run(() => auth.changePassword(String(f.get("current") || ""), String(f.get("new") || "")), "Password changed");
    if (ok) form.reset();
  }

  return (
    <Page>
      <PageHeader title="Profile" description="Manage your account details and password." />
      <Card>
        <h2>Account</h2>
        <p className="muted">{user.email} · {user.role} · {user.google ? "Google connected" : "Email account"}</p>
        <form onSubmit={saveName}>
          <FormField label="Name"><Input name="name" required maxLength={120} defaultValue={user.name} /></FormField>
          <Button type="submit">Save name</Button>
        </form>
      </Card>
      <Card>
        <h2>{user.has_password ? "Change password" : "Set a password"}</h2>
        <form onSubmit={password}>
          {user.has_password && <FormField label="Current password"><Input type="password" name="current" required autoComplete="current-password" /></FormField>}
          <FormField label="New password" hint="At least 8 characters"><Input type="password" name="new" minLength={8} maxLength={128} required autoComplete="new-password" /></FormField>
          <Button type="submit">{user.has_password ? "Change password" : "Set password"}</Button>
        </form>
      </Card>
      <Card>
        <h2>Sign out</h2>
        <p className="muted">Sign out of this RegLens AI session on this device.</p>
        <Button type="button" variant="danger" onClick={onSignOut}>Log out</Button>
      </Card>
    </Page>
  );
}
