"use client";

import React, { useState, useEffect } from "react";
import { apiClient } from "../../../../../lib/apiClient";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { OCROverlay, OcrChunk } from "@/components/OCROverlay";

export default function DocumentOCRPage() {
  const params = useParams();
  const router = useRouter();
  const docId = params.id as string;

  const [document, setDocument] = useState<any>(null);
  const [pages, setPages] = useState<any[]>([]);
  const [chunks, setChunks] = useState<OcrChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentPageIndex, setCurrentPageIndex] = useState(0);

  useEffect(() => {
    fetchData();
  }, [docId]);

  const fetchData = async () => {
    const token = localStorage.getItem("docscope_token");
    if (!token) return;

    try {
      const [docRes, pagesRes, chunksRes] = await Promise.all([
        fetch(`/api/v1/documents/${docId}`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`/api/v1/documents/${docId}/pages`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`/api/v1/documents/${docId}/ocr`, { headers: { Authorization: `Bearer ${token}` } })
      ]);

      if (docRes.ok) setDocument(await docRes.json());
      if (pagesRes.ok) setPages(await pagesRes.json());
      if (chunksRes.ok) setChunks(await chunksRes.json());
    } catch (e) {
      console.error("Failed to fetch OCR data", e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-emerald-500" />
      </div>
    );
  }

  if (!document || pages.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4">
        <p className="text-zinc-400">Document or OCR data not found.</p>
        <button onClick={() => router.back()} className="text-emerald-400 hover:underline">
          Go Back
        </button>
      </div>
    );
  }

  const currentPage = pages[currentPageIndex];

  return (
    <div className="flex flex-col h-full bg-zinc-950 p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push(`/dashboard/documents/${docId}`)}
            className="p-2 bg-zinc-900 border border-white/5 rounded-xl text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">{document.name}</h1>
            <p className="text-sm text-zinc-500">OCR Region Inspection</p>
          </div>
        </div>

        {/* Pagination Controls */}
        <div className="flex items-center gap-4 bg-zinc-900 border border-white/5 p-1 rounded-xl">
          <button 
            onClick={() => setCurrentPageIndex(p => Math.max(0, p - 1))}
            disabled={currentPageIndex === 0}
            className="p-2 text-zinc-400 hover:text-white hover:bg-white/10 rounded-lg disabled:opacity-50 transition-colors"
          >
            <ChevronLeft size={20} />
          </button>
          <span className="text-sm font-medium text-zinc-300 min-w-[80px] text-center">
            Page {currentPage.page_number} / {pages.length}
          </span>
          <button 
            onClick={() => setCurrentPageIndex(p => Math.min(pages.length - 1, p + 1))}
            disabled={currentPageIndex === pages.length - 1}
            className="p-2 text-zinc-400 hover:text-white hover:bg-white/10 rounded-lg disabled:opacity-50 transition-colors"
          >
            <ChevronRight size={20} />
          </button>
        </div>
      </div>

      {/* Main View */}
      <div className="flex-1 overflow-hidden">
        <OCROverlay 
          imageUrl={currentPage.image_url} 
          chunks={chunks} 
          pageNumber={currentPage.page_number} 
        />
      </div>
    </div>
  );
}
