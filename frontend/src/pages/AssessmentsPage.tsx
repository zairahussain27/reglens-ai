import { useState } from "react";
import { Badge, Button, Card, Checkbox, Empty, ErrorNotice, Loader, Page, PageHeader } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, formatDate } from "../services/api";
import type { Assessment, Finding, Regulation } from "../types/api";
import { Highlight } from "../components/Highlight";

const pct = (n: number | null) => (n == null ? "Not yet calculated" : `${n}%`);

function FindingCard({ finding }: { finding: Finding }) {
  const tone = finding.applicability === "Applicable" ? "default" : "soft";
  return (
    <Card>
      <div className="row between top">
        <h3 style={{ margin: 0 }}>{finding.title}</h3>
        <Badge tone={tone}>{finding.applicability}</Badge>
      </div>
      {finding.source_url && <p><a className="auth-link" href={finding.source_url} target="_blank" rel="noreferrer">Open regulation source</a></p>}

      <div className="grid grid-2 section">
        <div>
          <b>Why this decision</b>
          <p>{finding.applicability_reason || "No applicability explanation is available."}</p>
        </div>
        <div>
          <b>Compliance status</b>
          <p>{finding.compliance_status === "Unable to Determine" ? "Unable to determine" : finding.compliance_status}{finding.ai_evaluated ? " · AI evaluated" : " · Not AI evaluated"}</p>
          {finding.ai_evaluated && finding.ai_confidence != null && <p className="muted">AI confidence: {Math.round(finding.ai_confidence * 100)}%</p>}
        </div>
      </div>

      {finding.ai_summary && <div><b>AI assessment summary</b><p>{finding.ai_summary}</p></div>}
      {finding.ai_findings.length > 0 && <div className="section">
        <b>Structured obligation findings</b>
        <div className="stack">{finding.ai_findings.map((item, index) => <div key={`${item.requirement}-${index}`}>
          <div className="row between"><b>{item.requirement}</b><Badge tone={item.status === "Non-Compliant" ? "default" : "soft"}>{item.status}</Badge></div>
          <p>{item.reasoning}</p>
          {item.evidence && <p className="muted">Evidence: “{item.evidence}” {item.source && `· ${item.source}`}</p>}
        </div>)}</div>
      </div>}

      {finding.missing_info.length > 0 && (
        <div>
          <b>Business information to confirm</b>
          <ul>{finding.missing_info.map((item, i) => <li key={i}>{item.question}</li>)}</ul>
        </div>
      )}

      <div className="section">
        <b>Compliance gap</b>
        <p>{finding.compliance_gap}</p>
      </div>

      <div>
        <b>Risk contribution</b>
        <p>{finding.risk_contribution}/100 · {finding.risk_reason}</p>
      </div>

      <div>
        <b>Recommended next step</b>
        <p>{finding.action_recommendation}</p>
      </div>

      {finding.due_on && <p className="muted">Recorded due date: {formatDate(finding.due_on)}</p>}
    </Card>
  );
}

