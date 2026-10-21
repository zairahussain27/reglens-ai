import { Link } from "../router";
import { Badge, Card, ErrorNotice, Alert, Kpi, Loader, Page, PageHeader, Table, Empty } from "../components/ui";
import { useResource } from "../hooks/useResource";
import { formatDate } from "../services/api";
import type { Dashboard, User } from "../types/api";

const greeting = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"; };

export function HomePage({ user }: { user: User }) {
  const { data, error } = useResource<Dashboard>("/dashboard");
  if (error) return <Page><ErrorNotice error={error} /></Page>;
  if (!data) return <Page><Loader /></Page>;
  const first = (user.name || "").split(" ")[0];
  return (
    <Page>
      <PageHeader title={first ? `${greeting()}, ${first}` : greeting()} description="Here is where your compliance stands this week." />
      {!data.profile.complete && <Alert>Complete your <Link className="auth-link" href="#/business">Business Profile</Link> to make applicability review more useful.</Alert>}
      {data.profile.review_required && <Alert>Your Business Profile changed since the last assessment. <Link className="auth-link" href="#/assessments">Start a new assessment</Link> to refresh results.</Alert>}
      <div className="kpis">
        <Kpi value={`${data.profile.completion_percent}%`} label="Business profile" hint={`${data.profile.missing.length} details missing`} />
        <Kpi value={data.applicable_regulations} label="Confirmed applicable" hint={`${data.unknown_applicability ?? 0} with applicability unconfirmed`} />
        <Kpi value={data.compliance_score == null ? "Not yet calculated" : `${data.compliance_score}%`} label="Average compliance score" hint={data.compliance_assessments ? `From confirmed findings across ${data.compliance_assessments} scored assessment${data.compliance_assessments === 1 ? "" : "s"}` : "AI or manually confirmed statuses needed"} />
        <Kpi value={data.risk_score == null ? "Not yet calculated" : `${data.risk_score}%`} label={data.risk_estimated ? "Estimated risk score" : "Latest risk score"} hint={data.risk_estimated ? `${data.risk_unassessed_findings} unassessed · ${data.risk_unknown_applicability} applicability unknown` : "Based on latest assessment"} />
      </div>
      {data.risk_estimated && <Alert>This risk score is an estimate. It reflects uncertainty and potential compliance gaps in unassessed or applicability-unknown findings; it does not confirm non-compliance. <Link className="auth-link" href="#/assessments">Review assessment details</Link>.</Alert>}
      <div className="grid grid-2">
        <Card>
          <h2>Latest regulations</h2>
          {data.latest.length ? (
            <Table>
              <thead><tr><th>Regulation</th><th>Regulator</th><th>Issued</th></tr></thead>
              <tbody>{data.latest.map((item) => (
                <tr key={item.id}>
                  <td className="table-title">{item.title}{item.applicable && <span style={{ marginLeft: 8 }}><Badge>Applies to you</Badge></span>}</td>
                  <td>{item.regulator}</td><td>{formatDate(item.date)}</td>
                </tr>))}</tbody>
            </Table>
          ) : <Empty>No regulations yet. <Link className="auth-link" href="#/regulations">Add one</Link>.</Empty>}
        </Card>
        <Card>
          <h2>Open risks</h2>
          <p className="muted">{data.open} unresolved items · {data.overdue} overdue</p>
          <p className="muted">The register separates confirmed compliance issues from items awaiting review.</p>
          {data.by_area.length ? data.by_area.map((a) => (
            <div key={a.area} style={{ marginBottom: 12 }}>
              <div className="row between"><span>{a.area}</span><span className="muted">{a.score}%</span></div>
              <div className="bar"><i style={{ width: `${a.score}%` }} /></div>
            </div>
          )) : <Empty>No open risks.</Empty>}
          <Link className="auth-link" href="#/risk">Open risk dashboard</Link>
        </Card>
      </div>
    </Page>
  );
}
