import { useState } from "react";
import { api, setToken, User } from "./api";
import { Spinner } from "./ui";
import { useFetch } from "./ui";
import { ShieldCheck, Bot, Search } from "lucide-react";

export default function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const demo = useFetch<any[]>(() => api("/auth/demo-users"));
  async function submit(e?: string, p?: string) {
    setBusy(true); setErr("");
    try { const r = await api("/auth/login", { body: { email: e ?? email, password: p ?? password } }); setToken(r.access_token); onLogin(r.user); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  const role = (r: string) => (r === "CUSTOMER" ? "Customer" : r === "ADMIN" ? "Admin" : "Support agent");
  return (
    <div className="min-h-full grid lg:grid-cols-[1.1fr_1fr]">
      <div className="hidden lg:flex flex-col justify-between p-12 bg-ink text-paper relative overflow-hidden">
        <div className="absolute -right-24 -top-24 w-96 h-96 rounded-full bg-brand/30 blur-3xl" />
        <div className="flex items-center gap-2 font-display text-xl relative"><span className="w-8 h-8 rounded-lg bg-brand grid place-items-center text-white text-sm font-sans font-semibold">N</span>NovaSupport AI</div>
        <div className="relative max-w-md">
          <h1 className="font-display text-5xl leading-[1.05] tracking-tight">Support that checks the facts before it speaks.</h1>
          <ul className="mt-8 space-y-4 text-paper/80 text-sm">
            <li className="flex gap-3"><Search className="w-5 h-5 text-brand shrink-0" />Answers come from NovaCart's policies and your real order records, with sources cited.</li>
            <li className="flex gap-3"><ShieldCheck className="w-5 h-5 text-brand shrink-0" />Refunds and cancellations need your confirmation, and large ones a human's approval.</li>
            <li className="flex gap-3"><Bot className="w-5 h-5 text-brand shrink-0" />Anything the assistant can't verify goes to a person, with the full context attached.</li>
          </ul>
        </div>
        <p className="text-xs text-paper/50 relative">Demo environment. NovaCart Technologies and all of its customers, orders and documents are synthetic.</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm animate-rise">
          <h2 className="font-display text-3xl">Sign in</h2><p className="text-mute text-sm mt-1 mb-6">Use a demo account below, or enter credentials.</p>
          <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="space-y-3">
            <input className="input" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
            <input className="input" type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            {err && <p className="text-bad text-sm" role="alert">{err}</p>}
            <button className="btn btn-primary w-full" disabled={busy || !email || !password}>{busy ? "Signing in…" : "Sign in"}</button>
          </form>
          <div className="mt-8"><p className="text-xs text-mute mb-2">Demo accounts (password shown is synthetic)</p>
            {demo.loading ? <Spinner /> : demo.error ? <p className="text-sm text-bad">{demo.error}</p> : (
              <div className="space-y-2">{demo.data?.map((u) => (
                <button key={u.customer_id} onClick={() => submit(u.email, u.password)} className="card w-full text-left px-3 py-2.5 hover:border-brand transition flex justify-between items-center">
                  <span><span className="text-sm font-medium block">{u.name}</span><span className="text-xs text-mute">{u.email}</span></span>
                  <span className="text-xs text-mute">{role(u.role)}{u.role === "CUSTOMER" ? ` · ${u.membership_tier}` : ""}</span></button>))}</div>)}
          </div>
        </div>
      </div>
    </div>
  );
}