export function AssessmentsPage() {
  const list = useResource<Assessment[]>("/assessments");
  const regulations = useResource<Regulation[]>("/regulations");
  const { run, success } = useFeedback();
  const [active, setActive] = useState<Assessment>();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const published = (regulations.data ?? []).filter((regulation) => regulation.status === "ready");
  const query = new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("q")?.trim() ?? "";
  const needle = query.toLocaleLowerCase();
  const assessments = (list.data ?? []).filter((assessment) => !query ||
    `assessment ${assessment.id} ${assessment.status} ${assessment.risk_level} ${assessment.critical_missing.join(" ")}`.toLocaleLowerCase().includes(needle));

  async function start() {
    setBusy(true);
    const assessment = await run(() => api<Assessment>("/assessments", {
      method: "POST", json: { regulation_ids: selectedIds },
    }), "Assessment created");
    setBusy(false);
    if (assessment) {
      setActive(assessment);
      list.reload();
    }
  }

  async function open(id: number) {
    const assessment = await run(() => api<Assessment>(`/assessments/${id}`));
    if (assessment) setActive(assessment);
  }

  async function completeActive() {
    if (!active) return;
    const assessment = await run(() => api<Assessment>(`/assessments/${active.id}/complete`, { method: "POST" }), "Assessment completed; applicable regulations added to the Risk dashboard");
    if (assessment) {
      setActive(assessment);
      list.reload();
      window.dispatchEvent(new Event("rl:assessment-completed"));
    }
  }

  async function evaluateActive() {
    if (!active) return;
    setBusy(true);
    const result = await run(() => api<Assessment & { ai_evaluated_now?: number }>(`/assessments/${active.id}/evaluate`, { method: "POST" }));
    setBusy(false);
    if (result) {
      setActive(result);
      list.reload();
      window.dispatchEvent(new Event("rl:assessment-completed"));
      if (result.ai_evaluated_now) success(`${result.ai_evaluated_now} regulation${result.ai_evaluated_now === 1 ? "" : "s"} AI evaluated; compliance score updated`);
      else success("No findings were evaluated. Check that an AI provider is configured and regulation text is indexed.");
    }
  }

  const counts = active?.counts ?? {};
  return (
    <Page>
      <PageHeader
        title="Assessments"
        description="Read how each regulation relates to your business. Applicable regulations are added to the Risk dashboard as soon as they are marked."
        action={<Button loading={busy} disabled={!selectedIds.length || !published.length} onClick={start}>Start assessment</Button>}
      />
      <ErrorNotice error={list.error} />
      <ErrorNotice error={regulations.error} />
      <Card>
        <div className="row between top">
          <div>
            <h2 style={{ marginTop: 0 }}>Regulations to assess</h2>
            <p className="muted">Choose the published regulations for this assessment. {selectedIds.length} selected.</p>
          </div>
          <div className="actions">
            <Button type="button" size="sm" variant="outline" disabled={!published.length}
              onClick={() => setSelectedIds(published.map((regulation) => regulation.id))}>Select all</Button>
            <Button type="button" size="sm" variant="outline" disabled={!selectedIds.length}
              onClick={() => setSelectedIds([])}>Clear</Button>
          </div>
        </div>
        {!regulations.data ? <Loader /> : published.length ? (
          <div className="stack">
            {published.map((regulation) => (
              <Checkbox key={regulation.id} label={`${regulation.title} · ${regulation.regulator}`}
                checked={selectedIds.includes(regulation.id)}
                onChange={(event) => setSelectedIds((current) => event.target.checked
                  ? [...current, regulation.id]
                  : current.filter((id) => id !== regulation.id))} />
            ))}
          </div>
        ) : <Empty>No published regulations are available to assess.</Empty>}
      </Card>
      {!list.data ? <Loader /> : assessments.length ? (
        <div className="grid grid-2">{assessments.map((assessment) => (
          <Card key={assessment.id}>
            <b><Highlight text={`Assessment #${assessment.id}`} query={query} /></b>
            <p className="muted">{formatDate(assessment.created_at)} · {assessment.status}</p>
            <p>Compliance {pct(assessment.compliance_score)} · Risk {pct(assessment.risk_score)} · {assessment.risk_level}</p>
            <Button size="sm" variant="outline" onClick={() => open(assessment.id)}>View assessment</Button>
          </Card>
        ))}</div>
      ) : <Empty>{list.data.length ? `No assessments match “${query}”.` : "No assessments yet. Start one to review regulations against your business profile."}</Empty>}

      {active && (
        <section className="section">
          <PageHeader
            title={`Assessment #${active.id}`}
            description={`${formatDate(active.created_at)} · ${active.status} · Compliance ${pct(active.compliance_score)} · Risk ${pct(active.risk_score)}`}
            action={<div className="actions"><Badge tone={active.risk_level === "High" ? "default" : "soft"}>{active.risk_level} risk</Badge>{active.findings?.some((finding) => finding.applicability === "Applicable" && !finding.ai_evaluated) && <Button loading={busy} onClick={evaluateActive}>Run AI evaluation</Button>}{active.status !== "complete" && <Button variant="outline" onClick={completeActive}>Complete assessment</Button>}</div>}
          />
          <Card>
            <h3 style={{ marginTop: 0 }}>Compliance score</h3>
            <p className="muted">AI evaluates each applicable regulation against its indexed text, the business profile, and enabled evidence documents. The score averages points across scored AI obligation findings (or a manually confirmed status when AI findings are unavailable). Unable to Determine and applicability-unknown findings are excluded.</p>
            {active.findings?.some((finding) => finding.applicability === "Applicable" && !finding.ai_evaluated) && <p className="muted">Some applicable findings could not be AI evaluated because a regulation passage or AI response was unavailable. They remain Unable to Determine and are excluded from the score.</p>}
            <div className="table-wrap">
              <table>
                <thead><tr><th>Compliance status</th><th>Score</th></tr></thead>
                <tbody>
                  <tr><td>Compliant</td><td>100</td></tr>
                  <tr><td>Partially Compliant</td><td>50</td></tr>
                  <tr><td>Non-Compliant</td><td>0</td></tr>
                  <tr><td>Unable to Determine</td><td>Excluded until assessed</td></tr>
                  <tr><td>Not Applicable</td><td>Excluded</td></tr>
                </tbody>
              </table>
            </div>
          </Card>
          <Card>
            <b>Risk score: {pct(active.risk_score)} · {active.risk_level}</b>
            {active.risk_estimated && <p>This is an estimate reflecting uncertainty and potential compliance gaps, not confirmed non-compliance. Findings with unknown applicability contribute as potential risk but are not counted as confirmed applicable regulations.</p>}
            <p className="muted">{active.risk_formula}</p>
            <p className="muted">{active.applicable_count} confirmed applicable · {active.unknown_applicability_count} applicability unknown · {active.unassessed_count} compliance status unassessed.</p>
            <b>Regulations contributing to this score</b>
            <div className="stack section">{active.risk_contributors.map((item, index) => <div key={`${item.title}-${index}`}>
              <b>{item.title}</b>
              <p>{item.score}/100 · {item.applicability === "Unknown" ? "Applicability unknown (potential contributor)" : item.applicability} · Severity {item.severity} · Likelihood {item.likelihood} · Compliance {item.compliance_status}</p>
              <p className="muted">{item.reason}</p>
            </div>)}</div>
          </Card>
          <div className="chips">
            <Badge>Applicable {counts.applicable || 0}</Badge>
            <Badge tone="soft">Not applicable {counts.not_applicable || 0}</Badge>
            <Badge tone="soft">Unknown {counts.unknown || 0}</Badge>
            <Badge tone={counts.evidence_gaps ? "default" : "soft"}>Evidence gaps {counts.evidence_gaps || 0}</Badge>
          </div>
          {active.critical_missing.length > 0 && (
            <Card><b>Business profile information to complete</b><p>{active.critical_missing.join(", ")}</p></Card>
          )}
          <div className="stack">
            {active.findings?.map((finding) => <FindingCard key={finding.id} finding={finding} />)}
          </div>
        </section>
      )}
    </Page>
  );
}
