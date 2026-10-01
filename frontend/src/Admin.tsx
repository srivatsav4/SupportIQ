import { useState } from "react";
import { api } from "./api";
import { Badge, Card, Empty, ErrorBox, PageHeader, Skeleton, Spinner, fmtDate, money, pct, useFetch } from "./ui";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Check, X, Play, RefreshCw } from "lucide-react";

const C = { brand: "rgb(var(--brand))", ok: "rgb(var(--ok))", info: "rgb(var(--info))", warn: "rgb(var(--warn))", bad: "rgb(var(--bad))", mute: "rgb(var(--mute))", line: "rgb(var(--line))" };
const axis = { stroke: C.mute, fontSize: 11, tickLine: false, axisLine: false } as const;
const tip = { contentStyle: { background: "rgb(var(--card))", border: "1px solid rgb(var(--line))", borderRadius: 8, fontSize: 12 } };

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return <Card className="p-4"><p className="text-xs text-mute">{label}</p><p className="font-display text-3xl mt-1 tabular-nums">{value}</p>{sub && <p className="text-xs text-mute mt-1">{sub}</p>}</Card>;
}

export function Dashboard() {
  const s = useFetch<any>(() => api("/admin/analytics/summary"));
  const ts = useFetch<any>(() => api("/admin/analytics/timeseries?days=14"));
  const d = useFetch<any>(() => api("/admin/analytics/distributions"));
  if (s.error) return <ErrorBox error={s.error} retry={s.reload} />;
  const m = s.data;
  const series = ts.data?.labels.map((l: string, i: number) => ({ day: l.slice(5), conversations: ts.data.conversations[i], resolved: ts.data.ai_resolved[i], escalated: ts.data.escalated[i], latency: ts.data.avg_latency_ms[i] })) || [];
  const intents = Object.entries(d.data?.intents || {}).map(([k, v]) => ({ name: k.replace("_", " ").toLowerCase(), value: v as number })).slice(0, 10);
  const prio = Object.entries(d.data?.ticket_priority || {}).map(([k, v]) => ({ name: k, value: v as number }));
  const cats = Object.entries(d.data?.ticket_categories || {}).map(([k, v]) => ({ name: k, value: v as number }));
  const res = m ? [{ name: "AI resolved", value: Math.round((m.ai_resolution_rate || 0) * m.total_conversations) }, { name: "Escalated", value: Math.round((m.human_escalation_rate || 0) * m.total_conversations) },
    { name: "Open", value: m.total_conversations - Math.round((m.ai_resolution_rate || 0) * m.total_conversations) - Math.round((m.human_escalation_rate || 0) * m.total_conversations) }] : [];
  return (<div><PageHeader title="Dashboard" sub="Live metrics computed from conversations handled by the assistant in this environment." right={<button className="btn btn-ghost" onClick={() => { s.reload(); ts.reload(); d.reload(); }}><RefreshCw className="w-4 h-4" />Refresh</button>} />
    {s.loading || !m ? <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div> : (<>
      {m.total_conversations === 0 && <Card className="p-4 mb-4 text-sm text-mute">No conversations yet. Sign in as a customer, chat with the assistant, and these numbers will fill in.</Card>}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label="Total conversations" value={String(m.total_conversations)} sub={`${m.ai_turns} AI turns`} />
        <Stat label="AI resolution rate" value={pct(m.ai_resolution_rate)} /><Stat label="Human escalation rate" value={pct(m.human_escalation_rate)} />
        <Stat label="Avg response time" value={m.avg_response_time_ms === null ? "—" : `${Math.round(m.avg_response_time_ms)} ms`} />
        <Stat label="Avg resolution time" value={m.avg_resolution_time_s === null ? "—" : `${m.avg_resolution_time_s.toFixed(1)} s`} /><Stat label="Open tickets" value={String(m.open_tickets)} />
        <Stat label="High-priority tickets" value={String(m.high_priority_tickets)} sub={`${m.pending_approvals} pending approvals`} /><Stat label="Tool failure rate" value={pct(m.tool_failure_rate)} />
        <Stat label="RAG retrieval quality" value={m.rag_retrieval_quality === null ? "—" : m.rag_retrieval_quality.toFixed(2)} sub="mean top-chunk score" /><Stat label="Groundedness" value={pct(m.groundedness)} sub="verifier, live turns" />
        <Stat label="Citation accuracy" value={pct(m.citation_accuracy)} /><Stat label="Est. LLM cost" value={`$${m.estimated_llm_cost_usd.toFixed(4)}`} sub={`${m.llm_tokens} tokens`} />
      </div>
      <div className="grid lg:grid-cols-2 gap-3 mt-3">
        <Card className="p-4"><p className="text-sm font-medium mb-3">Conversations over time</p><ResponsiveContainer width="100%" height={220}><AreaChart data={series}><CartesianGrid stroke={C.line} vertical={false} /><XAxis dataKey="day" {...axis} /><YAxis allowDecimals={false} {...axis} /><Tooltip {...tip} />
          <Area dataKey="resolved" stackId="1" stroke={C.ok} fill={C.ok} fillOpacity={0.25} name="AI resolved" /><Area dataKey="escalated" stackId="1" stroke={C.brand} fill={C.brand} fillOpacity={0.25} name="Escalated" /></AreaChart></ResponsiveContainer></Card>
        <Card className="p-4"><p className="text-sm font-medium mb-3">Resolution</p><ResponsiveContainer width="100%" height={220}><PieChart><Pie data={res} dataKey="value" innerRadius={55} outerRadius={85} paddingAngle={2}>{res.map((_, i) => <Cell key={i} fill={[C.ok, C.brand, C.info][i]} />)}</Pie><Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} /></PieChart></ResponsiveContainer></Card>
        <Card className="p-4"><p className="text-sm font-medium mb-3">Intent distribution</p>{intents.length ? <ResponsiveContainer width="100%" height={260}><BarChart data={intents} layout="vertical" margin={{ left: 40 }}><XAxis type="number" allowDecimals={false} {...axis} /><YAxis type="category" dataKey="name" width={130} {...axis} /><Tooltip {...tip} /><Bar dataKey="value" fill={C.brand} radius={4} /></BarChart></ResponsiveContainer> : <Empty title="No data yet" />}</Card>
        <Card className="p-4"><p className="text-sm font-medium mb-3">Ticket priority</p><ResponsiveContainer width="100%" height={260}><BarChart data={prio}><CartesianGrid stroke={C.line} vertical={false} /><XAxis dataKey="name" {...axis} /><YAxis allowDecimals={false} {...axis} /><Tooltip {...tip} /><Bar dataKey="value" fill={C.info} radius={4} /></BarChart></ResponsiveContainer></Card>
        <Card className="p-4"><p className="text-sm font-medium mb-3">Common customer problems (ticket categories)</p><ResponsiveContainer width="100%" height={260}><BarChart data={cats} layout="vertical" margin={{ left: 30 }}><XAxis type="number" allowDecimals={false} {...axis} /><YAxis type="category" dataKey="name" width={110} {...axis} /><Tooltip {...tip} /><Bar dataKey="value" fill={C.warn} radius={4} /></BarChart></ResponsiveContainer></Card>
        <Card className="p-4 overflow-x-auto"><p className="text-sm font-medium mb-3">AI performance by intent</p>{d.data?.ai_performance?.length ? (<table className="w-full text-sm"><thead className="text-xs text-mute text-left"><tr><th className="pb-2">Intent</th><th>Turns</th><th>Groundedness</th><th>Avg ms</th></tr></thead><tbody>
          {d.data.ai_performance.map((r: any) => <tr key={r.intent} className="border-t border-line"><td className="py-1.5">{r.intent}</td><td>{r.turns}</td><td>{pct(r.groundedness)}</td><td>{r.avg_latency_ms}</td></tr>)}</tbody></table>) : <Empty title="No data yet" />}</Card>
      </div></>)}</div>);
}

