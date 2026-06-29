"use client";

import React, { useState, useEffect } from "react";
import { Loader2, RefreshCw, AlertCircle, CheckCircle2, XCircle, FileText, Clock, Play } from "lucide-react";
import Link from "next/link";

function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

type Document = {
  id: string;
  name: string;
  status: string;
  file_type: string;
  file_size: number;
  error_message: string | null;
  created_at: string;
};

export default function ProcessingDashboard() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [retryIds, setRetryIds] = useState<Set<string>>(new Set());

  const fetchProcessingDocuments = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    const token = localStorage.getItem("docscope_token");
    if (!token) return;

    try {
      const res = await fetch("/api/v1/documents/processing", {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setDocuments(await res.json());
      } else if (res.status === 401) {
        localStorage.removeItem("docscope_token");
        window.location.href = "/login";
      }
    } catch (err) {
      console.error("Failed to fetch processing documents", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchProcessingDocuments();
    // Poll every 10 seconds for real-time updates
    const interval = setInterval(() => fetchProcessingDocuments(true), 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRetry = async (docId: string) => {
    const token = localStorage.getItem("docscope_token");
    if (!token) return;

    setRetryIds(prev => new Set(prev).add(docId));
    try {
      const res = await fetch(`/api/v1/documents/${docId}/reprocess?pipeline=hybrid`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        await fetchProcessingDocuments();
      }
    } catch (err) {
      console.error("Failed to retry document", err);
    } finally {
      setRetryIds(prev => {
        const next = new Set(prev);
        next.delete(docId);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin text-emerald-500" size={32} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full max-w-6xl mx-auto w-full">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Processing Dashboard</h1>
          <p className="text-sm text-zinc-400">Monitor background ingestion tasks and handle errors.</p>
        </div>
        <button 
          onClick={() => fetchProcessingDocuments(true)}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-900/50 hover:bg-zinc-800 border border-white/10 rounded-xl text-sm font-medium text-zinc-300 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
          Refresh Status
        </button>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden glass-panel rounded-2xl border border-white/5 flex flex-col">
        {documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-8">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center mb-4">
              <CheckCircle2 size={32} className="text-emerald-500" />
            </div>
            <h3 className="text-lg font-semibold text-zinc-200 mb-1">All clear!</h3>
            <p className="text-sm text-zinc-500 max-w-sm">There are no documents currently queuing, processing, or failing.</p>
            <Link href="/dashboard/documents" className="mt-6 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-sm font-medium text-white transition-colors">
              Go to Documents
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-white/5 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  <th className="py-4 px-6">Document</th>
                  <th className="py-4 px-6">Status</th>
                  <th className="py-4 px-6">Uploaded</th>
                  <th className="py-4 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {documents.map(doc => (
                  <tr key={doc.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-4 px-6">
                      <div className="flex items-start gap-3">
                        <div className="mt-1 p-2 bg-zinc-800 rounded-lg">
                          <FileText size={16} className="text-zinc-400" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-zinc-200">{doc.name}</p>
                          <p className="text-xs text-zinc-500 mt-0.5">{doc.file_type.toUpperCase()} • {formatBytes(doc.file_size)}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-2">
                        {doc.status === "processing" ? (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 text-xs font-medium border border-blue-500/20">
                            <RefreshCw size={12} className="animate-spin" /> Processing
                          </div>
                        ) : doc.status === "queued" ? (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 text-xs font-medium border border-amber-500/20">
                            <Clock size={12} /> Queued
                          </div>
                        ) : doc.status === "failed" ? (
                          <div className="flex flex-col gap-1.5">
                            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-500/10 text-red-400 text-xs font-medium border border-red-500/20 w-max">
                              <XCircle size={12} /> Failed
                            </div>
                            {doc.error_message && (
                              <p className="text-xs text-red-400/80 max-w-xs line-clamp-2" title={doc.error_message}>
                                {doc.error_message}
                              </p>
                            )}
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-500/10 text-zinc-400 text-xs font-medium border border-zinc-500/20">
                            Unknown
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-6 text-sm text-zinc-400">
                      {new Date(doc.created_at).toLocaleString()}
                    </td>
                    <td className="py-4 px-6 text-right">
                      {doc.status === "failed" && (
                        <button 
                          onClick={() => handleRetry(doc.id)}
                          disabled={retryIds.has(doc.id)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                        >
                          {retryIds.has(doc.id) ? (
                            <RefreshCw size={14} className="animate-spin" />
                          ) : (
                            <Play size={14} />
                          )}
                          Retry
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
