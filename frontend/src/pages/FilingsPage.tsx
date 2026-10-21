import { useMemo, useState, type FormEvent } from "react";
import { Actions, Badge, Button, Card, Empty, ErrorNotice, FormField, Input, Kpi, Loader, Page, PageHeader, Select, Table } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, downloadFile, formatDate, formatMoney } from "../services/api";
import type { FilingResponse } from "../types/api";

export function FilingsPage() {
  const resource = useResource<FilingResponse>("/filings");
  const { run, confirm } = useFeedback();
  const [busy, setBusy] = useState(false);
  const [fy, setFy] = useState("");

  const items = useMemo(() => (resource.data?.items ?? []).filter((i) => !fy || i.fy === fy), [resource.data, fy]);

  async function add(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    if (!(data.get("file") as File | null)?.name) data.delete("file");  // optional proof
    setBusy(true);
    const ok = await run(() => api("/filings", { method: "POST", body: data }), "Filing saved");
    setBusy(false);
    if (ok) { form.reset(); resource.reload(); }
  }

  const patch = async (id: number, body: object) => { if (await run(() => api(`/filings/${id}`, { method: "PATCH", json: body }))) resource.reload(); };

  async function remove(id: number) {
    if (!(await confirm("Delete filing?", "This filing and its proof will be permanently removed."))) return;
    if (await run(() => api(`/filings/${id}`, { method: "DELETE" }), "Filing deleted") !== undefined) resource.reload();
  }

  const s = resource.data?.summary;
  return (
    <Page>
      <PageHeader title="Filings" description="Track tax payments, returns, due dates, and proof."
        action={<Button variant="outline" onClick={() => run(() => downloadFile(`/filings/export/csv${fy ? `?fy=${encodeURIComponent(fy)}` : ""}`, "filings.csv"))}>Export CSV</Button>} />
      <Card>
        <h2>Add filing</h2>
        <form onSubmit={add}>
          <div className="grid grid-2">
            <FormField label="Type"><Select name="kind" required>{(resource.data?.kinds ?? []).map((x) => <option key={x}>{x}</option>)}</Select></FormField>
            <FormField label="Period"><Input name="period" placeholder="Apr 2026 or Q1 FY 2026-27" maxLength={80} /></FormField>
            <FormField label="Due date"><Input name="due_on" type="date" /></FormField>
            <FormField label="Status"><Select name="status" defaultValue="Pending"><option>Pending</option><option>Filed</option><option>Paid</option></Select></FormField>
            <FormField label="Amount (INR)"><Input name="amount" type="number" min="0" step="0.01" /></FormField>
            <FormField label="Paid on"><Input name="paid_on" type="date" /></FormField>
            <FormField label="Reference"><Input name="reference" maxLength={160} /></FormField>
            <FormField label="Proof (optional)" hint="PDF, image, CSV or XLSX"><Input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,.csv,.xlsx" /></FormField>
            <FormField label="Notes"><Input name="notes" maxLength={2000} /></FormField>
          </div>
          <Button type="submit" loading={busy} disabled={!resource.data}>Save filing</Button>
        </form>
      </Card>
      <div className="section">
        <ErrorNotice error={resource.error} />
        {!resource.data || !s ? <Loader /> : <>
          <div className="kpis" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
            <Kpi value={s.pending} label="Pending" /><Kpi value={s.overdue} label="Overdue" /><Kpi value={formatMoney(s.paid_total)} label="Paid / filed total" />
          </div>
          <div className="toolbar">
            <Select value={fy} onChange={(e) => setFy(e.target.value)} aria-label="Financial year filter" style={{ maxWidth: 240 }}>
              <option value="">All financial years</option>{resource.data.fys.map((y) => <option key={y} value={y}>FY {y}</option>)}
            </Select>
          </div>
          {items.length ? (
            <Card><Table>
              <thead><tr><th>Type</th><th>Period</th><th>Status</th><th>Due</th><th>Amount</th><th>Actions</th></tr></thead>
              <tbody>{items.map((item) => (
                <tr key={item.id}>
                  <td>{item.kind}</td><td>{item.period || "—"}</td>
                  <td><Badge tone={item.overdue ? "danger" : "soft"}>{item.overdue ? "Overdue" : item.status}</Badge></td>
                  <td>{formatDate(item.due_on)}</td><td>{item.amount == null ? "—" : formatMoney(item.amount)}</td>
                  <td><Actions>
                    {item.has_file && <Button size="sm" variant="outline" onClick={() => run(() => downloadFile(`/filings/${item.id}/file`, item.file_name || "proof"))}>Proof</Button>}
                    <Button size="sm" variant="secondary" onClick={() => patch(item.id, { status: item.status === "Pending" ? "Filed" : "Pending" })}>{item.status === "Pending" ? "Mark filed" : "Reopen"}</Button>
                    <Button size="sm" variant="danger" onClick={() => remove(item.id)}>Delete</Button>
                  </Actions></td>
                </tr>))}</tbody>
            </Table></Card>
          ) : <Empty>No filings{fy ? ` in FY ${fy}` : " yet"}.</Empty>}
        </>}
      </div>
    </Page>
  );
}
