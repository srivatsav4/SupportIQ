import { ReactNode, useEffect, useState } from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

const TONES: Record<string, string> = {
  green: "bg-ok/12 text-ok", amber: "bg-warn/15 text-warn", red: "bg-bad/12 text-bad", blue: "bg-info/12 text-info", gray: "bg-line/70 text-mute", brand: "bg-brand/12 text-brand",
};
const STATUS_TONE: Record<string, string> = {
  Delivered: "green", Shipped: "blue", "Out for Delivery": "blue", Processing: "amber", Confirmed: "amber", Pending: "amber", Cancelled: "gray", Returned: "gray",
  Open: "amber", "In Progress": "blue", Resolved: "green", Closed: "gray", Low: "gray", Medium: "blue", High: "amber", Urgent: "red",
  ai_resolved: "green", escalated: "red", open: "amber", PENDING: "amber", EXECUTED: "green", APPROVED: "green", REJECTED: "red", FAILED: "red",
  Approved: "green", Completed: "green", Initiated: "amber", Rejected: "red", up: "green", down: "red",
};
export const Badge = ({ children, tone }: { children: ReactNode; tone?: string }) => {
  const t = tone || STATUS_TONE[String(children)] || "gray";
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TONES[t]}`}>{String(children).replace("_", " ")}</span>;
};
export const Card = ({ children, className = "" }: { children: ReactNode; className?: string }) => <div className={`card ${className}`}>{children}</div>;
export const PageHeader = ({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) => (
  <div className="flex items-end justify-between gap-4 mb-6">
    <div><h1 className="font-display text-3xl tracking-tight">{title}</h1>{sub && <p className="text-mute text-sm mt-1 max-w-2xl">{sub}</p>}</div>{right}
  </div>
);
export const Spinner = ({ label = "Loading" }: { label?: string }) => <div className="flex items-center gap-2 text-mute text-sm py-10 justify-center"><Loader2 className="w-4 h-4 animate-spin" />{label}…</div>;
export const ErrorBox = ({ error, retry }: { error: string; retry?: () => void }) => (
  <div className="card p-5 flex items-start gap-3 border-bad/40"><AlertTriangle className="w-5 h-5 text-bad shrink-0" />
    <div className="text-sm"><p className="font-medium">Something went wrong</p><p className="text-mute">{error}</p>{retry && <button className="btn btn-ghost mt-3" onClick={retry}>Try again</button>}</div></div>
);
export const Empty = ({ title, hint }: { title: string; hint?: string }) => (
  <div className="py-14 text-center text-mute"><Inbox className="w-8 h-8 mx-auto mb-3 opacity-60" /><p className="font-medium text-ink">{title}</p>{hint && <p className="text-sm mt-1">{hint}</p>}</div>
);
export const Skeleton = ({ className = "h-20" }: { className?: string }) => <div className={`skeleton ${className}`} />;

export function useFetch<T>(fn: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true; setLoading(true); setError(null);
    fn().then((d) => live && setData(d)).catch((e) => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [...deps, tick]);
  return { data, error, loading, reload: () => setTick((x) => x + 1) };
}
export const fmtDate = (s?: string | null) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
export const fmtDay = (s?: string | null) => (s ? new Date(s).toLocaleDateString(undefined, { dateStyle: "medium" }) : "—");
export const money = (n: number) => `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export const pct = (n: number | null | undefined, d = 1) => (n === null || n === undefined ? "—" : `${(n * 100).toFixed(d)}%`);
