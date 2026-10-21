import { useState, type FormEvent } from "react";
import { Actions, Button, Card, Empty, ErrorNotice, FormField, Input, Loader, Page, PageHeader, Select } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, downloadFile, formatDate } from "../services/api";
import type { Report } from "../types/api";

export function ReportsPage() {
  const resource = useResource<Report[]>("/reports");
  const { run } = useFeedback();
  const [busy, setBusy] = useState(false);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    const ok = await run(() => api("/reports", { method: "POST", json: { name: data.get("name"), kind: data.get("kind") } }), "Report created");
    setBusy(false);
    if (ok) { form.reset(); resource.reload(); }
  }

  return (
    <Page>
      <PageHeader title="Reports" description="Generate a point-in-time PDF from your workspace data." />
      <Card>
        <form onSubmit={create}>
          <div className="grid grid-2">
            <FormField label="Report name"><Input name="name" required maxLength={160} /></FormField>
            <FormField label="Report type"><Select name="kind"><option>Compliance summary</option><option>Risk review</option><option>Regulation updates</option></Select></FormField>
          </div>
          <Button type="submit" loading={busy}>Create report</Button>
        </form>
      </Card>
      <div className="section">
        <ErrorNotice error={resource.error} />
        {!resource.data ? <Loader /> : resource.data.length ? resource.data.map((item) => (
          <Card key={item.id}>
            <div className="row between">
              <div><b>{item.name}</b><p className="muted">{item.kind} · {item.created_by_name} · {formatDate(item.created_at)}</p></div>
              <Actions><Button size="sm" variant="outline" onClick={() => run(() => downloadFile(`/reports/${item.id}/pdf`, `report-${item.id}.pdf`))}>Download PDF</Button></Actions>
            </div>
          </Card>
        )) : <Empty>No reports yet.</Empty>}
      </div>
    </Page>
  );
}