export function Conversations() {
  const [status, setStatus] = useState(""); const [open, setOpen] = useState<string | null>(null);
  const { data, error, loading, reload } = useFetch<any[]>(() => api(`/conversations?all=true${status ? `&status=${status}` : ""}`), [status]);
  return (<div><PageHeader title="Conversations" right={<select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option><option value="ai_resolved">AI resolved</option><option value="escalated">Escalated</option><option value="open">Open</option></select>} />
    {error ? <ErrorBox error={error} retry={reload} /> : loading ? <Spinner /> : !data?.length ? <Empty title="No conversations" /> : (<Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-xs text-mute text-left"><tr className="border-b border-line"><th className="p-3">Customer</th><th>Intent</th><th>Sentiment</th><th>Status</th><th>Turns</th><th>Updated</th></tr></thead><tbody>
      {data.map((c) => <tr key={c.conversation_id} className="border-b border-line last:border-0 hover:bg-line/30 cursor-pointer" onClick={() => setOpen(c.conversation_id)}><td className="p-3 font-mono">{c.customer_id}</td><td>{c.intent}</td><td>{c.sentiment}</td><td><Badge>{c.resolution_status}</Badge></td><td>{c.turns}</td><td className="text-mute">{fmtDate(c.updated_at)}</td></tr>)}</tbody></table></Card>)}
    {open && <Transcript id={open} close={() => setOpen(null)} />}</div>);
}
function Transcript({ id, close }: { id: string; close: () => void }) {
  const { data, loading, error } = useFetch<any>(() => api(`/conversations/${id}`), [id]);
  return (<div className="fixed inset-0 z-40 flex justify-end bg-ink/40" onClick={close}><div className="w-full max-w-lg h-full bg-paper border-l border-line p-6 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
    <div className="flex justify-between mb-4"><h2 className="font-display text-2xl">Transcript</h2><button className="btn btn-ghost !p-2" onClick={close}><X className="w-4 h-4" /></button></div>
    {error ? <ErrorBox error={error} /> : loading || !data ? <Spinner /> : <div className="space-y-3">{data.messages.map((m: any, i: number) => (<div key={i} className={`text-sm rounded-xl px-3 py-2 whitespace-pre-wrap ${m.role === "user" ? "bg-ink text-paper ml-8" : "card mr-8"}`}>{m.content}{m.escalation && <p className="text-xs mt-1 text-brand">Escalated → {m.escalation.ticket_id}</p>}</div>))}</div>}</div></div>);
}

