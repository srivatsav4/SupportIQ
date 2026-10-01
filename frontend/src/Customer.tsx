import { useState } from "react";
import { api } from "./api";
import { Badge, Card, Empty, ErrorBox, PageHeader, Skeleton, fmtDate, fmtDay, money, useFetch } from "./ui";
import { X } from "lucide-react";

export function Orders() {
  const { data, error, loading, reload } = useFetch<any[]>(() => api("/orders"));
  const [sel, setSel] = useState<string | null>(null);
  return (<div><PageHeader title="Your orders" sub="Only orders on your own account are shown." />
    {error ? <ErrorBox error={error} retry={reload} /> : loading ? <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} />)}</div> : !data?.length ? <Empty title="No orders yet" /> : (
      <div className="grid gap-3">{data.map((o) => (
        <button key={o.order_id} onClick={() => setSel(o.order_id)} className="card p-4 text-left hover:border-brand transition flex items-center justify-between gap-4">
          <div className="min-w-0"><p className="font-mono text-sm">{o.order_id}</p><p className="text-sm text-mute truncate">{o.items.join(", ") || "—"}</p><p className="text-xs text-mute mt-1">Ordered {fmtDay(o.order_date)} · expected {fmtDay(o.expected_delivery)}</p></div>
          <div className="text-right shrink-0"><Badge>{o.status}</Badge><p className="text-sm font-medium mt-1">{money(o.total_amount)}</p></div></button>))}</div>)}
    {sel && <OrderDrawer id={sel} close={() => setSel(null)} />}
  </div>);
}

function OrderDrawer({ id, close }: { id: string; close: () => void }) {
  const { data, error, loading } = useFetch<any>(() => api(`/orders/${id}`), [id]);
  return (<div className="fixed inset-0 z-40 flex justify-end bg-ink/40" onClick={close}>
    <div className="w-full max-w-md h-full bg-paper border-l border-line p-6 overflow-y-auto animate-rise" onClick={(e) => e.stopPropagation()}>
      <div className="flex justify-between items-center mb-4"><h2 className="font-display text-2xl font-mono">{id}</h2><button className="btn btn-ghost !p-2" onClick={close} aria-label="Close"><X className="w-4 h-4" /></button></div>
      {error ? <ErrorBox error={error} /> : loading || !data ? <Skeleton className="h-40" /> : (<div className="space-y-4 text-sm">
        <Card className="p-4 space-y-1"><div className="flex justify-between"><span className="text-mute">Status</span><Badge>{data.get_order.status}</Badge></div>
          <div className="flex justify-between"><span className="text-mute">Total</span><span>{money(data.get_order.total_amount)}</span></div>
          <div className="flex justify-between"><span className="text-mute">Ship to</span><span>{data.get_order.ship_to_city}</span></div>
          <div className="flex justify-between"><span className="text-mute">Expected</span><span>{data.get_order.expected_delivery}</span></div>
          {data.get_order.is_delayed && <p className="text-warn pt-1">Delayed by {data.get_order.days_late} day(s)</p>}</Card>
        {data.track_shipment?.has_shipment && <Card className="p-4 space-y-1"><p className="font-medium">Shipment</p>
          <div className="flex justify-between"><span className="text-mute">Carrier</span><span>{data.track_shipment.carrier}</span></div>
          <div className="flex justify-between"><span className="text-mute">Tracking</span><span className="font-mono">{data.track_shipment.tracking_number}</span></div>
          <div className="flex justify-between"><span className="text-mute">Status</span><span>{data.track_shipment.shipment_status}</span></div></Card>}
        <Card className="p-4"><p className="font-medium mb-2">Items</p>{data.get_order_items?.items.map((i: any, k: number) => <div key={k} className="flex justify-between py-1"><span>{i.quantity}× {i.name}</span><span>{money(i.price)}</span></div>)}</Card>
        {data.get_refund_status?.has_refund && <Card className="p-4"><p className="font-medium mb-2">Refunds</p>{data.get_refund_status.refunds.map((r: any) => <div key={r.refund_id} className="flex justify-between py-1"><span>{r.refund_id} · {money(r.amount)}</span><Badge>{r.status}</Badge></div>)}</Card>}
      </div>)}
    </div></div>);
}

export function Tickets() {
  const { data, error, loading, reload } = useFetch<any[]>(() => api("/tickets"));
  return (<div><PageHeader title="Support tickets" sub="Tickets created by you or by the assistant on your behalf." />
    {error ? <ErrorBox error={error} retry={reload} /> : loading ? <Skeleton className="h-40" /> : !data?.length ? <Empty title="No tickets" hint="Escalated issues will appear here." /> : (
      <div className="grid gap-3">{data.map((t) => (<Card key={t.ticket_id} className="p-4"><div className="flex justify-between gap-3"><div><p className="font-mono text-sm">{t.ticket_id} <span className="text-mute font-sans">· {t.category}</span></p>
        <p className="text-sm text-mute mt-1 line-clamp-2">{t.description}</p><p className="text-xs text-mute mt-2">{fmtDate(t.created_at)}{t.order_id ? ` · order ${t.order_id}` : ""}</p></div>
        <div className="flex flex-col gap-1 items-end shrink-0"><Badge>{t.status}</Badge><Badge>{t.priority}</Badge></div></div></Card>))}</div>)}</div>);
}

export function History({ open }: { open: (id: string) => void }) {
  const { data, error, loading, reload } = useFetch<any[]>(() => api("/conversations"));
  return (<div><PageHeader title="Conversation history" sub="Resume any previous conversation." />
    {error ? <ErrorBox error={error} retry={reload} /> : loading ? <Skeleton className="h-40" /> : !data?.length ? <Empty title="No conversations yet" hint="Start one from the Chat tab." /> : (
      <div className="grid gap-3">{data.map((c) => (<button key={c.conversation_id} onClick={() => open(c.conversation_id)} className="card p-4 text-left hover:border-brand transition flex justify-between gap-3">
        <div className="min-w-0"><p className="text-sm font-medium truncate">{c.preview || "(empty)"}</p><p className="text-xs text-mute mt-1">{fmtDate(c.updated_at)} · {c.turns} turn(s) · {c.intent}</p></div><Badge>{c.resolution_status}</Badge></button>))}</div>)}</div>);
}
