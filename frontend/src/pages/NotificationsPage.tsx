import { useEffect } from "react";
import { Badge, Button, Card, Empty, ErrorNotice, Loader, Page, PageHeader } from "../components/ui";
import { useFeedback } from "../components/feedback";
import { useResource } from "../hooks/useResource";
import { api, formatDate } from "../services/api";

type NotificationItem = { id: string; kind: string; title: string; detail: string; created_at: string | null; unread: boolean };
type NotificationSummary = { items: NotificationItem[]; unread: number };

const label: Record<string, string> = {
  alert: "Reminder", regulation: "Regulation", assessment: "Assessment", risk: "Risk", "risk-score": "Risk score",
};

export function NotificationsPage() {
  const resource = useResource<NotificationSummary>("/alerts/summary");
  const { run } = useFeedback();
  useEffect(() => {
    if (!resource.data?.unread) return;
    void api("/alerts/read-all", { method: "POST" }).then(() => {
      resource.reload();
      window.dispatchEvent(new Event("rl:notifications-seen"));
    }).catch(() => undefined);
  }, [resource.data?.unread]);
  async function markRead(path: string) {
    if (await run(() => api(path, { method: "POST" }))) {
      resource.reload();
      window.dispatchEvent(new Event("rl:notifications-seen"));
    }
  }

  return <Page>
    <PageHeader title="Notifications" description="A summary of recent regulations, assessments, risk updates, and reminders."
      action={<Button variant="outline" disabled={!resource.data?.unread} onClick={() => markRead("/alerts/read-all")}>Mark reminders read</Button>} />
    <ErrorNotice error={resource.error} />
    {!resource.data ? <Loader /> : resource.data.items.length ? <div className="stack">
      {resource.data.items.map((item) => {
        const alertId = item.kind === "alert" ? Number(item.id.replace("alert-", "")) : null;
        return <Card key={item.id}>
          <div className="row between top">
            <div>
              <div className="chips" style={{ margin: 0 }}>
                <Badge tone={item.unread ? "default" : "soft"}>{label[item.kind] ?? "Update"}</Badge>
                {item.unread && <Badge>Unread</Badge>}
              </div>
              <h3>{item.title}</h3>
              <p>{item.detail}</p>
              <small className="muted">{formatDate(item.created_at)}</small>
            </div>
            {item.unread && alertId !== null && <Button size="sm" variant="outline" onClick={() => markRead(`/alerts/${alertId}/read`)}>Mark read</Button>}
          </div>
        </Card>;
      })}
    </div> : <Empty>No notifications or recent activity yet.</Empty>}
  </Page>;
}
