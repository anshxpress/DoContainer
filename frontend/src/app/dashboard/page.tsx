"use client";

import React, { useState, useEffect } from "react";
import { apiClient } from "../../lib/apiClient";
import { 
  FileText, 
  Users, 
  Layers, 
  Clock, 
  ArrowUpRight, 
  Plus, 
  FolderPlus,
  Folder,
  TrendingUp,
  Cpu,
  HardDrive
} from "lucide-react";
import Link from "next/link";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
  CartesianGrid
} from "recharts";
import PersonalDashboard from "./personal/page";
import { CURRENT_APP_MODE, AppMode } from "../../config/appMode";

// Colors matching the dark emerald theme
const COLORS = ["#10b981", "#06b6d4", "#6366f1", "#f59e0b"];

interface StatCardProps {
  title: string;
  value: string;
  change: string;
  icon: React.ComponentType<any>;
}

function StatCard({ title, value, change, icon: Icon }: StatCardProps) {
  return (
    <div className="glass-card p-6 rounded-2xl relative overflow-hidden group">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-zinc-400 font-medium">{title}</span>
        <div className="p-2.5 rounded-xl bg-zinc-800/80 text-zinc-400 group-hover:text-[#82C8E5] group-hover:bg-[#0047AB]/10 transition-colors">
          <Icon size={20} />
        </div>
      </div>
      <div className="space-y-1">
        <h3 className="text-3xl font-bold tracking-tight text-zinc-100">{value}</h3>
        <p className="text-xs text-[#82C8E5] font-semibold flex items-center gap-1">
          {change} <span className="text-zinc-500 font-normal">vs last month</span>
        </p>
      </div>
      {/* Decorative background glow */}
      <div className="absolute -right-6 -bottom-6 w-24 h-24 bg-[#0047AB]/5 rounded-full blur-2xl group-hover:bg-[#0047AB]/10 transition-all duration-300" />
    </div>
  );
}

// Helper: Format bytes cleanly
function formatBytes(bytes: number) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

// Helper: Format relative time
function formatTime(isoStr: string, mounted: boolean = false) {
  try {
    const diffMs = Date.now() - new Date(isoStr).getTime();
    const diffMins = Math.floor(diffMs / (60 * 1000));
    const diffHours = Math.floor(diffMs / (3600 * 1000));
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
    if (!mounted) {
      return isoStr.substring(0, 10);
    }
    return new Date(isoStr).toLocaleDateString();
  } catch {
    return "recent";
  }
}

// High-quality mock data for demo mode / fallback
const MOCK_ANALYTICS = {
  totals: {
    documents: 1248,
    pages_rendered: 8492,
    storage_bytes: 2000000000000, // ~1.82 TB
    api_tokens: 456800,
    active_users: 48
  },
  recent_audits: [
    { action: "document.upload", user: "john.doe@docontainer.io", time: new Date(Date.now() - 2 * 3600 * 1000).toISOString() },
    { action: "document.search", user: "system_admin", time: new Date(Date.now() - 5 * 3600 * 1000).toISOString() },
    { action: "chat.ask", user: "alice@docontainer.io", time: new Date(Date.now() - 24 * 3600 * 1000).toISOString() }
  ],
  daily_trends: [
    { date: "Jun 20", tokens: 12000, pages: 120, storage_mb: 250 },
    { date: "Jun 21", tokens: 15400, pages: 180, storage_mb: 410 },
    { date: "Jun 22", tokens: 9800, pages: 90, storage_mb: 120 },
    { date: "Jun 23", tokens: 22000, pages: 340, storage_mb: 850 },
    { date: "Jun 24", tokens: 18500, pages: 280, storage_mb: 610 },
    { date: "Jun 25", tokens: 25000, pages: 420, storage_mb: 950 },
    { date: "Jun 26", tokens: 32000, pages: 580, storage_mb: 1200 }
  ],
  file_type_breakdown: [
    { name: "PDF", value: 850, size_mb: 1500000 },
    { name: "DOCX", value: 240, size_mb: 320000 },
    { name: "PPTX", value: 110, size_mb: 180000 },
    { name: "Images", value: 48, size_mb: 60000 }
  ]
};

