import { useState, type FormEvent } from "react";
import { Badge, Button, Card, Empty, ErrorNotice, FormField, Loader, Page, PageHeader, Textarea } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, formatDate } from "../services/api";
import type { AskResult } from "../types/api";

function Sources({ result }: { result: AskResult }) {
  if (!result.sources.length) return null;
  return <>{result.sources.map((s, i) => (
    <details key={i} style={{ marginBottom: 8 }}>
      <summary><Badge tone="soft">[{i + 1}] {s.doc}{s.page ? `, page ${s.page}` : ""}</Badge></summary>
      {s.snippet && <p className="muted">{s.snippet}</p>}
    </details>
  ))}</>;
}

export function AskPage() {
  const history = useResource<AskResult[]>("/ask/history");
  const scope = useResource<{ regulations: number; library: number }>("/ask/scope");
  const { run } = useFeedback();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResult>();
  const [busy, setBusy] = useState(false);

  async function ask(event: FormEvent) {
    event.preventDefault();
    if (question.trim().length < 3) return;
    setBusy(true);
    const result = await run(() => api<AskResult>("/ask", { method: "POST", json: { question: question.trim() } }));
    setBusy(false);
    if (result) { setAnswer(result); history.reload(); }
  }

  return (
    <Page>
      <PageHeader title="Ask" description="Answers come from government regulations and enabled Library documents." />
      {scope.data && <p className="muted">Sources available: {scope.data.regulations} regulations and {scope.data.library} Library documents.</p>}
      <Card>
        <form onSubmit={ask}>
          <FormField label="Question">
            <Textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} minLength={3} maxLength={1000}
              placeholder="e.g. What consent is needed before processing personal data?"
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(e); }} />
          </FormField>
          <Button type="submit" loading={busy} disabled={question.trim().length < 3}>Ask</Button>
        </form>
        {answer && (
          <div className="answer-box">
            <h2>Answer</h2>
            <p className="answer">{answer.answer}</p>
            <Sources result={answer} />
            <p className="muted">Research support from your sources, not legal advice.</p>
          </div>
        )}
      </Card>
      <div className="section">
        <h2>Recent questions</h2>
        <ErrorNotice error={history.error} />
        {!history.data ? <Loader /> : history.data.length ? history.data.map((item) => (
          <Card key={item.id}>
            <b>{item.question}</b>
            <p className="answer">{item.answer}</p>
            <div className="row between"><small className="muted">{formatDate(item.created_at)}</small>
              <Button size="sm" variant="outline" onClick={() => { setQuestion(item.question); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Ask again</Button></div>
          </Card>
        )) : <Empty>No questions yet.</Empty>}
      </div>
    </Page>
  );
}
