"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, Loader2, FileText, ZoomIn, MessageSquare, X, Filter, Clock, ChevronDown, Folder } from "lucide-react";
import Link from "next/link";

import { SearchModeToggle, SearchMode } from "@/components/SearchModeToggle";

interface SearchResult {
  page_id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  score: number;
  text_snippet: string;
  s3_signed_url: string;
}

interface FolderType {
  id: string;
  name: string;
  parent_id: string | null;
}

// Shimmer skeleton card
function SkeletonCard() {
  return (
    <div className="glass-card rounded-2xl overflow-hidden animate-pulse">
      <div className="aspect-[3/4] bg-zinc-800" />
      <div className="p-4 space-y-2">
        <div className="h-3 bg-zinc-700 rounded w-3/4" />
        <div className="h-2 bg-zinc-800 rounded w-1/2" />
        <div className="h-2 bg-zinc-800 rounded w-full" />
        <div className="h-2 bg-zinc-800 rounded w-2/3" />
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.min(100, Math.round(score * 100));
  const color = pct > 70 ? "text-emerald-400 bg-emerald-500/10" :
                pct > 40 ? "text-amber-400 bg-amber-500/10" :
                           "text-zinc-400 bg-zinc-800";
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${color}`}>
      {pct}% match
    </span>
  );
}

// Zoom overlay for page preview
function ZoomOverlay({ result, onClose }: { result: SearchResult; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="relative max-w-2xl w-full glass-panel rounded-3xl overflow-hidden shadow-2xl border border-white/10"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-white/5">
          <div>
            <p className="text-sm font-semibold text-zinc-200">{result.document_name}</p>
            <p className="text-xs text-zinc-500">Page {result.page_number}</p>
          </div>
          <div className="flex items-center gap-2">
            <ScoreBadge score={result.score} />
            <button onClick={onClose} className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors">
              <X size={18} />
            </button>
          </div>
        </div>
        {result.s3_signed_url ? (
          <img
            src={result.s3_signed_url}
            alt={`${result.document_name} page ${result.page_number}`}
            className="w-full object-contain max-h-[70vh]"
          />
        ) : (
          <div className="aspect-[3/4] flex items-center justify-center bg-zinc-900">
            <div className="text-center">
               <FileText size={48} className="text-zinc-600 mx-auto mb-3" />
               <p className="text-zinc-500 text-sm">No preview available</p>
            </div>
          </div>
        )}
        {result.text_snippet && (
          <div className="p-4 border-t border-white/5">
            <p className="text-xs text-zinc-400 italic leading-relaxed">"{result.text_snippet}"</p>
          </div>
        )}
        <div className="p-4 flex gap-2">
          <Link
            href={`/dashboard/documents/${result.document_id}`}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors"
          >
            <MessageSquare size={14} />
            Open in Document Viewer
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("hybrid");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [zoomedResult, setZoomedResult] = useState<SearchResult | null>(null);
  const [queryTimeMs, setQueryTimeMs] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Filters
  const [folders, setFolders] = useState<FolderType[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string>("");
  const [selectedFileType, setSelectedFileType] = useState<string>("");
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    fetchFolders();
  }, []);

  const fetchFolders = async () => {
    const token = localStorage.getItem("docscope_token");
    if (!token) return;
    try {
      const res = await fetch("/api/v1/folders", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setFolders(await res.json());
    } catch (err) {
      console.error("Failed to fetch folders", err);
    }
  };

  const runSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    setQueryTimeMs(null);

    try {
      const token = localStorage.getItem("docscope_token");
      if (!token) {
        setResults([]);
        setLoading(false);
        return;
      }

      const body: Record<string, unknown> = { 
        query: query.trim(), 
        top_k: 20,
        search_mode: searchMode 
      };
      if (selectedFolderId) body.folder_id = selectedFolderId;

      const resp = await fetch("/api/v1/search", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });

      if (resp.ok) {
        const data = await resp.json();
        setResults(data.results ?? []);
        setQueryTimeMs(data.query_time_ms ?? null);
      } else {
        setResults([]);
      }
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  // Client-side file type filter
  const filteredResults = selectedFileType
    ? results.filter((r) => {
        const name = r.document_name.toLowerCase();
        if (selectedFileType === "pdf") return name.endsWith(".pdf");
        if (selectedFileType === "docx") return name.endsWith(".docx") || name.endsWith(".doc");
        if (selectedFileType === "pptx") return name.endsWith(".pptx") || name.endsWith(".ppt");
        if (selectedFileType === "image") return /\.(png|jpg|jpeg|gif|webp)$/i.test(name);
        return true;
      })
    : results;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
            Visual Search
          </h1>
          <p className="text-sm text-zinc-400 mt-1">Semantic + keyword hybrid search across all your documents</p>
        </div>
        <SearchModeToggle mode={searchMode} onChange={setSearchMode} />
      </div>

      {/* Search Bar */}
      <div className="space-y-3">
        <div className="relative">
          <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
            <Search size={20} className="text-zinc-500" />
          </div>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
            placeholder="Search documents… (e.g. quarterly revenue, vendor agreement, architecture)"
            className="w-full pl-12 pr-40 py-4 rounded-2xl bg-zinc-900/80 border border-white/8 text-zinc-200 placeholder-zinc-600 text-sm focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all"
          />
          <div className="absolute inset-y-0 right-3 flex items-center gap-2">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`p-2 rounded-lg transition-colors ${showFilters ? "bg-emerald-500/20 text-emerald-400" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"}`}
            >
              <Filter size={16} />
            </button>
            <button
              onClick={runSearch}
              disabled={loading || !query.trim()}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold transition-all duration-200"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              Search
            </button>
          </div>
        </div>

        {/* Filter Panel */}
        {showFilters && (
          <div className="flex flex-wrap items-center gap-3 p-4 rounded-xl bg-zinc-900/50 border border-white/5 animate-in fade-in slide-in-from-top-2 duration-200">
            <div className="flex items-center gap-2">
              <Folder size={14} className="text-zinc-500" />
              <select
                value={selectedFolderId}
                onChange={(e) => setSelectedFolderId(e.target.value)}
                className="bg-zinc-800 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-emerald-500/50 appearance-none cursor-pointer"
              >
                <option value="">All Folders</option>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <FileText size={14} className="text-zinc-500" />
              <select
                value={selectedFileType}
                onChange={(e) => setSelectedFileType(e.target.value)}
                className="bg-zinc-800 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-emerald-500/50 appearance-none cursor-pointer"
              >
                <option value="">All File Types</option>
                <option value="pdf">PDF</option>
                <option value="docx">Word (DOCX)</option>
                <option value="pptx">PowerPoint (PPTX)</option>
                <option value="image">Images</option>
              </select>
            </div>
            {(selectedFolderId || selectedFileType) && (
              <button
                onClick={() => { setSelectedFolderId(""); setSelectedFileType(""); }}
                className="text-xs text-zinc-500 hover:text-zinc-300 underline transition-colors"
              >
                Clear filters
              </button>
            )}
          </div>
        )}
      </div>

      {/* Results */}
      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Initial State — before any search */}
      {!loading && !searched && (
        <div className="text-center py-24">
          <div className="w-20 h-20 rounded-3xl bg-emerald-500/10 flex items-center justify-center mx-auto mb-6">
            <Search size={36} className="text-emerald-500" />
          </div>
          <h2 className="text-xl font-semibold text-zinc-200 mb-2">Search your documents</h2>
          <p className="text-sm text-zinc-500 max-w-md mx-auto">
            Type a query above to search across all your uploaded documents using hybrid semantic + keyword search.
          </p>
        </div>
      )}

      {/* No Results State */}
      {!loading && searched && filteredResults.length === 0 && (
        <div className="text-center py-20">
          <Search size={48} className="text-zinc-700 mx-auto mb-4" />
          <p className="text-zinc-400 font-semibold">No results found</p>
          <p className="text-zinc-600 text-sm mt-1">Try different keywords or upload more documents</p>
        </div>
      )}

      {/* Results Grid */}
      {!loading && filteredResults.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm text-zinc-400">
              <span className="text-zinc-200 font-semibold">{filteredResults.length}</span> pages matched for{" "}
              <span className="text-emerald-400 font-semibold">"{query}"</span>
              {selectedFileType && <span className="text-zinc-500"> · filtered by {selectedFileType.toUpperCase()}</span>}
            </p>
            {queryTimeMs !== null && (
              <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                <Clock size={12} />
                <span>{queryTimeMs}ms</span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filteredResults.map((result) => (
              <div
                key={result.page_id}
                className="glass-card rounded-2xl overflow-hidden group cursor-pointer"
                onClick={() => setZoomedResult(result)}
              >
                {/* Page Image or Placeholder */}
                <div className="aspect-[3/4] relative overflow-hidden bg-zinc-900">
                  {result.s3_signed_url ? (
                    <img
                      src={result.s3_signed_url}
                      alt={`${result.document_name} page ${result.page_number}`}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center gap-3 p-4">
                      <FileText size={32} className="text-zinc-600" />
                      <p className="text-zinc-600 text-xs text-center leading-relaxed">{result.text_snippet.slice(0, 80)}…</p>
                    </div>
                  )}

                  {/* Hover zoom hint */}
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors duration-300 flex items-center justify-center">
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-300 p-3 rounded-full bg-white/10 backdrop-blur-sm">
                      <ZoomIn size={20} className="text-white" />
                    </div>
                  </div>

                  {/* Score badge */}
                  <div className="absolute top-2 right-2">
                    <ScoreBadge score={result.score} />
                  </div>
                </div>

                {/* Card Footer */}
                <div className="p-3 space-y-1">
                  <p className="text-xs font-semibold text-zinc-200 truncate">{result.document_name}</p>
                  <p className="text-[10px] text-zinc-500">Page {result.page_number}</p>
                  {result.text_snippet && (
                    <p className="text-[10px] text-zinc-500 line-clamp-2 leading-relaxed">{result.text_snippet}</p>
                  )}
                  <Link
                    href={`/dashboard/documents/${result.document_id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="mt-2 flex items-center gap-1 text-[10px] text-emerald-400 hover:text-emerald-300 font-semibold transition-colors"
                  >
                    <MessageSquare size={10} />
                    Open Document
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Zoom Overlay */}
      {zoomedResult && (
        <ZoomOverlay result={zoomedResult} onClose={() => setZoomedResult(null)} />
      )}
    </div>
  );
}