export function AdminTickets() {
  const [status, setStatus] = useState(""); const [sel, setSel] = useState<any>(null);
  const { data, error, loading, reload } = useFetch<any[]>(() => api(`/tickets?all=true&limit=200${status ? `&status=${status}` : ""}`), [status]);
  async function setS(id: string, st: string) { await api(`/tickets/${id}`, { method: "PATCH", body: { status: st } }); setSel(null); reload(); }
  return (<div><PageHeader title="Tickets" right={<select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>{["Open", "In Progress", "Resolved", "Closed"].map((s) => <option key={s}>{s}</option>)}</select>} />
    {error ? <ErrorBox error={error} retry={reload} /> : loading ? <Spinner /> : !data?.length ? <Empty title="No tickets" /> : (<Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-xs text-mute text-left"><tr className="border-b border-line"><th className="p-3">Ticket</th><th>Customer</th><th>Category</th><th>Priority</th><th>Status</th><th>Created</th></tr></thead><tbody>
      {data.map((t) => <tr key={t.ticket_id} className="border-b border-line last:border-0 hover:bg-line/30 cursor-pointer" onClick={() => setSel(t)}><td className="p-3 font-mono">{t.ticket_id}</td><td className="font-mono">{t.customer_id}</td><td>{t.category}</td><td><Badge>{t.priority}</Badge></td><td><Badge>{t.status}</Badge></td><td className="text-mute">{fmtDate(t.created_at)}</td></tr>)}</tbody></table></Card>)}
    {sel && <div className="fixed inset-0 z-40 flex justify-end bg-ink/40" onClick={() => setSel(null)}><div className="w-full max-w-lg h-full bg-paper border-l border-line p-6 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
      <div className="flex justify-between mb-3"><h2 className="font-display text-2xl font-mono">{sel.ticket_id}</h2><button className="btn btn-ghost !p-2" onClick={() => setSel(null)}><X className="w-4 h-4" /></button></div>
      <div className="flex gap-2 mb-3"><Badge>{sel.priority}</Badge><Badge>{sel.status}</Badge><span className="text-sm text-mute">{sel.category}</span></div>
      <p className="text-sm whitespace-pre-wrap">{sel.description}</p>
      {sel.escalation_context && <Card className="p-4 mt-4 text-sm space-y-2"><p className="font-medium">Escalation context</p>
        {[["Customer", `${sel.escalation_context.customer_name} (${sel.escalation_context.customer_id}, ${sel.escalation_context.membership_tier})`], ["Intent", `${sel.escalation_context.intent} (${Math.round(sel.escalation_context.intent_confidence * 100)}%)`],
          ["Sentiment / urgency", `${sel.escalation_context.sentiment} / ${sel.escalation_context.urgency}`], ["Order", sel.escalation_context.order_id || "—"], ["Reason", sel.escalation_context.escalation_reason], ["AI recommendation", sel.escalation_context.ai_recommendation]].map(([k, v]) => <div key={k as string}><span className="text-mute">{k}: </span>{v}</div>)}
        <div><span className="text-mute">Policy sources: </span>{(sel.escalation_context.policy_sources || []).join("; ") || "—"}</div>
        <details><summary className="cursor-pointer text-mute">Conversation summary</summary><pre className="whitespace-pre-wrap text-xs mt-2">{sel.escalation_context.conversation_summary}</pre></details></Card>}
      <div className="flex gap-2 mt-5">{["In Progress", "Resolved", "Closed"].map((s) => <button key={s} className="btn btn-ghost" onClick={() => setS(sel.ticket_id, s)}>Mark {s}</button>)}</div></div></div>}</div>);
}

