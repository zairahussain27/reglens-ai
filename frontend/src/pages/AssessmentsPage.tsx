import { useState } from "react";
import { Alert, Badge, Button, Card, Checkbox, Empty, ErrorNotice, Loader, Page, PageHeader, Select } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, errorMessage, formatDate, todayISO } from "../services/api";
import type { ActionItem, AiStatus, Assessment, EvaluateResult, Finding, Regulation } from "../types/api";
import { Highlight } from "../components/Highlight";
import { ScoreGauge } from "../components/ScoreGauge";

type Tab = "regulations" | "plan" | "method";
type Progress = { done: number; total: number; current: string };

const pct = (n: number | null | undefined) => (n == null ? "Not scored" : `${n}%`);
const statusLabel = (s: string) => (s === "Unable to Determine" ? "Needs evidence" : s);
const statusTone = (s: string) => (s === "Non-Compliant" ? "danger" : s === "Compliant" ? "default" : "soft");
const STATUSES = ["Unable to Determine", "Compliant", "Partially Compliant", "Non-Compliant"];
const DUE_DAYS: Record<string, number> = { Critical: 7, High: 14, Medium: 30, Low: 45 };
const addDays = (days: number) => { const d = new Date(); d.setDate(d.getDate() + days); return d.toISOString().slice(0, 10); };

