"use client";

import React, { useState, useEffect } from "react";
import { apiClient } from "../../../lib/apiClient";
import { 
  FileText, 
  Search, 
  MessageSquare,
  Clock, 
  Plus, 
  Folder,
  HardDrive,
  Star,
  Bookmark
} from "lucide-react";
import Link from "next/link";
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip
} from "recharts";

const COLORS = ["#10b981", "#06b6d4", "#6366f1", "#f59e0b"];

function formatBytes(bytes: number) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

const MOCK_DATA = {
  totals: {
    documents: 125,
    storage_bytes: 450000000, // ~450 MB
  },
  recent_documents: [
    { name: "Q3 Tax Return.pdf", date: "2 hours ago" },
    { name: "Receipts-June.zip", date: "5 hours ago" },
    { name: "Passport Scan.png", date: "1 day ago" }
  ],
  file_type_breakdown: [
    { name: "PDF", value: 85, size_mb: 250 },
    { name: "Images", value: 30, size_mb: 150 },
    { name: "Other", value: 10, size_mb: 50 }
  ]
};

export default function PersonalDashboard() {
  const [mounted, setMounted] = useState(false);
  const [data, setData] = useState(MOCK_DATA);

  useEffect(() => {
    setMounted(true);
    // In a real implementation, we would fetch personal dashboard data here
    // apiClient.get("/api/v1/analytics/personal")
  }, []);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
            My Workspace
          </h1>
          <p className="text-sm text-zinc-400">
            Welcome to your personal document intelligence hub.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link 
            href="/dashboard/search" 
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-white/5 bg-zinc-900/60 hover:bg-zinc-800 text-zinc-300 text-xs font-semibold transition-colors"
          >
            <Search size={16} />
            <span>AI Search</span>
          </Link>
          <Link 
            href="/dashboard/upload" 
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#0047AB] hover:bg-[#1a5fc4] text-white text-xs font-semibold shadow-lg shadow-[#0047AB]/25 transition-all duration-200"
          >
            <Plus size={16} />
            <span>Quick Upload</span>
          </Link>
        </div>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="glass-card p-6 rounded-2xl relative overflow-hidden group">
          <div className="flex justify-between mb-4">
            <span className="text-sm text-zinc-400 font-medium">My Documents</span>
            <FileText size={20} className="text-[#82C8E5]" />
          </div>
          <h3 className="text-3xl font-bold text-zinc-100">{data.totals.documents}</h3>
        </div>
        <div className="glass-card p-6 rounded-2xl relative overflow-hidden group">
          <div className="flex justify-between mb-4">
            <span className="text-sm text-zinc-400 font-medium">Storage Used</span>
            <HardDrive size={20} className="text-[#82C8E5]" />
          </div>
          <h3 className="text-3xl font-bold text-zinc-100">{formatBytes(data.totals.storage_bytes)}</h3>
        </div>
        <div className="glass-card p-6 rounded-2xl relative overflow-hidden group">
          <div className="flex justify-between mb-4">
            <span className="text-sm text-zinc-400 font-medium">Favorites</span>
            <Star size={20} className="text-yellow-400" />
          </div>
          <h3 className="text-3xl font-bold text-zinc-100">12</h3>
        </div>
        <div className="glass-card p-6 rounded-2xl relative overflow-hidden group">
          <div className="flex justify-between mb-4">
            <span className="text-sm text-zinc-400 font-medium">Recent AI Chats</span>
            <MessageSquare size={20} className="text-[#6D8196]" />
          </div>
          <h3 className="text-3xl font-bold text-zinc-100">5</h3>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-white/5 space-y-4">
          <h3 className="font-semibold text-zinc-200 text-base">Recent Activity</h3>
          <div className="space-y-4">
            {data.recent_documents.map((doc, i) => (
              <div key={i} className="flex items-start justify-between border-b border-white/5 pb-3 last:border-0 last:pb-0">
                <div className="flex items-center gap-3">
                  <FileText size={16} className="text-zinc-500" />
                  <p className="text-sm text-zinc-300">{doc.name}</p>
                </div>
                <span className="text-xs text-zinc-500">{doc.date}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Storage Breakdown */}
        <div className="glass-panel p-6 rounded-2xl border border-white/5 space-y-4">
          <h3 className="font-semibold text-zinc-200 text-base">Storage Usage</h3>
          <div className="h-[200px] w-full">
            {mounted && (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.file_type_breakdown}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={70}
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
            )}
          </div>
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 pb-2">
            {data.file_type_breakdown.map((entry, index) => (
              <div key={entry.name} className="flex items-center gap-1.5 text-xs text-zinc-300">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                <span>{entry.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
