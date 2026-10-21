import { useState, type FormEvent } from "react";
import { Actions, Badge, Button, Card, Empty, ErrorNotice, FormField, Input, Kpi, Loader, Modal, Page, PageHeader, Select } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, formatDate, todayISO } from "../services/api";
import type { Reminder, RiskData, RiskRow, WorkspaceSettings } from "../types/api";

export function RiskPage() {
  const resource = useResource<RiskData>("/risk");
  const settings = useResource<WorkspaceSettings>("/settings");
  const { run, confirm } = useFeedback();
  const [selectedRisk, setSelectedRisk] = useState<RiskRow | null>(null);
  const [reminderDue, setReminderDue] = useState(todayISO());
  const [busy, setBusy] = useState(false);
  const data = resource.data;

  const patch = async (id: number, body: object) => { if (await run(() => api(`/risk/${id}`, { method: "PATCH", json: body }))) resource.reload(); };
  async function remove(id: number, title: string) {
    if (!(await confirm("Delete risk?", `“${title}” will be removed from the register.`))) return;
    if (await run(() => api(`/risk/${id}`, { method: "DELETE" }), "Risk deleted") !== undefined) resource.reload();
  }
  function openReminder(risk: RiskRow) {
    const today = todayISO();
    setReminderDue(risk.due && risk.due >= today ? risk.due : today);
    setSelectedRisk(risk);
  }
  async function createReminder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedRisk) return;
    setBusy(true);
    const reminder = await run(() => api<Reminder>("/reminders", {
      method: "POST",
      json: {
        title: `Follow up: ${selectedRisk.title}`.slice(0, 160),
        due: reminderDue,
        lead: settings.data?.default_lead ?? 3,
      },
    }), "Reminder added");
    setBusy(false);
    if (reminder) {
      setSelectedRisk(null);
      window.dispatchEvent(new Event("rl:reminders-changed"));
    }
  }

  return (
    <Page>
      <PageHeader title="Risk dashboard" description="Review assessment risk values and track identified risks." />
      <ErrorNotice error={resource.error} />
      {!data ? <Loader /> : <>
        <div className="kpis">
          <Kpi value={data.assessment?.risk_score == null ? "Not yet calculated" : `${data.assessment.risk_score}%`}
            label={data.assessment?.estimated ? "Estimated risk score" : "Latest assessment risk"} hint={data.assessment ? `${data.assessment.risk_level} · ${formatDate(data.assessment.created_at)}` : "Start an assessment to calculate risk"} />
          <Kpi value={data.open} label="Unresolved items" />
          <Kpi value={data.overdue} label="Overdue" />
          <Kpi value={data.overall} label="Register level" />
        </div>
        {data.assessment?.estimated && <Card className="section">
          <b>Why this is an estimate</b>
          <p>It reflects uncertainty and potential compliance gaps. Findings with unknown applicability are included as potential risk contributors, not counted as confirmed applicable regulations. This score does not mean non-compliance has been confirmed.</p>
          <p className="muted">Contributors: {data.assessment.applicable_count} confirmed applicable · {data.assessment.unknown_applicability_count} applicability unknown · {data.assessment.unassessed_count} compliance status unassessed.</p>
          <p className="muted">{data.assessment.formula}</p>
          <h3>Regulations contributing to the estimate</h3>
          <div className="stack">{data.assessment.contributors.map((item, index) => <Card key={`${item.title}-${index}`}>
            <div className="row between top"><b>{item.title}</b><Badge tone={item.applicability === "Unknown" ? "soft" : "default"}>{item.applicability === "Unknown" ? "Applicability unknown" : "Applicable"}</Badge></div>
            <p>{item.score}/100 · Severity {item.severity} · Likelihood {item.likelihood} · Compliance {item.compliance_status}</p>
            <p className="muted">{item.reason}</p>
          </Card>)}</div>
        </Card>}
        <div className="section">
          <h2>Risk register</h2>
          <p className="muted">Confirmed compliance issues are separated from unresolved items that still need review. Applicability unknown is never treated as confirmed applicable.</p>
          {data.register.length > 0 && <div className="chips">
            <Badge>{data.register.filter((risk) => risk.classification === "confirmed").length} confirmed issues</Badge>
            <Badge tone="soft">{data.register.filter((risk) => risk.classification === "review").length} need review</Badge>
          </div>}
          {data.by_area.length > 0 && <div className="chips">{data.by_area.map((x) => <Badge key={x.area} tone="soft">{x.area}: {x.score}%</Badge>)}</div>}
          {data.register.length ? data.register.map((risk) => (
            <Card key={risk.id}>
              <div className="row between top">
                <div>
                  <b>{risk.title}</b>
                  <p className="muted">{risk.area} · {risk.level} · {risk.source} · {risk.owner || "Unassigned"} · Due {formatDate(risk.due)}</p>
                </div>
                <div className="chips" style={{ margin: 0 }}>
                  <Badge tone={risk.status === "Resolved" || risk.ignored || risk.classification === "review" ? "soft" : "default"}>{risk.ignored ? "Ignored" : risk.classification === "review" ? "Needs review" : "Confirmed issue"}</Badge>
                  {risk.compliance_status && <Badge tone="soft">{risk.compliance_status}</Badge>}
                </div>
              </div>
              <Actions>
                {!risk.ignored && <>
                  <Select aria-label="Risk status" value={risk.status} onChange={(e) => patch(risk.id, { status: e.target.value })} style={{ width: "auto" }}>
                    <option>Open</option><option>In progress</option><option>Resolved</option>
                  </Select>
                  <Select aria-label="Risk owner" value={risk.owner_id ?? ""} onChange={(e) => patch(risk.id, { owner_id: e.target.value ? Number(e.target.value) : null })} style={{ width: "auto" }}>
                    <option value="">Unassigned</option>{data.members.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                  </Select>
                </>}
                <Button size="sm" variant="secondary" onClick={() => openReminder(risk)}>Add reminder</Button>
                {risk.source_ref && <Button size="sm" variant="outline" onClick={() => patch(risk.id, { ignored: !risk.ignored })}>{risk.ignored ? "Unignore" : "Ignore"}</Button>}
                <Button size="sm" variant="danger" onClick={() => remove(risk.id, risk.title)}>Delete</Button>
              </Actions>
            </Card>
          )) : <Empty>{data.assessment ? "No applicable regulation risks have been added yet. Complete an assessment to add its applicable regulations here." : "No assessment found yet. Start and complete an assessment to review your business risks."}</Empty>}
        </div>
      </>}
      <Modal open={!!selectedRisk} title="Add risk reminder" onClose={() => setSelectedRisk(null)}>
        {selectedRisk && <form onSubmit={createReminder}>
          <p>Set a reminder to follow up on “{selectedRisk.title}”. It will also appear on the Reminders page.</p>
          <FormField label="Reminder due date">
            <Input type="date" min={todayISO()} value={reminderDue} onChange={(event) => setReminderDue(event.target.value)} required />
          </FormField>
          <p className="muted">Notification lead time: {settings.data?.default_lead ?? 3} days.</p>
          <div className="actions end">
            <Button type="button" variant="outline" onClick={() => setSelectedRisk(null)}>Cancel</Button>
            <Button type="submit" loading={busy}>Add reminder</Button>
          </div>
        </form>}
      </Modal>
    </Page>
  );
}
