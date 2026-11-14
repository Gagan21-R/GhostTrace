import { Link2, Scale, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Logo } from "../components/Layout";
import { useAuth } from "../lib/auth";

export default function LoginPage({ register = false }: { register?: boolean }) {
  const { login, register: doRegister } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState(""); const [name, setName] = useState(""); const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { register ? await doRegister(email, name, pw) : await login(email, pw); nav("/"); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden bg-ink-950 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <svg className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.18]" aria-hidden>
          {Array.from({ length: 26 }).map((_, i) => <circle key={i} cx={`${(i * 37) % 100}%`} cy={`${(i * 53) % 100}%`} r={2 + (i % 3)} fill="#3b82f6" />)}
          {Array.from({ length: 22 }).map((_, i) => <line key={i} x1={`${(i * 37) % 100}%`} y1={`${(i * 53) % 100}%`} x2={`${((i + 3) * 37) % 100}%`} y2={`${((i + 3) * 53) % 100}%`} stroke="#94a3b8" strokeWidth="0.6" />)}
        </svg>
        <div className="relative"><Logo dark /></div>
        <div className="relative max-w-md">
          <h1 className="text-[34px] font-semibold leading-tight tracking-tight">Every clue connected.<br />Every claim traceable.<br /><span className="text-accent-500">Every conclusion challenged.</span></h1>
          <div className="mt-10 space-y-4 text-sm text-slate-300">
            <div className="flex gap-3"><ShieldCheck className="h-5 w-5 shrink-0 text-accent-500" />Originals are hashed at intake and never modified.</div>
            <div className="flex gap-3"><Link2 className="h-5 w-5 shrink-0 text-accent-500" />Every finding links back to the page, message or row it came from.</div>
            <div className="flex gap-3"><Scale className="h-5 w-5 shrink-0 text-accent-500" />A counter-investigation agent tests each hypothesis before a human reviews it.</div>
          </div>
        </div>
        <div className="relative text-xs text-slate-500">Assists investigators. Does not determine guilt.</div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h2 className="text-xl font-semibold">{register ? "Create an account" : "Sign in"}</h2>
          <p className="mt-1 text-sm text-slate-500">{register ? "New accounts get the Investigator role." : "Access your investigation workspace."}</p>
          <div className="mt-6 space-y-3">
            {register && <div><label className="label">Full name</label><input className="input mt-1" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} /></div>}
            <div><label className="label">Email</label><input className="input mt-1" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" /></div>
            <div><label className="label">Password</label><input className="input mt-1" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required autoComplete={register ? "new-password" : "current-password"} />
              {register && <div className="mt-1 text-[11px] text-slate-500">At least 10 characters, with an uppercase letter and a digit.</div>}</div>
          </div>
          {err && <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
          <button className="btn-primary mt-5 w-full justify-center py-2.5" disabled={busy}>{busy ? "Please wait…" : register ? "Create account" : "Sign in"}</button>
          <div className="mt-4 text-center text-sm text-slate-500">
            {register ? <>Already have an account? <Link to="/login" className="font-medium text-accent-700">Sign in</Link></> :
              <>No account? <Link to="/register" className="font-medium text-accent-700">Create one</Link></>}
          </div>
        </form>
      </div>
    </div>
  );
}