export function Approvals() {
  const { data, error, loading, reload } = useFetch<any[]>(() => api("/admin/approvals"));
  const [busy, setBusy] = useState<string | null>(null); const [msg, setMsg] = useState("");
  async function act(id: string, kind: "approve" | "reject") {
    setBusy(id); setMsg("");
    try { await api(`/admin/approvals/${id}/${kind}`, { body: { note: kind === "reject" ? "Rejected by reviewer" : "" } }); reload(); } catch (e: any) { setMsg(e.message); } finally { setBusy(null); }
  }
  const pending = data?.filter((a) => a.status === "PENDING") || []; const done = data?.filter((a) => a.status !== "PENDING") || [];
  return (<div><PageHeader title="Approvals" sub="High-risk actions the AI is not allowed to perform on its own. Approving executes the action; rejecting leaves everything unchanged." />
    {msg && <p className="text-bad text-sm mb-3">{msg}</p>}
    {error ? <ErrorBox error={error} retry={reload} /> : loading ? <Spinner /> : (<><h3 className="font-medium mb-2">Pending ({pending.length})</h3>
      {!pending.length ? <Card className="mb-6"><Empty title="Nothing waiting" hint="Ask the assistant for a refund of order A12353 as Priya to create one." /></Card> : <div className="grid gap-3 mb-6">{pending.map((a) => (
        <Card key={a.approval_id} className="p-4 border-warn/40 flex flex-wrap items-center justify-between gap-3"><div><p className="font-mono text-sm">{a.approval_id} <span className="font-sans text-mute">· {a.action} · customer {a.customer_id}</span></p><p className="text-sm mt-1">{a.reason}</p><p className="text-xs text-mute mt-1">{fmtDate(a.created_at)} · risk <Badge tone="red">{a.risk_level}</Badge></p></div>
          <div className="flex gap-2"><button className="btn btn-primary" disabled={busy === a.approval_id} onClick={() => act(a.approval_id, "approve")}><Check className="w-4 h-4" />Approve</button><button className="btn btn-ghost" disabled={busy === a.approval_id} onClick={() => act(a.approval_id, "reject")}><X className="w-4 h-4" />Reject</button></div></Card>))}</div>}
      <h3 className="font-medium mb-2">History</h3>{!done.length ? <p className="text-sm text-mute">None yet.</p> : <Card className="overflow-x-auto"><table className="w-full text-sm"><tbody>{done.map((a) => <tr key={a.approval_id} className="border-b border-line last:border-0"><td className="p-3 font-mono">{a.approval_id}</td><td>{a.action}</td><td><Badge>{a.status}</Badge></td><td className="text-mute">{a.reviewer}</td><td className="text-mute">{fmtDate(a.resolved_at)}</td></tr>)}</tbody></table></Card>}</>)}</div>);
}

