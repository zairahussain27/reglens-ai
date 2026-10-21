import { useMemo } from "react";
import { Badge, Card, Empty, ErrorNotice, Loader, Page, PageHeader } from "../components/ui";
import { useResource } from "../hooks/useResource";
import { navigate } from "../router";
import { formatDate } from "../services/api";
import { api } from "../services/api";
import type { Assessment, Document, Regulation } from "../types/api";

function searchTerm() {
  return new URLSearchParams(window.location.hash.split("?")[1] ?? "").get("q")?.trim() ?? "";
}

export function SearchPage() {
  const query = searchTerm();
  const regulations = useResource<Regulation[]>("/regulations");
  const documents = useResource<Document[]>("/documents");
  const assessments = useResource<Assessment[]>("/assessments");
  const needle = query.toLocaleLowerCase();

  const matches = useMemo(() => ({
    regulations: (regulations.data ?? []).filter((item) => `${item.title} ${item.regulator} ${item.summary}`.toLocaleLowerCase().includes(needle)),
    documents: (documents.data ?? []).filter((item) => `${item.name} ${item.kind} ${item.status}`.toLocaleLowerCase().includes(needle)),
    assessments: (assessments.data ?? []).filter((item) => `assessment ${item.id} ${item.status} ${item.risk_level} ${item.critical_missing.join(" ")}`.toLocaleLowerCase().includes(needle)),
  }), [regulations.data, documents.data, assessments.data, needle]);
  const loading = regulations.loading || documents.loading || assessments.loading;

  return <Page>
    <PageHeader title="Search" description={query ? `Results for “${query}” across regulations, library files, and assessments.` : "Search your workspace."} />
    {!query && <Empty>Enter a search term in the top bar to find workspace content.</Empty>}
    {query && <>
      <ErrorNotice error={[regulations.error, documents.error, assessments.error].filter(Boolean).join(" ")} />
      {loading ? <Loader /> : <div className="stack">
        {matches.regulations.length > 0 && <section>
          <h2>Regulations</h2>
          <div className="stack">{matches.regulations.map((item) => <Card key={item.id} className="search-result" onClick={() => navigate(`regulations?q=${encodeURIComponent(query)}`)}>
            <b>{item.title}</b><p className="muted">{item.regulator} · {item.summary || item.status}</p><span className="search-result__action">Open regulation results →</span>
          </Card>)}</div>
        </section>}
        {matches.documents.length > 0 && <section>
          <h2>Library files</h2>
          <div className="stack">{matches.documents.map((item) => <Card key={item.id} className="search-result" onClick={() => navigate(`library?q=${encodeURIComponent(query)}`)}>
            <div className="row between"><b>{item.name}</b><Badge tone="soft">{item.kind}</Badge></div>
            <p className="muted">{formatDate(item.created_at)} · {item.status}{item.use_in_ai ? " · Used in Ask" : ""}</p><span className="search-result__action">Open library results →</span>
          </Card>)}</div>
        </section>}
        {matches.assessments.length > 0 && <section>
          <h2>Assessments</h2>
          <div className="stack">{matches.assessments.map((item) => <Card key={item.id} className="search-result" onClick={() => navigate(`assessments?q=${encodeURIComponent(query)}`)}>
            <b>Assessment #{item.id}</b><p className="muted">{formatDate(item.created_at)} · {item.status} · {item.risk_level} risk</p><span className="search-result__action">Open assessment results →</span>
          </Card>)}</div>
        </section>}
        {!matches.regulations.length && !matches.documents.length && !matches.assessments.length && <Empty>No workspace content matched “{query}”.</Empty>}
      </div>}
    </>}
  </Page>;
}
