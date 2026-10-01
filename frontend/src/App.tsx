import { useEffect, useState } from "react";
import { api, getToken, setToken, User } from "./api";
import Login from "./Login";
import Chat from "./Chat";
import { History, Orders, Tickets } from "./Customer";
import { AdminTickets, Approvals, Conversations, Customers, Dashboard, Evaluation, Knowledge, SystemHealth } from "./Admin";
import { Spinner } from "./ui";
import { Activity, BookOpen, CheckSquare, ClipboardList, FlaskConical, History as HistoryIcon, LayoutDashboard, LogOut, MessageSquare, Moon, Package, Sun, Ticket, Users, MessagesSquare } from "lucide-react";

const CUSTOMER_NAV = [["chat", "Chat", MessageSquare], ["orders", "Orders", Package], ["tickets", "Tickets", Ticket], ["history", "History", HistoryIcon]] as const;
const ADMIN_NAV = [["dashboard", "Dashboard", LayoutDashboard], ["conversations", "Conversations", MessagesSquare], ["atickets", "Tickets", ClipboardList], ["approvals", "Approvals", CheckSquare],
  ["customers", "Customers", Users], ["evaluation", "AI Evaluation", FlaskConical], ["knowledge", "Knowledge Base", BookOpen], ["system", "System Health", Activity]] as const;

export default function App() {
  const [user, setUser] = useState<User | null>(null); const [boot, setBoot] = useState(!!getToken());
  const [dark, setDark] = useState(() => localStorage.getItem("ns_theme") ? localStorage.getItem("ns_theme") === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
  const [page, setPage] = useState("chat"); const [resume, setResume] = useState<string | null>(null);
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); localStorage.setItem("ns_theme", dark ? "dark" : "light"); }, [dark]);
  useEffect(() => { if (getToken()) api("/me").then(setUser).catch(() => setToken(null)).finally(() => setBoot(false)); }, []);
  useEffect(() => { const f = () => setUser(null); window.addEventListener("ns-logout", f); return () => window.removeEventListener("ns-logout", f); }, []);
  const staff = user && user.role !== "CUSTOMER";
  useEffect(() => { if (user) setPage(staff ? "dashboard" : "chat"); }, [user?.customer_id]);
  if (boot) return <Spinner />;
  if (!user) return <Login onLogin={setUser} />;
  const nav = staff ? ADMIN_NAV : CUSTOMER_NAV; const isAdmin = user.role === "ADMIN";
  const visible = nav.filter(([k]) => isAdmin || !["approvals"].includes(k) ? true : false);
  return (
    <div className="h-full flex">
      <aside className="w-16 lg:w-60 shrink-0 border-r border-line bg-card flex flex-col">
        <div className="h-16 px-4 flex items-center gap-2 font-display text-lg border-b border-line"><span className="w-8 h-8 rounded-lg bg-brand text-white grid place-items-center text-sm font-sans font-semibold shrink-0">N</span><span className="hidden lg:block">NovaSupport</span></div>
        <nav className="flex-1 p-2 space-y-1">{visible.map(([k, label, Icon]) => (
          <button key={k} onClick={() => setPage(k)} className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition ${page === k ? "bg-brand/12 text-brand font-medium" : "text-mute hover:bg-line/50 hover:text-ink"}`} aria-current={page === k}>
            <Icon className="w-4 h-4 shrink-0" /><span className="hidden lg:block">{label}</span></button>))}</nav>
        <div className="p-3 border-t border-line space-y-2">
          <div className="hidden lg:block px-1"><p className="text-sm font-medium truncate">{user.name}</p><p className="text-xs text-mute">{user.role === "CUSTOMER" ? `${user.membership_tier} member` : user.role.replace("_", " ").toLowerCase()}</p></div>
          <div className="flex gap-2"><button className="btn btn-ghost flex-1 !px-2" onClick={() => setDark(!dark)} aria-label="Toggle theme">{dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}</button>
            <button className="btn btn-ghost flex-1 !px-2" onClick={() => { setToken(null); setUser(null); }} aria-label="Sign out"><LogOut className="w-4 h-4" /></button></div></div>
      </aside>
      <main className={`flex-1 min-w-0 ${page === "chat" ? "p-4 lg:p-6 overflow-hidden" : "p-6 lg:p-8 overflow-y-auto"}`}>
        {page === "chat" && <Chat user={user} resume={resume} onResumed={() => setResume(null)} />}
        {page === "orders" && <Orders />}{page === "tickets" && <Tickets />}
        {page === "history" && <History open={(id) => { setResume(id); setPage("chat"); }} />}
        {page === "dashboard" && <Dashboard />}{page === "conversations" && <Conversations />}{page === "atickets" && <AdminTickets />}
        {page === "approvals" && <Approvals />}{page === "customers" && <Customers />}{page === "evaluation" && <Evaluation canRun={isAdmin} />}
        {page === "knowledge" && <Knowledge />}{page === "system" && <SystemHealth />}
      </main>
    </div>
  );
}
