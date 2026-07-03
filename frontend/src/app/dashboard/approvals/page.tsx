"use client";

import React, { useState, useEffect } from "react";
import { apiClient } from "../../../lib/apiClient";
import { CheckCircle, Clock, XCircle, Search, FileText, Check, X, Loader2 } from "lucide-react";
import Link from "next/link";

type ApprovalRequest = {
  id: string;
  document_id: string;
  submitted_by: string;
  status: string;
  submission_note: string | null;
  review_note: string | null;
  submitted_at: string;
};

type Tab = "pending" | "my-requests";

export default function ApprovalsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("pending");
  const [loading, setLoading] = useState(true);
  const [requests, setRequests] = useState<ApprovalRequest[]>([]);
  const [search, setSearch] = useState("");

  const fetchApprovals = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get("/api/v1/approval/requests");
      setRequests(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const filtered = requests.filter(r => {
    if (activeTab === "pending") return r.status === "pending";
    // For my-requests we ideally filter by submitted_by, but backend just returns what we can see based on role for now
    return true;
  }).filter(r => (r.submission_note || "").toLowerCase().includes(search.toLowerCase()) || r.document_id.includes(search));

  const handleDecide = async (id: string, action: "approve" | "reject", note: string) => {
    try {
      await apiClient.post(`/api/v1/approval/${id}/decide`, { action, review_note: note });
      fetchApprovals();
    } catch (e) {}
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
          Approvals Hub
        </h1>
        <p className="text-sm text-zinc-400 mt-1">Review and manage document approval workflows.</p>
      </div>

      {/* Tabs & Actions */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-white/5 pb-4">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab("pending")}
            className={`pb-4 -mb-4 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "pending" ? "border-emerald-500 text-emerald-400" : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Pending Review
          </button>
          <button
            onClick={() => setActiveTab("my-requests")}
            className={`pb-4 -mb-4 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === "my-requests" ? "border-emerald-500 text-emerald-400" : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            All Requests
          </button>
        </div>
        
        <div className="relative w-full sm:w-64">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search requests..."
            className="w-full pl-9 pr-4 py-2 bg-zinc-900/50 border border-white/5 rounded-xl text-sm text-zinc-200 focus:outline-none focus:border-emerald-500/50"
          />
        </div>
      </div>

      {/* Content List */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-emerald-500" /></div>
      ) : (
        <div className="space-y-4">
          {filtered.length === 0 && (
            <div className="p-12 text-center text-zinc-500 glass-panel rounded-2xl border border-white/5">
              No approval requests found.
            </div>
          )}
          {filtered.map(req => (
            <div key={req.id} className="p-5 glass-panel rounded-2xl border border-white/5 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div className="flex items-start gap-4">
                <div className={`p-3 rounded-xl flex items-center justify-center ${
                  req.status === 'pending' ? 'bg-yellow-500/10 text-yellow-500' :
                  req.status === 'approved' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'
                }`}>
                  {req.status === 'pending' ? <Clock size={20} /> : req.status === 'approved' ? <CheckCircle size={20} /> : <XCircle size={20} />}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                    Request for Document
                    <Link href={`/dashboard/documents/${req.document_id}`} className="text-emerald-400 hover:underline">
                      {req.document_id.slice(0, 8)}...
                    </Link>
                  </h3>
                  <p className="text-xs text-zinc-400 mt-1">Submitted {new Date(req.submitted_at).toLocaleString()}</p>
                  {req.submission_note && (
                    <p className="text-sm text-zinc-300 mt-2 p-3 bg-white/5 rounded-xl">"{req.submission_note}"</p>
                  )}
                  {req.review_note && (
                    <p className="text-xs text-zinc-500 mt-2 flex items-center gap-2">
                      <span className="font-semibold text-zinc-400">Review Note:</span> {req.review_note}
                    </p>
                  )}
                </div>
              </div>
              
              {activeTab === "pending" && req.status === "pending" && (
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleDecide(req.id, "reject", "Rejected via Hub")}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500/20 font-semibold text-sm transition-colors"
                  >
                    <X size={16} /> Reject
                  </button>
                  <button
                    onClick={() => handleDecide(req.id, "approve", "Approved via Hub")}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 text-white hover:bg-emerald-400 font-semibold text-sm transition-colors"
                  >
                    <Check size={16} /> Approve
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
