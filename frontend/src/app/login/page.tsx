"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ShieldAlert,
  Mail,
  Lock,
  User,
  Loader2,
  FileSearch2,
  ScanLine,
  MessageSquare,
  Search,
  Copy,
  ChevronRight,
  Building,
} from "lucide-react";
import { CURRENT_APP_MODE, AppMode } from "../../config/appMode";

// ─── Left-panel feature pill ──────────────────────────────────────────────────
function FeaturePill({
  icon: Icon,
  label,
}: {
  icon: React.ComponentType<any>;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-white/5 border border-white/5 text-xs text-zinc-300 font-medium">
      <Icon size={14} className="text-[#82C8E5] shrink-0" />
      {label}
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If already logged in, redirect straight to dashboard
  useEffect(() => {
    const token = localStorage.getItem("DoContainer_token");
    if (token) router.push("/dashboard");
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const url = isRegister ? "/api/v1/auth/register" : "/api/v1/auth/login";
    const payload = isRegister
      ? {
          email: email.trim(),
          password,
          first_name: firstName.trim() || null,
          last_name: lastName.trim() || null,
          // org_name omitted in Personal Edition — auto-provisioned server-side
          ...(CURRENT_APP_MODE !== AppMode.PERSONAL && orgName.trim()
            ? { org_name: orgName.trim() }
            : {}),
        }
      : { email: email.trim(), password };

    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok)
        throw new Error(data.detail || "Authentication failed. Please check credentials.");
      localStorage.setItem("DoContainer_token", data.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Something went wrong. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#03030a] flex overflow-hidden">
      {/* ── Left panel — branding + feature list ────────────────────────────── */}
      <div className="hidden lg:flex flex-col justify-between w-[480px] shrink-0 relative border-r border-white/5 p-12">
        {/* Background glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-emerald-500/8 via-transparent to-indigo-500/5" />
          <div className="absolute bottom-0 left-0 w-80 h-80 bg-[#0047AB]/10 rounded-full blur-[120px]" />
        </div>

        <div className="relative z-10 space-y-10">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 group w-fit">
            <div className="p-2.5 rounded-xl bg-[#0047AB]/10 group-hover:bg-[#0047AB]/20 transition-colors">
              <FileSearch2 size={24} className="text-[#82C8E5]" />
            </div>
            <div>
              <span className="block font-bold text-lg tracking-wide bg-gradient-to-r from-[#82C8E5] to-[#dff0fc] bg-clip-text text-transparent">
                DoContainer
              </span>
              <span className="block text-[10px] text-zinc-500 uppercase tracking-widest font-medium">
                Personal AI Workspace
              </span>
            </div>
          </Link>

          {/* Headline */}
          <div className="space-y-4">
            <h1 className="text-4xl font-black tracking-tight leading-tight text-zinc-100">
              Your documents,{" "}
              <span className="bg-gradient-to-r from-[#82C8E5] to-[#82C8E5] bg-clip-text text-transparent">
                finally intelligent.
              </span>
            </h1>
            <p className="text-sm text-zinc-400 leading-relaxed">
              Upload PDFs, ask questions in plain English, and get instant answers.
              Semantic search, adaptive OCR, and AI summaries — all in one personal workspace.
            </p>
          </div>

          {/* Feature pills */}
          <div className="grid grid-cols-2 gap-3">
            <FeaturePill icon={ScanLine}     label="Adaptive OCR" />
            <FeaturePill icon={Search}       label="Semantic Search" />
            <FeaturePill icon={MessageSquare}label="AI Chat" />
            <FeaturePill icon={FileSearch2}  label="AI Summaries" />
            <FeaturePill icon={Copy}         label="Duplicate Detection" />
            <FeaturePill icon={FileSearch2}  label="Hybrid Search" />
          </div>

          {/* Example query */}
          <div className="rounded-2xl border border-white/5 bg-white/3 p-5 space-y-3">
            <p className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold">
              Example query
            </p>
            <div className="flex items-start gap-3">
              <div className="mt-0.5 p-1.5 rounded-lg bg-[#0047AB]/15 shrink-0">
                <MessageSquare size={13} className="text-[#82C8E5]" />
              </div>
              <p className="text-sm text-zinc-300 italic leading-relaxed">
                &ldquo;Summarise the key risks in my Q3 financial report and compare them with Q2.&rdquo;
              </p>
            </div>
            <div className="flex items-start gap-3">
              <div className="mt-0.5 p-1.5 rounded-lg bg-zinc-800 shrink-0">
                <FileSearch2 size={13} className="text-zinc-400" />
              </div>
              <p className="text-xs text-zinc-500 leading-relaxed">
                DoContainer retrieves the most relevant pages from your uploaded reports and generates a grounded answer with page citations.
              </p>
            </div>
          </div>
        </div>

        {/* Footer note */}
        <p className="relative z-10 text-[10px] text-zinc-600">
          Enterprise Edition preserved · Set{" "}
          <code className="font-mono text-zinc-500">APP_MODE=enterprise</code> to restore
        </p>
      </div>

      {/* ── Right panel — auth form ──────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 relative">
        {/* Mobile glow */}
        <div className="absolute inset-0 pointer-events-none lg:hidden">
          <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-[#0047AB]/8 rounded-full blur-[120px]" />
        </div>

        {/* Mobile logo */}
        <div className="lg:hidden mb-8 flex items-center gap-3 relative z-10">
          <div className="p-2 rounded-xl bg-[#0047AB]/10">
            <FileSearch2 size={22} className="text-[#82C8E5]" />
          </div>
          <div>
            <span className="block font-bold text-base tracking-wide bg-gradient-to-r from-[#82C8E5] to-[#dff0fc] bg-clip-text text-transparent">
              DoContainer
            </span>
            <span className="block text-[10px] text-zinc-500 uppercase tracking-widest font-medium">
              Personal AI Workspace
            </span>
          </div>
        </div>

        {/* Card */}
        <div className="w-full max-w-sm relative z-10 space-y-7">
          {/* Card header */}
          <div className="space-y-1">
            <h2 className="text-2xl font-black text-zinc-100">
              {isRegister ? "Create your workspace" : "Welcome back"}
            </h2>
            <p className="text-sm text-zinc-500">
              {isRegister
                ? "Your personal workspace is created automatically."
                : "Sign in to your DoContainer workspace."}
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/25 text-red-400 text-xs flex items-start gap-2.5">
              <ShieldAlert size={15} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name fields (register only) */}
            {isRegister && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                      First Name
                    </label>
                    <div className="relative">
                      <User size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
                      <input
                        type="text"
                        required
                        placeholder="Jane"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        className="w-full pl-9 pr-3 py-2.5 bg-zinc-900 border border-white/5 rounded-xl text-zinc-200 text-sm placeholder:text-zinc-700 focus:border-[#0047AB]/60 focus:ring-1 focus:ring-[#0047AB]/20 outline-none transition-all"
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                      Last Name
                    </label>
                    <div className="relative">
                      <User size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
                      <input
                        type="text"
                        placeholder="Doe"
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                        className="w-full pl-9 pr-3 py-2.5 bg-zinc-900 border border-white/5 rounded-xl text-zinc-200 text-sm placeholder:text-zinc-700 focus:border-[#0047AB]/60 focus:ring-1 focus:ring-[#0047AB]/20 outline-none transition-all"
                      />
                    </div>
                  </div>
                </div>

                {/* Organization name — Enterprise Feature (hidden in Personal Edition) */}
                {CURRENT_APP_MODE !== AppMode.PERSONAL && (
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                      Organization Name
                    </label>
                    <div className="relative">
                      <Building size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
                      <input
                        type="text"
                        required
                        placeholder="Acme Corp"
                        value={orgName}
                        onChange={(e) => setOrgName(e.target.value)}
                        className="w-full pl-9 pr-3 py-2.5 bg-zinc-900 border border-white/5 rounded-xl text-zinc-200 text-sm placeholder:text-zinc-700 focus:border-[#0047AB]/60 focus:ring-1 focus:ring-[#0047AB]/20 outline-none transition-all"
                      />
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                Email Address
              </label>
              <div className="relative">
                <Mail size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
                <input
                  type="email"
                  required
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-9 pr-3 py-2.5 bg-zinc-900 border border-white/5 rounded-xl text-zinc-200 text-sm placeholder:text-zinc-700 focus:border-[#0047AB]/60 focus:ring-1 focus:ring-[#0047AB]/20 outline-none transition-all"
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                  Password
                </label>
                {!isRegister && (
                  <button type="button" className="text-[10px] text-[#82C8E5] hover:underline">
                    Forgot password?
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock size={13} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-600" />
                <input
                  type="password"
                  required
                  minLength={8}
                  placeholder="Min. 8 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-9 pr-3 py-2.5 bg-zinc-900 border border-white/5 rounded-xl text-zinc-200 text-sm placeholder:text-zinc-700 focus:border-[#0047AB]/60 focus:ring-1 focus:ring-[#0047AB]/20 outline-none transition-all"
                />
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-[#0047AB] hover:bg-[#1a5fc4] disabled:bg-[#0047AB]/30 disabled:cursor-not-allowed text-white text-sm font-semibold shadow-lg shadow-[#0047AB]/30 hover:shadow-[#0047AB]/40 transition-all duration-200 mt-2"
            >
              {loading ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  <span>Processing…</span>
                </>
              ) : (
                <>
                  <span>{isRegister ? "Create workspace" : "Sign in"}</span>
                  <ChevronRight size={15} />
                </>
              )}
            </button>
          </form>

          {/* Toggle sign in / register */}
          <div className="text-center">
            <button
              type="button"
              onClick={() => {
                setIsRegister(!isRegister);
                setError(null);
              }}
              className="text-xs text-zinc-500 hover:text-[#82C8E5] transition-colors"
            >
              {isRegister
                ? "Already have an account? Sign in →"
                : "Don't have an account? Create one →"}
            </button>
          </div>

          {/* Back to landing */}
          <div className="text-center">
            <Link href="/" className="text-[10px] text-zinc-700 hover:text-zinc-500 transition-colors">
              ← Back to home
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
