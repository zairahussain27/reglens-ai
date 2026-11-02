import type { ReactNode } from "react";
import { Link } from "../router";
import { Badge, Button, Empty, ErrorNotice, Loader, Page, PageHeader, Table } from "../components/ui";
import { ScoreGauge } from "../components/ScoreGauge";
import { useResource } from "../hooks/useResource";
import { formatDate } from "../services/api";
import type { Dashboard, User } from "../types/api";
import "./home.css";

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
};

const tone = (priority: string) =>
  priority === "Critical" || priority === "High" ? "high" : priority === "Medium" ? "mid" : "low";

function Panel({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="home-panel">
      <header>
        <h2>{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}

function Meter({ value, label, right }: { value: number | null; label: string; right?: string }) {
  return (
    <div className="home-meter">
      <div>
        <span>{label}</span>
        <span className="home-quiet">{right ?? (value == null ? "Needs evidence" : `${Math.round(value)}%`)}</span>
      </div>
      <div className="home-track" data-empty={value == null}>
        <i style={{ width: `${value ?? 0}%` }} />
      </div>
    </div>
  );
}

function Trend({ points }: { points: Array<number | null> }) {
  const values = points.map((v, i) => ({ v, i })).filter((p): p is { v: number; i: number } => p.v != null);
  if (values.length < 2) return <Empty>Complete two assessments to see how your score moves.</Empty>;
  const x = (i: number) => 8 + (i / Math.max(points.length - 1, 1)) * 284;
  const y = (v: number) => 72 - (v / 100) * 64;
  const line = values.map((p) => `${x(p.i)},${y(p.v)}`).join(" ");
  const last = values[values.length - 1];
  const prev = values[values.length - 2];
  const delta = Math.round(last.v - prev.v);
  return (
    <>
      <p className="home-quiet" style={{ marginTop: 0 }}>
        {delta === 0 ? "No change since the last assessment." : `${delta > 0 ? "Up" : "Down"} ${Math.abs(delta)} points since the last assessment.`}
      </p>
      <svg className="home-spark" viewBox="0 0 300 80" role="img" aria-label="Compliance score trend">
        <polygon points={`${x(values[0].i)},76 ${line} ${x(last.i)},76`} />
        <polyline points={line} />
        <circle cx={x(last.i)} cy={y(last.v)} r="4" />
      </svg>
    </>
  );
}

export function HomePage({ user }: { user: User }) {
  const { data, error } = useResource<Dashboard>("/dashboard");
  if (error) return <Page><ErrorNotice error={error} /></Page>;
  if (!data) return <Page><Loader /></Page>;

  const first = (user.name || "").split(" ")[0];
  const coverage = data.coverage == null ? "—" : `${Math.round(data.coverage * 100)}%`;

  const notices: Array<{ key: string; danger?: boolean; body: ReactNode }> = [];
  if (!data.ai.available)
    notices.push({ key: "ai", danger: true, body: <>AI scoring is off. Add <b>GROQ_API_KEY</b> to the backend environment to calculate your score.</> });
  if (!data.profile.complete)
    notices.push({ key: "profile", body: <>Finish your <Link className="auth-link" href="#/business">Business Profile</Link> so the AI can judge which rules apply to you.</> });
  if (data.profile.review_required)
    notices.push({ key: "review", body: <>Your Business Profile changed after the last assessment. <Link className="auth-link" href="#/assessments">Start a new assessment</Link> to refresh your results.</> });

  return (
    <Page>
      <PageHeader title={first ? `${greeting()}, ${first}` : greeting()} description="Where your business stands on compliance, and what to do next." />

      {notices.length > 0 && (
        <ul className="home-notices" role="status">
          {notices.map((n) => <li key={n.key} data-danger={n.danger}>{n.body}</li>)}
        </ul>
      )}

      <div className="home-hero">
        <div className="home-score">
          <ScoreGauge value={data.compliance_score} size={190} />
          {data.compliance_score != null ? (
            <p className="home-quiet">
              Based on {data.assessed_obligations} of {data.total_obligations} obligations the AI could verify{data.compliance_estimated ? ". This score is provisional." : "."}
            </p>
          ) : (
            <p className="home-quiet">{data.compliance_score_reason}</p>
          )}
          {data.assessment_id && <Link className="auth-link" href="#/assessments">Open assessment #{data.assessment_id}</Link>}
        </div>

        <div>
          <h2 className="home-lead">{data.priorities.length ? "Fix these first" : "Next step"}</h2>
          {data.priorities.length > 0 ? (
            <ol className="home-priorities">
              {data.priorities.map((p, i) => (
                <li key={`${p.finding_id}-${i}`} data-tone={tone(p.priority)}>
                  <span>
                    <b>{p.requirement}</b>
                    <span className="home-quiet">{p.regulation}</span>
                  </span>
                  <Badge tone={tone(p.priority) === "high" ? "danger" : "soft"}>{p.priority}</Badge>
                </li>
              ))}
            </ol>
          ) : (
            <div className="home-next">
              <p>{data.assessment_id ? "Your last assessment has no urgent fixes. Run the AI evaluation again after you add new evidence." : "Run your first assessment to get a score and a list of what to fix."}</p>
              <Link href="#/assessments"><Button>{data.assessment_id ? "Run the AI evaluation" : "Run your first assessment"}</Button></Link>
            </div>
          )}
        </div>
      </div>

      <dl className="home-stats">
        <div><dt>Business profile</dt><dd>{data.profile.completion_percent}%</dd><small>{data.profile.missing.length} details missing</small></div>
        <div><dt>Applicable regulations</dt><dd>{data.applicable_regulations}</dd><small>{data.unknown_applicability ?? 0} not yet confirmed</small></div>
        <div><dt>Evidence coverage</dt><dd>{coverage}</dd><small>{data.confidence ? `Confidence ${data.confidence}` : "Obligations backed by evidence"}</small></div>
        <div><dt>Risk score</dt><dd>{data.risk_score == null ? "—" : `${data.risk_score}%`}</dd><small>{data.risk_level ?? "Run an assessment"}</small></div>
      </dl>

      <div className="home-cols">
        <Panel title="Upcoming deadlines" action={<span><Link className="auth-link" href="#/filings">Filings</Link> <Link className="auth-link" href="#/reminders">Reminders</Link></span>}>
          {data.deadlines.length ? (
            <ul className="home-list">
              {data.deadlines.map((d, i) => (
                <li key={i}>
                  <span>
                    {d.title}
                    <span className="home-quiet">{d.kind === "filing" ? "Filing" : "Reminder"}, due {formatDate(d.due)}</span>
                  </span>
                  <Badge tone={d.overdue ? "danger" : "soft"}>{d.overdue ? `${-d.days}d overdue` : d.days === 0 ? "Today" : `in ${d.days}d`}</Badge>
                </li>
              ))}
            </ul>
          ) : <Empty>Nothing due in the next 30 days.</Empty>}
        </Panel>

        <Panel title="Regulation scorecards">
          {data.scorecards.length
            ? data.scorecards.map((s) => <Meter key={s.id} label={s.title} value={s.score} />)
            : <Empty>No applicable regulations scored yet.</Empty>}
        </Panel>

        <Panel title="Score trend">
          <Trend points={data.trend.map((t) => t.compliance)} />
        </Panel>

        <Panel title="Open risks" action={<Link className="auth-link" href="#/risk">Open risk dashboard</Link>}>
          <p className="home-quiet" style={{ marginTop: 0 }}>{data.open} unresolved, {data.overdue} overdue</p>
          {data.by_area.length
            ? data.by_area.map((a) => <Meter key={a.area} label={a.area} value={a.score} right={`${a.score}%`} />)
            : <Empty>No open risks.</Empty>}
        </Panel>
      </div>

      <Panel title="Latest regulations" action={<Link className="auth-link" href="#/regulations">All regulations</Link>}>
        {data.latest.length ? (
          <Table>
            <thead><tr><th>Regulation</th><th>Regulator</th><th>Issued</th></tr></thead>
            <tbody>
              {data.latest.map((item) => (
                <tr key={item.id}>
                  <td className="table-title">{item.title}{item.applicable && <span style={{ marginLeft: 8 }}><Badge>Applies to you</Badge></span>}</td>
                  <td>{item.regulator}</td>
                  <td>{formatDate(item.date)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : <Empty>No regulations yet. <Link className="auth-link" href="#/regulations">Add one</Link>.</Empty>}
      </Panel>
    </Page>
  );
}