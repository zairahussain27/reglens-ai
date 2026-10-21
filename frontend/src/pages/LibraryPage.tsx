import { useState, type FormEvent } from "react";
import { Actions, Badge, Button, Card, Empty, ErrorNotice, FormField, Input, Loader, Page, PageHeader, Select } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, downloadFile, formatDate } from "../services/api";
import type { Document } from "../types/api";
import { Highlight } from "../components/Highlight";

export function LibraryPage() {
  const resource = useResource<Document[]>("/documents");
  const { run, confirm } = useFeedback();
  const [busy, setBusy] = useState(false);
  const query = new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("q")?.trim() ?? "";
  const needle = query.toLocaleLowerCase();
  const documents = (resource.data ?? []).filter((item) => !query || `${item.name} ${item.kind} ${item.status}`.toLocaleLowerCase().includes(needle));

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(true);
    const doc = await run(() => api<Document>("/documents", { method: "POST", body: new FormData(form) }));
    setBusy(false);
    if (!doc) return;
    form.reset();
    resource.reload();
  }

  async function toggle(item: Document) {
    if (await run(() => api(`/documents/${item.id}`, { method: "PATCH", json: { use_in_ai: !item.use_in_ai } }), item.use_in_ai ? "Removed from Ask" : "Now used in Ask")) resource.reload();
  }

  async function remove(item: Document) {
    if (!(await confirm("Delete file?", `“${item.name}” will be permanently removed from your Library.`))) return;
    if (await run(() => api(`/documents/${item.id}`, { method: "DELETE" }), "File deleted") !== undefined) resource.reload();
  }

  return (
    <Page>
      <PageHeader title="Library" description="Your workspace files. They stay private to Ask unless you enable them." />
      <Card>
        <form onSubmit={upload}>
          <div className="grid grid-2">
            <FormField label="PDF or TXT file" hint="Up to 15 MB"><Input name="file" type="file" accept=".pdf,.txt" required /></FormField>
            <FormField label="Category"><Select name="kind" defaultValue="Policy"><option>Policy</option><option>Evidence</option><option>Regulation</option><option>Other</option></Select></FormField>
          </div>
          <Button type="submit" loading={busy}>Upload file</Button>
        </form>
      </Card>
      <div className="section">
        <ErrorNotice error={resource.error} />
        {!resource.data ? <Loader /> : documents.length ? documents.map((item) => (
          <Card key={item.id}>
            <div className="row between top">
              <div>
                <b><Highlight text={item.name} query={query} /></b>
                <p className="muted"><Highlight text={`${item.kind} · ${formatDate(item.created_at)}${item.status !== "ready" ? ` · ${item.status}` : ""}`} query={query} /></p>
                {item.error && <p className="muted" style={{ color: "var(--color-danger)" }}>{item.error}</p>}
              </div>
              <Badge tone={item.use_in_ai ? "default" : "soft"}>{item.use_in_ai ? "Used in Ask" : "Private"}</Badge>
            </div>
            <Actions>
              <Button size="sm" variant="outline" onClick={() => run(() => downloadFile(`/documents/${item.id}/file`, item.name))}>Download</Button>
              <Button size="sm" variant="secondary" disabled={item.status !== "ready"} onClick={() => toggle(item)}>{item.use_in_ai ? "Turn off in Ask" : "Use in Ask"}</Button>
              <Button size="sm" variant="danger" onClick={() => remove(item)}>Delete</Button>
            </Actions>
          </Card>
        )) : <Empty>{resource.data.length ? `No files match “${query}”.` : "No files yet. Upload a policy or evidence document above."}</Empty>}
      </div>
    </Page>
  );
}