export default function Dashboard() {
  if (CURRENT_APP_MODE === AppMode.PERSONAL) {
    return <PersonalDashboard />;
  }

  const [mounted, setMounted] = useState(false);
  const [data, setData] = useState<typeof MOCK_ANALYTICS | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);

    const fetchAnalytics = async () => {
      try {
        const result = await apiClient.get("/api/v1/analytics/dashboard");
        setData(result);
        setLoading(false);
      } catch (err: any) {
        console.error("Failed to fetch analytics from backend", err);
        setError(err.message || "Failed to fetch analytics from backend.");
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, []);

  const folders = [
    { id: "1", name: "Financial Audits", items: "12 files", color: "from-[#0047AB]/15 to-[#0047AB]/8" },
    { id: "2", name: "Legal Contracts", items: "8 files", color: "from-blue-500/20 to-indigo-500/20" },
    { id: "3", name: "Engineering Specs", items: "24 files", color: "from-purple-500/20 to-pink-500/20" },
  ];

  if (loading) {
    return (
      <div className="space-y-8 animate-pulse">
        {/* Header Skeleton */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="h-8 w-64 bg-zinc-800/50 rounded-lg mb-2"></div>
            <div className="h-4 w-48 bg-zinc-800/30 rounded-lg"></div>
          </div>
          <div className="flex items-center gap-3">
            <div className="h-10 w-32 bg-zinc-800/50 rounded-xl"></div>
            <div className="h-10 w-40 bg-emerald-900/20 rounded-xl"></div>
          </div>
        </div>

        {/* Stats Grid Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass-card p-6 rounded-2xl h-32">
              <div className="flex justify-between mb-4">
                <div className="h-4 w-24 bg-zinc-800/50 rounded"></div>
                <div className="h-8 w-8 bg-zinc-800/50 rounded-xl"></div>
              </div>
              <div className="space-y-2">
                <div className="h-8 w-32 bg-zinc-800/50 rounded"></div>
                <div className="h-3 w-40 bg-zinc-800/30 rounded"></div>
              </div>
            </div>
          ))}
        </div>

        {/* Main Charts Skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 glass-panel p-6 rounded-3xl h-[400px]">
            <div className="h-6 w-48 bg-zinc-800/50 rounded mb-8"></div>
            <div className="w-full h-[280px] bg-zinc-800/30 rounded-xl"></div>
          </div>
          <div className="glass-panel p-6 rounded-3xl h-[400px]">
            <div className="h-6 w-48 bg-zinc-800/50 rounded mb-8"></div>
            <div className="w-full h-[280px] bg-zinc-800/30 rounded-full w-48 h-48 mx-auto mt-8"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-[80vh] items-center justify-center">
        <div className="flex flex-col items-center text-red-400 bg-red-500/10 p-8 rounded-2xl border border-red-500/20">
          <p className="font-semibold mb-2">Error loading analytics</p>
          <p className="text-sm opacity-80">{error || "Unknown error occurred"}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Dashboard Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
            Workspace Overview
          </h1>
          <p className="text-sm text-zinc-400">
            Welcome back to <span className="text-[#82C8E5] font-semibold">DoContainer Inc</span>. Monitor your document operations.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-white/5 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold transition-colors">
            <FolderPlus size={16} />
            <span>New Folder</span>
          </button>
          <Link 
            href="/dashboard/upload" 
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#0047AB] hover:bg-[#1a5fc4] text-white text-xs font-semibold shadow-lg shadow-[#0047AB]/25 transition-all duration-200"
          >
            <Plus size={16} />
            <span>Upload Document</span>
          </Link>
        </div>
      </div>

      {/* Stats Cards Section */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Total Documents" value={data.totals.documents.toLocaleString()} change="+12.3%" icon={FileText} />
        <StatCard title="Rendered Pages" value={data.totals.pages_rendered.toLocaleString()} change="+18.7%" icon={Layers} />
        <StatCard title="Active Team Members" value={data.totals.active_users.toLocaleString()} change="+4.1%" icon={Users} />
        <StatCard title="Storage Consumed" value={formatBytes(data.totals.storage_bytes)} change="+8.9%" icon={Clock} />
      </div>

      {/* Recharts Analytics Widgets */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Token consumption chart */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-white/5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-zinc-200 text-base">API Token Consumption</h3>
              <p className="text-xs text-zinc-500">Gemini LLM tokens consumed over last 7 days</p>
            </div>
            <TrendingUp size={20} className="text-[#82C8E5]" />
          </div>
          <div className="h-[280px] w-full">
            {mounted ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.daily_trends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorTokens" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="date" stroke="#71717a" fontSize={11} tickLine={false} />
                  <YAxis stroke="#71717a" fontSize={11} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a", borderRadius: "12px" }}
                    labelStyle={{ color: "#a1a1aa", fontSize: "11px", fontWeight: 600 }}
                    itemStyle={{ color: "#10b981", fontSize: "12px" }}
                  />
                  <Area type="monotone" dataKey="tokens" name="Tokens" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorTokens)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="w-full h-full bg-zinc-900/40 animate-pulse rounded-xl" />
            )}
          </div>
        </div>

        {/* Storage breakdown chart */}
        <div className="glass-panel p-6 rounded-2xl border border-white/5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-zinc-200 text-base">Storage Breakdown</h3>
              <p className="text-xs text-zinc-500">Resource counts by format type</p>
            </div>
            <HardDrive size={20} className="text-[#82C8E5]" />
          </div>
          <div className="h-[280px] w-full flex flex-col justify-between items-center">
            {mounted ? (
              <>
                <div className="h-[180px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={data.file_type_breakdown}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {data.file_type_breakdown.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a", borderRadius: "12px" }}
                        itemStyle={{ fontSize: "12px" }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 pb-2">
                  {data.file_type_breakdown.map((entry, index) => (
                    <div key={entry.name} className="flex items-center gap-1.5 text-xs text-zinc-300">
                      <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                      <span className="font-medium">{entry.name}</span>
                      <span className="text-zinc-500">({entry.value})</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="w-full h-full bg-zinc-900/40 animate-pulse rounded-xl" />
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Processing activity (daily pages) */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-white/5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-zinc-200 text-base">Ingestion Pipeline Activity</h3>
              <p className="text-xs text-zinc-500">Rendered document pages count per day</p>
            </div>
            <Cpu size={20} className="text-[#6D8196]" />
          </div>
          <div className="h-[240px] w-full">
            {mounted ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.daily_trends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="date" stroke="#71717a" fontSize={11} tickLine={false} />
                  <YAxis stroke="#71717a" fontSize={11} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a", borderRadius: "12px" }}
                    labelStyle={{ color: "#a1a1aa", fontSize: "11px", fontWeight: 600 }}
                    itemStyle={{ color: "#818cf8", fontSize: "12px" }}
                  />
                  <Bar dataKey="pages" name="Pages Rendered" fill="#6366f1" radius={[4, 4, 0, 0]} maxBarSize={30} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="w-full h-full bg-zinc-900/40 animate-pulse rounded-xl" />
            )}
          </div>
        </div>

        {/* Security Audits Snapshot (Dynamic) */}
        <div className="glass-panel p-6 rounded-2xl border border-white/5 space-y-4 flex flex-col justify-between">
          <div>
            <h3 className="font-semibold text-zinc-200 text-base mb-1">Recent Security Audits</h3>
            <p className="text-xs text-zinc-500 mb-4">Live security log actions</p>
            <div className="space-y-4">
              {data.recent_audits.length > 0 ? (
                data.recent_audits.map((audit, i) => (
                  <div key={i} className="flex items-start justify-between border-b border-white/5 pb-3 last:border-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-zinc-300 truncate">{audit.action}</p>
                      <p className="text-[10px] text-zinc-500 truncate">{audit.user}</p>
                    </div>
                    <span className="text-[10px] text-zinc-500 shrink-0 ml-2">{formatTime(audit.time, mounted)}</span>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-zinc-500 text-xs">No audit logs recorded yet</div>
              )}
            </div>
          </div>
          <Link href="/dashboard/admin" className="text-xs text-[#82C8E5] hover:underline flex items-center justify-center gap-1 pt-4 border-t border-white/5">
            <span>View Security Matrix</span>
            <ArrowUpRight size={14} />
          </Link>
        </div>
      </div>

      {/* Sub sections: Folders */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-zinc-200">Featured Folders</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {folders.map((folder) => (
            <div 
              key={folder.id}
              className={`glass-card p-5 rounded-2xl cursor-pointer bg-gradient-to-br ${folder.color} border-white/5 relative overflow-hidden group`}
            >
              <Folder size={32} className="text-zinc-100/90 mb-3 group-hover:scale-110 transition-transform" />
              <h3 className="font-semibold text-zinc-200 text-sm truncate">{folder.name}</h3>
              <p className="text-xs text-zinc-400 mt-1">{folder.items}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