export function Customers() {
  const [q, setQ] = useState("");
  const { data, error, loading } = useFetch<any[]>(() => api(`/admin/customers?q=${encodeURIComponent(q)}`), [q]);
  return (<div><PageHeader title="Customers" sub="Synthetic customers. Contact details are masked in this view." right={<input className="input !w-64" placeholder="Search name, ID or email" value={q} onChange={(e) => setQ(e.target.value)} />} />
    {error ? <ErrorBox error={error} /> : loading ? <Spinner /> : !data?.length ? <Empty title="No matches" /> : <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-xs text-mute text-left"><tr className="border-b border-line"><th className="p-3">ID</th><th>Name</th><th>Email</th><th>Phone</th><th>Tier</th><th>Orders</th></tr></thead><tbody>
      {data.map((c) => <tr key={c.customer_id} className="border-b border-line last:border-0"><td className="p-3 font-mono">{c.customer_id}</td><td>{c.name}</td><td className="text-mute">{c.email}</td><td className="text-mute font-mono">{c.phone}</td><td>{c.membership_tier}</td><td>{c.orders}</td></tr>)}</tbody></table></Card>}</div>);
}

export function Evaluation({ canRun }: { canRun: boolean }) {
  const { data, error, loading, reload } = useFetch<any>(() => api("/admin/evaluation/latest"));
  const [running, setRunning] = useState(false); const [err, setErr] = useState("");
  async function run() { setRunning(true); setErr(""); try { await api("/admin/evaluation/run", { method: "POST" }); reload(); } catch (e: any) { setErr(e.message); } finally { setRunning(false); } }
  const M = data?.metrics || {};
  const rows: [string, string][] = [["Intent accuracy", "intent_accuracy"], ["Retrieval precision (doc-level)", "retrieval_precision"], ["Retrieval recall", "retrieval_recall"], ["Answer correctness", "answer_correctness"], ["Groundedness", "groundedness"], ["Citation accuracy", "citation_accuracy"], ["Tool selection accuracy", "tool_selection_accuracy"], ["Escalation accuracy", "escalation_accuracy"], ["Safety accuracy", "safety_accuracy"], ["Verifier pass rate", "verifier_pass_rate"]];
  return (<div><PageHeader title="AI evaluation" sub="Computed by running a synthetic test set through the live agent. Not a measure of real-world accuracy." right={canRun && <button className="btn btn-primary" disabled={running} onClick={run}><Play className="w-4 h-4" />{running ? "Running…" : "Run evaluation"}</button>} />
    {err && <p className="text-bad text-sm mb-3">{err}</p>}
    {error ? <ErrorBox error={error} retry={reload} /> : loading ? <Spinner /> : !data?.available ? <Card><Empty title="No evaluation run yet" hint={data?.message} /></Card> : (<>
      <p className="text-xs text-mute mb-3">{data.cases} cases · {data.mode} · {fmtDate(data.generated_at)} · avg latency {data.latency_ms.average} ms (p95 {data.latency_ms.p95} ms)</p>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">{rows.map(([l, k]) => <Stat key={k} label={l} value={M[k]?.value_pct == null ? "—" : `${M[k].value_pct}%`} sub={`n=${M[k]?.n}`} />)}</div>
      <Card className="p-4 mt-4"><p className="text-sm font-medium mb-3">Failed cases ({data.failures.length})</p>{!data.failures.length ? <p className="text-sm text-mute">None.</p> : <div className="space-y-3">{data.failures.map((f: any) => <div key={f.id} className="text-sm border-t border-line pt-3 first:border-0 first:pt-0"><p><span className="font-mono">{f.id}</span> <span className="text-mute">{(f.turns || []).slice(-1)[0]}</span></p><p className="text-xs text-mute mt-1 line-clamp-2">{f.response || f.error}</p></div>)}</div>}</Card></>)}</div>);
}

