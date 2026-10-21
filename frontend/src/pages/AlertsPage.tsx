import { Badge, Button, Card, Empty, ErrorNotice, Loader, Page, PageHeader } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, formatDate } from "../services/api";
import type { AlertItem } from "../types/api";

export function AlertsPage() {
  const resource = useResource<AlertItem[]>("/alerts");
  const { run } = useFeedback();
  const mark = async (path: string) => { if (await run(() => api(path, { method: "POST" }))) resource.reload(); };
  const unread = resource.data?.filter((a) => a.unread).length ?? 0;
  return (
    <Page>
      <PageHeader title="Reminder alerts" description="Reminder notifications and changes that need your attention."
        action={<Button variant="outline" disabled={!unread} onClick={() => mark("/alerts/read-all")}>Mark all read</Button>} />
      <ErrorNotice error={resource.error} />
      {!resource.data ? <Loader /> : resource.data.length ? resource.data.map((item) => (
        <Card key={item.id}>
          <div className="row between top">
            <div>
              <Badge tone={item.unread ? "default" : "soft"}>{item.unread ? "Unread" : "Read"}</Badge>
              <h3>{item.title}</h3><p>{item.detail}</p><small className="muted">{formatDate(item.created_at)}</small>
            </div>
            {item.unread && <Button size="sm" variant="outline" onClick={() => mark(`/alerts/${item.id}/read`)}>Mark read</Button>}
          </div>
        </Card>
      )) : <Empty>You’re all caught up.</Empty>}
    </Page>
  );
}
