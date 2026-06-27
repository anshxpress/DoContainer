"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ShieldAlert, Mail, Lock, User, Building, Loader2, FileSearch2 } from "lucide-react";

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
    const token = localStorage.getItem("docscope_token");
    if (token) {
      router.push("/dashboard");
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const url = isRegister ? "/api/v1/auth/register" : "/api/v1/auth/login";
    const payload = isRegister 
      ? {
          email: email.trim(),
          password: password,
          first_name: firstName.trim() || null,
          last_name: lastName.trim() || null,
          org_name: orgName.trim(),
        }
      : {
          email: email.trim(),
          password: password,
        };

    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.detail || "Authentication failed. Please check credentials.");
      }

      // Store auth credentials
      localStorage.setItem("docscope_token", data.access_token);
      
      // Redirect to dashboard
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Something went wrong. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Background Decorative Glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-emerald-500/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-10 left-10 w-[300px] h-[300px] bg-cyan-500/5 rounded-full blur-[100px] pointer-events-none" />

      {/* Main Login Card */}
      <div className="w-full max-w-md glass-card rounded-3xl p-8 border border-white/5 relative z-10 space-y-8 shadow-2xl">
        {/* Brand logo */}
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="p-3 rounded-2xl bg-emerald-500/15 text-emerald-400">
            <FileSearch2 size={36} className="text-glow" />
          </div>
          <h1 className="text-2xl font-extrabold tracking-wider bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent mt-2">
            DOCSCOPE AI
          </h1>
          <p className="text-xs text-zinc-500">
            {isRegister ? "Register your enterprise workspace" : "Sign in to your document intelligence portal"}
          </p>
        </div>

        {/* Error message */}
        {error && (
          <div className="p-4 rounded-2xl bg-red-500/10 border border-red-500/25 text-red-400 text-xs flex items-start gap-2.5">
            <ShieldAlert size={16} className="shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegister && (
            <>
              {/* Names */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">First Name</label>
                  <div className="relative">
                    <User size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
                    <input
                      type="text"
                      required
                      placeholder="Jane"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 bg-zinc-900/60 border border-white/5 rounded-xl text-zinc-200 text-sm focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 outline-none transition-all"
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Last Name</label>
                  <div className="relative">
                    <User size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
                    <input
                      type="text"
                      required
                      placeholder="Doe"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 bg-zinc-900/60 border border-white/5 rounded-xl text-zinc-200 text-sm focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 outline-none transition-all"
                    />
                  </div>
                </div>
              </div>

              {/* Organization name */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Organization Name</label>
                <div className="relative">
                  <Building size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
                  <input
                    type="text"
                    required
                    placeholder="Acme Corp"
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-zinc-900/60 border border-white/5 rounded-xl text-zinc-200 text-sm focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 outline-none transition-all"
                  />
                </div>
              </div>
            </>
          )}

          {/* Email */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Email Address</label>
            <div className="relative">
              <Mail size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="email"
                required
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-zinc-900/60 border border-white/5 rounded-xl text-zinc-200 text-sm focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 outline-none transition-all"
              />
            </div>
          </div>

          {/* Password */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">Password</label>
              {!isRegister && (
                <button type="button" className="text-[10px] text-emerald-400 hover:underline">
                  Forgot Password?
                </button>
              )}
            </div>
            <div className="relative">
              <Lock size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="password"
                required
                minLength={8}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-zinc-900/60 border border-white/5 rounded-xl text-zinc-200 text-sm focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 outline-none transition-all"
              />
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-3 mt-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-700/50 text-white text-sm font-semibold shadow-lg shadow-emerald-600/15 hover:shadow-emerald-600/25 transition-all duration-200"
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Processing...</span>
              </>
            ) : (
              <span>{isRegister ? "Create Enterprise Account" : "Access Workspace"}</span>
            )}
          </button>
        </form>

        {/* Toggle Mode */}
        <div className="text-center">
          <button
            type="button"
            onClick={() => {
              setIsRegister(!isRegister);
              setError(null);
            }}
            className="text-xs text-zinc-400 hover:text-emerald-400 transition-colors"
          >
            {isRegister ? "Already have an account? Sign In" : "Need a workspace? Create an Account"}
          </button>
        </div>
      </div>
    </div>
  );
}