export function Knowledge() {
  const { data, error, loading } = useFetch<any>(() => api("/admin/knowledge"));
  const [q, setQ] = useState(""); const [res, setRes] = useState<any>(null); const [busy, setBusy] = useState(false);
  async function search() { setBusy(true); try { setRes(await api("/admin/knowledge/search", { body: { query: q } })); } finally { setBusy(false); } }
  return (<div><PageHeader title="Knowledge base" sub="Synthetic NovaCart policy documents indexed for retrieval." />
    <Card className="p-4 mb-4"><p className="text-sm font-medium mb-2">Test retrieval</p><form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.length > 1) search(); }}><input className="input" placeholder="e.g. how long does a refund take" value={q} onChange={(e) => setQ(e.target.value)} /><button className="btn btn-primary" disabled={busy}>Search</button></form>
      {res && <div className="mt-3 space-y-2">{res.results.length === 0 ? <p className="text-sm text-mute">No chunks above the relevance threshold.</p> : res.results.map((r: any) => <div key={r.chunk_id} className="text-sm border border-line rounded-lg p-3"><p className="text-xs text-mute"><span className="font-mono">{r.chunk_id}</span> · {r.source} — {r.section} · score {r.score}</p><p className="mt-1">{r.content}</p></div>)}<p className="text-xs text-mute">{res.latency_ms} ms</p></div>}</Card>
    {error ? <ErrorBox error={error} /> : loading || !data ? <Spinner /> : (<><p className="text-xs text-mute mb-3">{data.total_chunks} chunks · embeddings: {data.embedding_backend} · store: {data.vector_store}</p>
      <div className="grid md:grid-cols-2 gap-3">{data.documents.map((d: any) => <Card key={d.document} className="p-4"><p className="font-medium">{d.source}</p><p className="text-xs text-mute font-mono">{d.document} · {d.chunks} chunks</p><p className="text-xs text-mute mt-2">{d.sections.join(" · ")}</p></Card>)}</div></>)}</div>);
}

export function SystemHealth() {
  const { data, error, loading, reload } = useFetch<any>(() => api("/admin/system"));
  const row = (name: string, ok: boolean, detail: string) => <Card className="p-4 flex items-center justify-between"><div><p className="font-medium">{name}</p><p className="text-xs text-mute mt-0.5">{detail}</p></div><Badge tone={ok ? "green" : "red"}>{ok ? "up" : "down"}</Badge></Card>;
  return (<div><PageHeader title="System health" right={<button className="btn btn-ghost" onClick={reload}><RefreshCw className="w-4 h-4" />Recheck</button>} />
    {error ? <ErrorBox error={error} retry={reload} /> : loading || !data ? <Spinner /> : (<div className="grid md:grid-cols-2 gap-3">
      {row("Database", data.database.status === "up", `${data.database.engine} · ${data.database.latency_ms} ms`)}
      {row("Conversation memory", data.redis.backend === "redis", data.redis.backend === "redis" ? "Redis" : "Redis unreachable: using in-process fallback (state is lost on restart)")}
      {row("Vector search", data.vector_search.status === "up", data.vector_search.error || `${data.vector_search.latency_ms} ms`)}
      {row("LLM", !!data.llm.available, data.llm.provider === "demo" ? "Demo mode: deterministic extractive answers, no model required" : `${data.llm.provider} · ${data.llm.model}`)}
      <Card className="p-4 md:col-span-2 text-sm"><p className="font-medium mb-1">Monitoring</p><p className="text-mute">Prometheus <a className="text-brand underline" href={data.prometheus_url} target="_blank">{data.prometheus_url}</a> · Grafana <a className="text-brand underline" href={data.grafana_url} target="_blank">{data.grafana_url}</a> (login admin / admin) · raw metrics at <span className="font-mono">/metrics</span></p><p className="text-xs text-mute mt-2">Reference date: {data.as_of_date} · embeddings: {data.embedding}</p></Card></div>)}</div>);
}
