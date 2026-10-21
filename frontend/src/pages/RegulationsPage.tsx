import { useMemo, useState, type FormEvent } from "react";
import { Actions, Badge, Button, Card, Empty, ErrorNotice, FormField, Input, Loader, Page, PageHeader, Select } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, downloadFile, formatDate } from "../services/api";
import type { Regulation, User } from "../types/api";
import { Highlight } from "../components/Highlight";

const REGULATORS = ["RBI", "SEBI", "IRDAI", "NPCI", "MeitY", "CBIC / GST", "Other"];

function RegulatorFields() {
  return <>
    <FormField label="Regulator"><Select name="regulator" defaultValue="RBI">{REGULATORS.map((x) => <option key={x}>{x}</option>)}</Select></FormField>
    <FormField label="Issue date"><Input name="issued_on" type="date" /></FormField>
  </>;
}

export function RegulationsPage({ user }: { user: User }) {
  const resource = useResource<Regulation[]>("/regulations");
  const { run, confirm } = useFeedback();
  const [busy, setBusy] = useState<"file" | "url" | "seed" | null>(null);
  const initialQuery = new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("q") ?? "";
  const [query, setQuery] = useState(initialQuery);
  const [regulator, setRegulator] = useState("");
  const isAdmin = user.email.toLowerCase() === "zairahussain27@gmail.com";

  const items = useMemo(() => (resource.data ?? []).filter((r) =>
    (!regulator || r.regulator === regulator) && (!query || `${r.title} ${r.summary} ${r.regulator}`.toLowerCase().includes(query.toLowerCase()))), [resource.data, query, regulator]);

  async function submitFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy("file");
    const ok = await run(() => api("/regulations", { method: "POST", body: new FormData(form) }), "Regulation uploaded and indexed");
    setBusy(null);
    if (ok) { form.reset(); resource.reload(); }
  }

  async function addUrl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy("url");
    const ok = await run(() => api("/regulations/from-url", { method: "POST", json: {
      url: data.get("url"), title: data.get("title"), regulator: data.get("regulator"), issued_on: data.get("issued_on") || null } }), "Regulation imported");
    setBusy(null);
    if (ok) { form.reset(); resource.reload(); }
  }

  async function seed() {
    setBusy("seed");
    const r = await run(() => api<{ added: number }>("/regulations/seed-ingest", { method: "POST" }));
    setBusy(null);
    if (r) { resource.reload(); }
  }

  async function remove(item: Regulation) {
    if (!(await confirm("Delete regulation?", `“${item.title}” and its indexed text will be removed from Ask.`))) return;
    if (await run(() => api(`/regulations/${item.id}`, { method: "DELETE" }), "Regulation deleted") !== undefined) resource.reload();
  }

  return (
    <Page>
      <PageHeader title="Regulations" description="Government regulations used by Ask and assessments." />
      {isAdmin && (
        <Card>
          <h2>Add a regulation</h2>
          <form onSubmit={submitFile}>
            <div className="grid grid-2">
              <FormField label="PDF or TXT file"><Input name="file" type="file" accept=".pdf,.txt" required /></FormField>
              <FormField label="Title (optional)"><Input name="title" maxLength={300} /></FormField>
              <RegulatorFields />
            </div>
            <Button type="submit" loading={busy === "file"}>Upload and index</Button>
          </form>
          <hr className="rule" />
          <form onSubmit={addUrl}>
            <div className="grid grid-2">
              <FormField label="Regulation URL" hint="PDF, HTML or text page"><Input name="url" type="url" required /></FormField>
              <FormField label="Title"><Input name="title" maxLength={300} /></FormField>
              <RegulatorFields />
            </div>
            <Button type="submit" variant="secondary" loading={busy === "url"}>Import from URL</Button>
          </form>
        </Card>
      )}
      <div className="toolbar section">
        <Input className="control" placeholder="Search regulations…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search regulations" />
        <Select value={regulator} onChange={(e) => setRegulator(e.target.value)} aria-label="Filter by regulator">
          <option value="">All regulators</option>{REGULATORS.map((x) => <option key={x}>{x}</option>)}
        </Select>
        {isAdmin && <Button variant="outline" size="sm" loading={busy === "seed"} onClick={seed}>Load platform regulations</Button>}
      </div>
      <ErrorNotice error={resource.error} />
      {!resource.data ? <Loader /> : items.length ? (
        <div className="grid">{items.map((item) => (
          <Card key={item.id}>
            <div className="row between top">
              <div>
                <b><Highlight text={item.title} query={query} /></b>
                <p className="muted"><Highlight text={item.summary || item.ingestion_error || "Processing…"} query={query} /></p>
                <small className="muted">{item.regulator} · {formatDate(item.issued_on || item.created_at)}{!item.own && " · Platform library"}</small>
              </div>
              <div className="chips" style={{ margin: 0 }}>
                <Badge tone={item.status === "ready" ? "soft" : "default"}>{item.status}</Badge>
                {item.applicable && <Badge>Applies to your profile</Badge>}
              </div>
            </div>
            <Actions>
              {item.source_url && <a className="button button-outline button-sm" href={item.source_url} target="_blank" rel="noreferrer">Source</a>}
              {item.has_file && <Button size="sm" variant="outline" onClick={() => run(() => downloadFile(`/regulations/${item.id}/file`, item.title))}>Download</Button>}
              {isAdmin && item.own && <Button size="sm" variant="danger" onClick={() => remove(item)}>Delete</Button>}
            </Actions>
          </Card>
        ))}</div>
      ) : <Empty>{resource.data.length ? "No regulations match your search." : "No regulations yet."}</Empty>}
    </Page>
  );
}
