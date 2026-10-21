import { useState, type FormEvent } from "react";
import { Actions, Badge, Button, Card, Empty, ErrorNotice, FormField, Input, Loader, Page, PageHeader } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, formatDate, todayISO } from "../services/api";
import type { Reminder, WorkspaceSettings } from "../types/api";

export function RemindersPage() {
  const resource = useResource<Reminder[]>("/reminders");
  const settings = useResource<WorkspaceSettings>("/settings");
  const { run, confirm } = useFeedback();
  const [busy, setBusy] = useState(false);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const f = new FormData(form);
    setBusy(true);
    const ok = await run(() => api("/reminders", { method: "POST", json: { title: f.get("title"), due: f.get("due"), lead: Number(f.get("lead")) } }), "Reminder added");
    setBusy(false);
    if (ok) { form.reset(); resource.reload(); window.dispatchEvent(new Event("rl:reminders-changed")); }
  }
  const toggle = async (r: Reminder) => { if (await run(() => api(`/reminders/${r.id}`, { method: "PATCH", json: { done: !r.done } }))) { resource.reload(); window.dispatchEvent(new Event("rl:reminders-changed")); } };
  async function remove(r: Reminder) {
    if (!(await confirm("Delete reminder?", `“${r.title}” will be removed.`))) return;
    if (await run(() => api(`/reminders/${r.id}`, { method: "DELETE" })) !== undefined) { resource.reload(); window.dispatchEvent(new Event("rl:reminders-changed")); }
  }

  return (
    <Page>
      <PageHeader title="Reminders" description="Keep track of upcoming compliance tasks and reminder notifications." />
      <Card>
        <form onSubmit={create}>
          <div className="grid grid-2">
            <FormField label="Reminder"><Input name="title" required maxLength={160} /></FormField>
            <FormField label="Due date"><Input name="due" type="date" required min={todayISO()} /></FormField>
            <FormField label="Notify days before"><Input key={settings.data?.default_lead} name="lead" type="number" min="0" max="30" defaultValue={settings.data?.default_lead ?? 3} /></FormField>
          </div>
          <Button type="submit" loading={busy}>Add reminder</Button>
        </form>
      </Card>
      <div className="section">
        <ErrorNotice error={resource.error} />
        {!resource.data ? <Loader /> : resource.data.length ? resource.data.map((r) => (
          <Card key={r.id}>
            <div className="row between">
              <div><b style={{ textDecoration: r.done ? "line-through" : "none" }}>{r.title}</b><p className="muted">Due {formatDate(r.due)} · notification {r.lead} days before</p></div>
              <Badge tone={r.done ? "soft" : "default"}>{r.done ? "Done" : "Open"}</Badge>
            </div>
            <Actions>
              <Button size="sm" variant="secondary" onClick={() => toggle(r)}>{r.done ? "Reopen" : "Mark done"}</Button>
              <Button size="sm" variant="danger" onClick={() => remove(r)}>Delete</Button>
            </Actions>
          </Card>
        )) : <Empty>No reminders yet.</Empty>}
      </div>
    </Page>
  );
}
