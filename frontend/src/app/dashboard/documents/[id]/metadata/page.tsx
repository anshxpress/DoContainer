"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Play } from "lucide-react";
import { MetadataPanel, DocumentMetadata } from "@/components/MetadataPanel";

export default function DocumentMetadataPage() {
  const params = useParams();
  const router = useRouter();
  const docId = params.id as string;

  const [document, setDocument] = useState<any>(null);
  const [metadata, setMetadata] = useState<DocumentMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [reprocessing, setReprocessing] = useState(false);

  useEffect(() => {
    fetchData();
  }, [docId]);

  const fetchData = async () => {
    const token = localStorage.getItem("docscope_token");
    if (!token) return;

    try {
      const [docRes, metaRes] = await Promise.all([
        fetch(`/api/v1/documents/${docId}`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`/api/v1/documents/${docId}/metadata`, { headers: { Authorization: `Bearer ${token}` } })
      ]);

      if (docRes.ok) setDocument(await docRes.json());
      if (metaRes.ok) setMetadata(await metaRes.json());
    } catch (e) {
      console.error("Failed to fetch metadata", e);
    } finally {
      setLoading(false);
    }
  };

  const handleReprocess = async () => {
    if (!confirm("This will re-run the AI extraction pipeline. Continue?")) return;
    
    setReprocessing(true);
    const token = localStorage.getItem("docscope_token");
    if (!token) return;

    try {
      await fetch(`/api/v1/documents/${docId}/reprocess?pipeline=hybrid`, { 
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` } 
      });
      alert("Hybrid processing pipeline started in the background.");
    } catch (e) {
      console.error("Failed to reprocess", e);
    } finally {
      setReprocessing(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-emerald-500" />
      </div>
    );
  }

  if (!document || !metadata) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4">
        <p className="text-zinc-400">Document or metadata not found.</p>
        <button onClick={() => router.back()} className="text-emerald-400 hover:underline">
          Go Back
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-zinc-950 p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push(`/dashboard/documents/${docId}`)}
            className="p-2 bg-zinc-900 border border-white/5 rounded-xl text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">{document.name}</h1>
            <p className="text-sm text-zinc-500">AI Metadata & Extractions</p>
          </div>
        </div>

        <button
          onClick={handleReprocess}
          disabled={reprocessing}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 font-medium text-sm transition-colors border border-amber-500/20 disabled:opacity-50"
        >
          {reprocessing ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          Reprocess AI Metadata
        </button>
      </div>

      {/* Main View */}
      <div className="flex-1 overflow-hidden flex justify-center">
        <div className="w-full max-w-4xl">
          <MetadataPanel metadata={metadata} />
        </div>
      </div>
    </div>
  );
}
