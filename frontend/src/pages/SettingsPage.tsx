import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, Checkbox, ErrorNotice, FormField, Input, Loader, Page, PageHeader } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api } from "../services/api";
import type { User, WorkspaceSettings } from "../types/api";

const REGULATORS = ["RBI", "SEBI", "IRDAI", "NPCI", "MeitY", "CBIC / GST", "Other"];

export function SettingsPage({ user, onWorkspaceRenamed }: { user: User; onWorkspaceRenamed: (name: string) => void }) {
  const resource = useResource<WorkspaceSettings>("/settings");
  const { run } = useFeedback();
  const [s, setS] = useState<WorkspaceSettings>();
  const [busy, setBusy] = useState(false);
  const admin = user.role === "admin";
  useEffect(() => { if (resource.data) setS(resource.data); }, [resource.data]);

  if (!s) return <Page><PageHeader title="Settings" description="Workspace preferences." /><ErrorNotice error={resource.error} /><Loader /></Page>;
  const patch = (p: Partial<WorkspaceSettings>) => setS((cur) => (cur ? { ...cur, ...p } : cur));

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!s) return;
    setBusy(true);
    const saved = await run(() => api<WorkspaceSettings>("/settings", { method: "PUT", json: s }), "Settings saved");
    setBusy(false);
    if (saved) { setS(saved); onWorkspaceRenamed(saved.name); }
  }

  return (
    <Page>
      <PageHeader title="Settings" description="Workspace notification and regulator preferences." />
      <Card>
        <form onSubmit={save}>
          <fieldset disabled={!admin} style={{ margin: 0 }}>
            <FormField label="Workspace name"><Input value={s.name} onChange={(e) => patch({ name: e.target.value })} required maxLength={120} /></FormField>
            <fieldset>
              <legend>Follow regulators</legend>
              <div className="fieldset-grid">{REGULATORS.map((r) => (
                <Checkbox key={r} label={r} checked={s.regulators.includes(r)}
                  onChange={(e) => patch({ regulators: e.target.checked ? [...s.regulators, r] : s.regulators.filter((x) => x !== r) })} />
              ))}</div>
              <p className="hint">Your Home feed shows regulations from the regulators you follow.</p>
            </fieldset>
            <div className="stack">
              <Checkbox label="Email reminders" checked={s.reminders} onChange={(e) => patch({ reminders: e.target.checked })} />
              <Checkbox label="Regulation change alerts" checked={s.changes} onChange={(e) => patch({ changes: e.target.checked })} />
              <Checkbox label="Weekly summary" checked={s.weekly} onChange={(e) => patch({ weekly: e.target.checked })} />
            </div>
            <div style={{ marginTop: 16 }}>
              <FormField label="Default reminder lead time (days)">
                <Input type="number" min={0} max={30} value={s.default_lead} onChange={(e) => patch({ default_lead: Math.min(30, Math.max(0, Number(e.target.value) || 0)) })} />
              </FormField>
            </div>
          </fieldset>
          {admin ? <div className="actions" style={{ justifyContent: "flex-start" }}><Button type="submit" loading={busy}>Save workspace settings</Button></div>
            : <p className="muted">Only admins can change workspace settings.</p>}
        </form>
      </Card>
    </Page>
  );
}