function FindingCard({ finding, locked, busy, onEvaluate, onOverride }: {
  finding: Finding; locked: boolean; busy: boolean;
  onEvaluate: (f: Finding) => void; onOverride: (f: Finding, status: string) => void;
}) {
  const [open, setOpen] = useState(finding.applicability === "Applicable");
  const applicable = finding.applicability === "Applicable";
  return (
    <Card className="reg-card">
      <button type="button" className="reg-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <div>
          <h3>{finding.title}</h3>
          <div className="reg-meta">
            <Badge tone={applicable ? "default" : "soft"}>{finding.applicability}</Badge>
            {applicable && <Badge tone={statusTone(finding.compliance_status)}>{statusLabel(finding.compliance_status)}</Badge>}
            {applicable && !finding.ai_evaluated && <Badge tone="soft">Waiting for AI</Badge>}
            {finding.manual_override && <Badge tone="soft">Manually set</Badge>}
            {finding.ai_confidence != null && <span className="muted">AI confidence {Math.round(finding.ai_confidence * 100)}%</span>}
          </div>
        </div>
        <div className={`reg-score ${finding.score == null ? "muted-score" : ""}`}>{finding.score == null ? "—" : `${Math.round(finding.score)}%`}</div>
      </button>
      {open && (
        <div className="reg-body">
          <p className="muted" style={{ marginTop: 14 }}><b>Why this applies: </b>{finding.applicability_reason || "No explanation recorded."}</p>
          {finding.ai_summary && <p>{finding.ai_summary}</p>}
          {finding.ai_findings.length > 0 && (
            <div>
              <b>Obligations checked ({finding.assessed_obligations} of {finding.total_obligations} verified)</b>
              {finding.ai_findings.map((item, i) => (
                <div className="obl" key={`${item.requirement}-${i}`}>
                  <div className="obl-top">
                    <b>{item.requirement}</b>
                    <div className="actions">
                      <Badge tone="soft">{item.criticality}</Badge>
                      <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
                    </div>
                  </div>
                  {item.reasoning && <p className="muted">{item.reasoning}</p>}
                  {(item.evidence || item.evidence_refs?.length > 0) && (
                    <div className="obl-evidence">
                      {item.evidence ? <>“{item.evidence}” </> : null}
                      {item.evidence_refs?.length > 0 && <>· Evidence {item.evidence_refs.join(", ")}</>}
                      {item.citation && <> · Regulation passage {item.citation}</>}
                    </div>
                  )}
                  {item.action && item.status !== "Compliant" && <div className="obl-action"><b>Next step: </b>{item.action}</div>}
                </div>
              ))}
            </div>
          )}
          {finding.missing_info.length > 0 && (
            <div className="section"><b>Business information to confirm</b><ul>{finding.missing_info.map((m, i) => <li key={i}>{m.question}</li>)}</ul></div>
          )}
          {!locked && applicable && (
            <div className="row between section" style={{ flexWrap: "wrap", gap: 12 }}>
              <div className="actions">
                <Button size="sm" variant="outline" loading={busy} onClick={() => onEvaluate(finding)}>{finding.ai_evaluated ? "Re-run AI" : "Run AI"}</Button>
              </div>
              <label className="muted" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                Override status
                <Select value={finding.compliance_status} onChange={(e) => onOverride(finding, e.target.value)} style={{ width: "auto" }}>
                  {STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
                </Select>
              </label>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function ActionPlan({ items, locked, onRemind }: { items: ActionItem[]; locked: boolean; onRemind: (item: ActionItem) => void }) {
  if (!items.length) return <Card><Empty>No open actions. Run the AI evaluation to generate a prioritised plan.</Empty></Card>;
  return (
    <Card>
      <p className="muted" style={{ marginTop: 0 }}>Ordered by urgency × how critical the obligation is. “Needs evidence” items become compliant once you add proof to the Library or Filings and re-run the AI.</p>
      {items.map((item, i) => (
        <div className="plan-item" key={`${item.finding_id}-${i}`}>
          <Badge tone={item.priority === "Critical" || item.priority === "High" ? "danger" : "soft"}>{item.priority}</Badge>
          <div>
            <b>{item.requirement}</b>
            <p className="muted">{item.regulation} · {statusLabel(item.status)}</p>
            <p>{item.action}</p>
          </div>
          {!locked && <Button size="sm" variant="outline" onClick={() => onRemind(item)}>Add reminder</Button>}
        </div>
      ))}
    </Card>
  );
}

function AiBanner({ ai }: { ai?: AiStatus }) {
  if (!ai) return null;
  if (!ai.available) {
    return <Alert tone="error">AI scoring is off: no AI key is configured on the server. Add <b>GROQ_API_KEY</b> to the backend environment and redeploy. Until then, scores can only come from manual statuses.</Alert>;
  }
  return (
    <div className="row between" style={{ marginBottom: 16 }}>
      <span className="muted">AI engine: <b>{ai.provider}</b> · {ai.model}</span>
      {/* <Button size="sm" variant="outline" loading={checking} onClick={onCheck}>Test AI connection</Button> */}
    </div>
  );
}

export function AssessmentsPage() {
  const list = useResource<Assessment[]>("/assessments");
  const regulations = useResource<Regulation[]>("/regulations");
  const ai = useResource<AiStatus>("/assessments/ai-status");
  const { run, success, error } = useFeedback();
  const [active, setActive] = useState<Assessment>();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  // const [checking, setChecking] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [busyFinding, setBusyFinding] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("regulations");
  const published = (regulations.data ?? []).filter((r) => r.status === "ready");
  const query = new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("q")?.trim() ?? "";
  const needle = query.toLocaleLowerCase();
  const assessments = (list.data ?? []).filter((a) => !query ||
    `assessment ${a.id} ${a.status} ${a.risk_level} ${a.critical_missing.join(" ")}`.toLocaleLowerCase().includes(needle));
  const locked = active?.status === "complete";

  const refresh = (a: Assessment) => { setActive(a); list.reload(); window.dispatchEvent(new Event("rl:assessment-completed")); };

  /** Evaluate regulations one request each (2 at a time) so progress is visible and nothing times out. */
  async function evaluateAll(target: Assessment, force = false) {
    const todo = (target.findings ?? []).filter((f) => f.applicability !== "Not Applicable" && (force || !f.ai_evaluated));
    if (!todo.length) { success("Every applicable regulation has already been evaluated"); return; }
    setProgress({ done: 0, total: todo.length, current: todo[0].title });
    const failures: string[] = [];
    let next = 0;
    const worker = async () => {
      while (next < todo.length) {
        const f = todo[next++];
        setProgress((p) => p && { ...p, current: f.title });
        try {
          const r = await api<EvaluateResult>(`/assessments/${target.id}/findings/${f.id}/evaluate`, { method: "POST" });
          if (!r.ok && r.error) failures.push(r.error);
        } catch (e) { failures.push(errorMessage(e)); }
        setProgress((p) => p && { ...p, done: p.done + 1 });
      }
    };
    await Promise.all(Array.from({ length: Math.min(2, todo.length) }, worker));
    try {
      refresh(await api<Assessment>(`/assessments/${target.id}/rescore`, { method: "POST" }));
    } catch (e) { error(errorMessage(e)); }
    setProgress(null);
    if (failures.length) {
      const unique = [...new Set(failures)];
      error(`${failures.length} of ${todo.length} regulations could not be evaluated: ${unique[0]}${unique.length > 1 ? ` (+${unique.length - 1} other issue${unique.length > 2 ? "s" : ""})` : ""}`);
    } else success("AI evaluation finished; compliance score updated");
  }

  async function start() {
    setBusy(true);
    const created = await run(() => api<Assessment>("/assessments", { method: "POST", json: { regulation_ids: selectedIds } }), "Assessment created");
    setBusy(false);
    if (!created) return;
    setTab("regulations");
    refresh(created);
    await evaluateAll(created);
  }

  async function open(id: number) {
    const a = await run(() => api<Assessment>(`/assessments/${id}`));
    if (a) { setActive(a); setTab("regulations"); }
  }

  async function complete() {
    if (!active) return;
    const a = await run(() => api<Assessment>(`/assessments/${active.id}/complete`, { method: "POST" }), "Assessment completed; applicable regulations added to the Risk dashboard");
    if (a) refresh(a);
  }

  async function evaluateOne(f: Finding) {
    if (!active) return;
    setBusyFinding(f.id);
    try {
      const r = await api<EvaluateResult>(`/assessments/${active.id}/findings/${f.id}/evaluate`, { method: "POST" });
      if (r.ok) { refresh(await api<Assessment>(`/assessments/${active.id}`)); success("Regulation re-evaluated"); }
      else error(r.error ?? "The AI could not evaluate this regulation");
    } catch (e) { error(errorMessage(e)); }
    setBusyFinding(null);
  }

  async function override(f: Finding, status: string) {
    if (!active) return;
    const a = await run(() => api<Assessment>(`/assessments/${active.id}/findings/${f.id}`, { method: "PATCH", json: { compliance_status: status } }), "Status updated; score recalculated");
    if (a) refresh(a);
  }

  async function remind(item: ActionItem) {
    const due = addDays(DUE_DAYS[item.priority] ?? 30);
    const r = await run(() => api("/reminders", { method: "POST", json: { title: `${item.regulation}: ${item.requirement}`.slice(0, 160), due: due < todayISO() ? todayISO() : due, lead: 3 } }), `Reminder added for ${formatDate(due)}`);
    if (r) window.dispatchEvent(new Event("rl:reminders-changed"));
  }

  /*
  async function checkAi() {
    setChecking(true);
    try {
      const r = await api<AiStatus>("/assessments/ai-status?check=true");
      if (r.ok) success("AI connection works"); else error(r.error ?? "The AI provider did not respond");
    } catch (e) { error(errorMessage(e)); }
    setChecking(false);
  }
  */

  const pending = active?.findings?.filter((f) => f.applicability !== "Not Applicable" && !f.ai_evaluated).length ?? 0;
  const counts = active?.counts ?? {};
  return (
    <Page>
      <PageHeader
        title="Assessments"
        description="AI reads each regulation, checks it against your profile, registrations, filings and documents, and scores how well you comply."
        action={<Button loading={busy || !!progress} disabled={!selectedIds.length || !published.length} onClick={start}>Start assessment</Button>}
      />
      <ErrorNotice error={list.error} />
      <ErrorNotice error={regulations.error} />
      <AiBanner ai={ai.data} />
      <Card>
        <div className="row between top">
          <div>
            <h2 style={{ marginTop: 0 }}>Regulations to assess</h2>
            <p className="muted">Choose the published regulations for this assessment. {selectedIds.length} selected.</p>
          </div>
          <div className="actions">
            <Button size="sm" variant="outline" disabled={!published.length} onClick={() => setSelectedIds(published.map((r) => r.id))}>Select all</Button>
            <Button size="sm" variant="outline" disabled={!selectedIds.length} onClick={() => setSelectedIds([])}>Clear</Button>
          </div>
        </div>
        {!regulations.data ? <Loader /> : published.length ? (
          <div className="stack">
            {published.map((r) => (
              <Checkbox key={r.id} label={`${r.title} · ${r.regulator}`} checked={selectedIds.includes(r.id)}
                onChange={(e) => setSelectedIds((cur) => e.target.checked ? [...cur, r.id] : cur.filter((id) => id !== r.id))} />
            ))}
          </div>
        ) : <Empty>No published regulations are available to assess.</Empty>}
      </Card>

      {!list.data ? <Loader /> : assessments.length ? (
        <div className="grid grid-2" style={{ marginTop: 24 }}>{assessments.map((a) => (
          <Card key={a.id}>
            <b><Highlight text={`Assessment #${a.id}`} query={query} /></b>
            <p className="muted">{formatDate(a.created_at)} · {a.status === "complete" ? "Final" : "Draft"}</p>
            <p>Compliance {pct(a.compliance_score)} · Coverage {a.coverage == null ? "—" : `${Math.round(a.coverage * 100)}%`} · Risk {pct(a.risk_score)}</p>
            <Button size="sm" variant="outline" onClick={() => open(a.id)}>View assessment</Button>
          </Card>
        ))}</div>
      ) : <Empty>{list.data.length ? `No assessments match “${query}”.` : "No assessments yet. Select regulations above and start one."}</Empty>}

      {active && (
        <section className="section">
          <PageHeader
            title={`Assessment #${active.id}`}
            description={`${formatDate(active.created_at)} · ${locked ? "Final" : "Draft"}`}
            action={!locked && (
              <div className="actions">
                <Button variant="outline" loading={!!progress} onClick={() => evaluateAll(active, pending === 0)}>{pending ? `Run AI evaluation (${pending})` : "Re-run AI on all"}</Button>
                <Button onClick={complete}>Complete assessment</Button>
              </div>
            )}
          />
          {progress && (
            <div className="eval-banner" role="status">
              <b>AI is evaluating {progress.done} of {progress.total}</b>
              <div className="progress"><i style={{ width: `${(progress.done / progress.total) * 100}%` }} /></div>
              <span className="muted">Now reading: {progress.current}</span>
            </div>
          )}
          <Card>
            <div className="score-hero">
              <ScoreGauge value={active.compliance_score} />
              <div className="score-stats">
                <div className="stat"><b>{active.coverage == null ? "—" : `${Math.round(active.coverage * 100)}%`}</b><span>Evidence coverage ({active.assessed_obligations} of {active.total_obligations} obligations verified)</span></div>
                <div className="stat"><b>{active.confidence ?? "—"}</b><span>Score confidence</span></div>
                <div className="stat"><b>{pct(active.risk_score)}</b><span>Risk score · {active.risk_level}</span></div>
                <div className="stat"><b>{counts.applicable || 0}</b><span>Applicable · {counts.not_applicable || 0} not applicable · {counts.unknown || 0} unknown</span></div>
              </div>
            </div>
            {active.compliance_score == null && <p className="muted" style={{ marginBottom: 0 }}>{active.compliance_score_reason}</p>}
            {active.compliance_score != null && active.score_basis === "provisional" && (
              <p className="muted" style={{ marginBottom: 0 }}>Provisional: {active.waiting_for_ai ? `${active.waiting_for_ai} regulation(s) are not evaluated yet. ` : ""}{(active.coverage ?? 1) < 0.5 ? "Less than half of the obligations could be verified from your evidence. " : ""}Add filings, registrations and Library documents (enabled for AI) to raise coverage.</p>
            )}
          </Card>
          {active.critical_missing.length > 0 && <Alert>Complete these Business Profile details for better results: {active.critical_missing.join(", ")}.</Alert>}

          <div className="tabs" role="tablist">
            {([["regulations", "Regulations"], ["plan", `Action plan (${active.action_plan?.length ?? 0})`], ["method", "How it is scored"]] as const).map(([id, label]) => (
              <button key={id} type="button" role="tab" aria-selected={tab === id} className={`tab ${tab === id ? "is-active" : ""}`} onClick={() => setTab(id)}>{label}</button>
            ))}
          </div>

          {tab === "regulations" && <div className="stack">{active.findings?.map((f) => (
            <FindingCard key={`${f.id}-${f.compliance_status}-${f.ai_evaluated}`} finding={f} locked={!!locked} busy={busyFinding === f.id || !!progress}
              onEvaluate={evaluateOne} onOverride={override} />
          ))}</div>}
          {tab === "plan" && <ActionPlan items={active.action_plan ?? []} locked={!!locked} onRemind={remind} />}
          {tab === "method" && (
            <Card>
              <h3 style={{ marginTop: 0 }}>How the AI score is calculated</h3>
              <ol>
                <li>For each applicable regulation, the AI picks the obligations that matter to your business and checks them against your profile, registrations, filing history and the Library documents you enabled for AI.</li>
                <li>A verdict counts only when it cites real evidence. If it cites nothing verifiable it is downgraded to <b>Needs evidence</b>.</li>
                <li>Compliant = 100, Partially Compliant = 50, Non-Compliant = 0. Critical obligations count 3×, medium 2×, low 1×.</li>
                <li><b>Needs evidence</b> items are left out of the score but lower <b>coverage</b> and <b>confidence</b>, and appear in the action plan.</li>
                <li>You can override any regulation’s status; your choice replaces the AI verdict in the score.</li>
              </ol>
              <p className="muted">{active.risk_formula}</p>
              <p className="muted">This is an AI-assisted estimate to support review, not legal advice.</p>
            </Card>
          )}
        </section>
      )}
    </Page>
  );
}