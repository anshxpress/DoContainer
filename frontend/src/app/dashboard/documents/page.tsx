"use client";

import React, { useState, useEffect, useCallback } from "react";
import { apiClient } from "../../../lib/apiClient";
import {
  Folder, FileText, MoreVertical, LayoutGrid, List as ListIcon, 
  FolderPlus, UploadCloud, Search, ChevronRight, Check, X,
  File, Image as ImageIcon, FileSpreadsheet, Presentation, Loader2,
  Trash2, Edit2, CornerUpLeft, Clock, HardDrive, Download
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

// --- Types ---
type FolderType = { id: string; name: string; parent_id: string | null; created_at: string; updated_at: string };
type DocumentType = { id: string; name: string; folder_id: string | null; status: string; file_type: string; file_size: number; created_at: string; storage_path: string };

function getFileIcon(type: string) {
  const ext = type.toLowerCase();
  if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext)) return ImageIcon;
  if (["xls", "xlsx", "csv"].includes(ext)) return FileSpreadsheet;
  if (["ppt", "pptx"].includes(ext)) return Presentation;
  return FileText;
}

function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export default function DocumentsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  
  // Data
  const [allFolders, setAllFolders] = useState<FolderType[]>([]);
  const [currentDocs, setCurrentDocs] = useState<DocumentType[]>([]);
  
  // UI State
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [searchQuery, setSearchQuery] = useState("");
  
  // Modals
  const [isNewFolderModalOpen, setIsNewFolderModalOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  
  // Context Menu
  const [activeMenu, setActiveMenu] = useState<{ type: "folder" | "doc", id: string } | null>(null);

  const fetchAllFolders = async () => {
    try {
      const folders = await apiClient.get("/api/v1/folders");
      setAllFolders(folders);
    } catch {}
  };

  const fetchDocuments = useCallback(async (folderId: string | null) => {
    try {
      const docs = await apiClient.get(`/api/v1/documents?folder_id=${folderId || "root"}`);
      setCurrentDocs(docs);
    } catch {}
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    await fetchAllFolders();
    await fetchDocuments(currentFolderId);
    setLoading(false);
  }, [currentFolderId, fetchDocuments]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Derived state
  const currentFolders = allFolders.filter(f => f.parent_id === currentFolderId);
  const filteredFolders = currentFolders.filter(f => f.name.toLowerCase().includes(searchQuery.toLowerCase()));
  const filteredDocs = currentDocs.filter(d => d.name.toLowerCase().includes(searchQuery.toLowerCase()));

  // Breadcrumbs builder
  const getBreadcrumbs = () => {
    const crumbs: { id: string | null; name: string }[] = [{ id: null, name: "My Documents" }];
    if (!currentFolderId) return crumbs;
    
    const trace = [];
    let curr = allFolders.find(f => f.id === currentFolderId);
    while (curr) {
      trace.unshift({ id: curr.id, name: curr.name });
      curr = allFolders.find(f => f.id === curr!.parent_id);
    }
    return [...crumbs, ...trace];
  };

  const breadcrumbs = getBreadcrumbs();

  // Handlers
  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;
    
    try {
      await apiClient.post("/api/v1/folders", { name: newFolderName, parent_id: currentFolderId });
      setNewFolderName("");
      setIsNewFolderModalOpen(false);
      loadData();
    } catch (err) {}
  };

  const handleDelete = async (type: "folder" | "doc", id: string) => {
    if (!confirm(`Are you sure you want to delete this ${type}?`)) return;
    
    const endpoint = type === "folder" ? `/api/v1/folders/${id}` : `/api/v1/documents/${id}`;
    
    try {
      await apiClient.delete(endpoint);
      loadData();
    } catch (err: any) {
      alert(`Failed to delete: ${err.message}`);
    }
    setActiveMenu(null);
  };

  if (loading && allFolders.length === 0) {
    return (
      <div className="flex flex-col h-[calc(100vh-4rem)] space-y-6 animate-pulse">
        {/* Toolbar Skeleton */}
        <div className="flex justify-between items-center">
          <div className="flex gap-2">
            <div className="w-32 h-6 bg-zinc-800/50 rounded-lg"></div>
            <div className="w-4 h-6 bg-zinc-800/20 rounded-lg"></div>
            <div className="w-24 h-6 bg-zinc-800/50 rounded-lg"></div>
          </div>
          <div className="flex gap-3">
            <div className="w-64 h-10 bg-zinc-800/50 rounded-xl"></div>
            <div className="w-24 h-10 bg-zinc-800/50 rounded-xl"></div>
            <div className="w-32 h-10 bg-emerald-900/20 rounded-xl"></div>
          </div>
        </div>

        {/* Content Skeleton */}
        <div className="flex-1 glass-panel rounded-2xl border border-white/5 p-6 space-y-8">
          <div>
            <div className="w-20 h-4 bg-zinc-800/50 rounded mb-4"></div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="flex items-center gap-3 p-4 rounded-xl bg-zinc-900/50 border border-white/5 h-16">
                  <div className="w-6 h-6 bg-zinc-800/50 rounded-md"></div>
                  <div className="flex-1 h-4 bg-zinc-800/50 rounded-md"></div>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="w-20 h-4 bg-zinc-800/50 rounded mb-4"></div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="flex flex-col p-4 rounded-xl bg-zinc-900/50 border border-white/5 h-32">
                  <div className="w-10 h-10 bg-zinc-800/50 rounded-lg mb-4"></div>
                  <div className="w-3/4 h-4 bg-zinc-800/50 rounded-md mb-2"></div>
                  <div className="flex justify-between mt-auto">
                    <div className="w-12 h-3 bg-zinc-800/50 rounded-md"></div>
                    <div className="w-16 h-3 bg-zinc-800/50 rounded-full"></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] space-y-6">
      
      {/* Top Toolbar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        {/* Breadcrumbs */}
        <div className="flex items-center flex-wrap gap-2 text-lg font-semibold">
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={crumb.id || "root"}>
              <button 
                onClick={() => setCurrentFolderId(crumb.id)}
                className={`hover:text-emerald-400 transition-colors ${idx === breadcrumbs.length - 1 ? "text-zinc-200" : "text-zinc-500"}`}
              >
                {crumb.name}
              </button>
              {idx < breadcrumbs.length - 1 && <ChevronRight size={18} className="text-zinc-600" />}
            </React.Fragment>
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Search in folder..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 sm:w-64 pl-9 pr-4 py-2 rounded-xl bg-zinc-900/80 border border-white/8 text-zinc-300 placeholder-zinc-600 text-sm focus:outline-none focus:border-emerald-500/40 transition-all"
            />
          </div>
          <div className="flex items-center p-1 rounded-xl glass-panel border border-white/5">
            <button 
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded-lg transition-colors ${viewMode === "grid" ? "bg-white/10 text-emerald-400" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              <LayoutGrid size={16} />
            </button>
            <button 
              onClick={() => setViewMode("list")}
              className={`p-1.5 rounded-lg transition-colors ${viewMode === "list" ? "bg-white/10 text-emerald-400" : "text-zinc-500 hover:text-zinc-300"}`}
            >
              <ListIcon size={16} />
            </button>
          </div>
          <button 
            onClick={() => setIsNewFolderModalOpen(true)}
            className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white text-sm font-semibold transition-all"
          >
            <FolderPlus size={16} />
            <span className="hidden sm:inline">New Folder</span>
          </button>
          <Link href="/dashboard/upload" className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition-all">
            <UploadCloud size={16} />
            <span className="hidden sm:inline">Upload</span>
          </Link>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto glass-panel rounded-2xl border border-white/5 p-6">
        
        {/* Empty State */}
        {filteredFolders.length === 0 && filteredDocs.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 rounded-2xl bg-zinc-800/50 flex items-center justify-center mb-4">
              <Folder size={28} className="text-zinc-600" />
            </div>
            <h3 className="text-lg font-semibold text-zinc-300 mb-1">This folder is empty</h3>
            <p className="text-sm text-zinc-500 max-w-sm mb-6">Create a new folder or upload documents to get started.</p>
            <div className="flex gap-3">
              <button onClick={() => setIsNewFolderModalOpen(true)} className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-sm font-semibold text-white transition-colors">
                New Folder
              </button>
              <Link href="/dashboard/upload" className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-sm font-semibold text-white transition-colors">
                Upload File
              </Link>
            </div>
          </div>
        )}

        {/* Grid View */}
        {viewMode === "grid" && (filteredFolders.length > 0 || filteredDocs.length > 0) && (
          <div className="space-y-8">
            {/* Folders */}
            {filteredFolders.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Folders</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
                  {filteredFolders.map(folder => (
                    <div 
                      key={folder.id}
                      onDoubleClick={() => setCurrentFolderId(folder.id)}
                      className="group relative flex items-center gap-3 p-4 rounded-xl bg-zinc-900/50 border border-white/5 hover:border-emerald-500/30 hover:bg-emerald-500/5 transition-all cursor-pointer select-none"
                    >
                      <Folder size={24} className="text-zinc-400 group-hover:text-emerald-400 transition-colors" />
                      <span className="text-sm font-medium text-zinc-200 truncate">{folder.name}</span>
                      
                      {/* Context Menu Button */}
                      <button 
                        onClick={(e) => { e.stopPropagation(); setActiveMenu(activeMenu?.id === folder.id ? null : { type: "folder", id: folder.id }); }}
                        className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-zinc-500 hover:text-white hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <MoreVertical size={16} />
                      </button>

                      {/* Dropdown */}
                      {activeMenu?.id === folder.id && (
                        <div className="absolute right-4 top-10 w-48 bg-zinc-900 border border-white/10 rounded-xl shadow-xl py-1 z-50">
                          <button onClick={(e) => { e.stopPropagation(); handleDelete("folder", folder.id); }} className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-white/5 flex items-center gap-2">
                            <Trash2 size={14} /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Documents */}
            {filteredDocs.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-4">Files</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
                  {filteredDocs.map(doc => {
                    const Icon = getFileIcon(doc.file_type);
                    return (
                      <div 
                        key={doc.id}
                        onClick={() => router.push(`/dashboard/documents/${doc.id}`)}
                        className="group relative flex flex-col p-4 rounded-xl bg-zinc-900/50 border border-white/5 hover:border-emerald-500/30 hover:bg-emerald-500/5 transition-all cursor-pointer select-none"
                      >
                        <div className="flex items-start justify-between mb-4">
                          <div className={`p-2.5 rounded-lg bg-zinc-800 ${doc.status === 'completed' ? 'text-emerald-400' : 'text-amber-400'}`}>
                            <Icon size={24} />
                          </div>
                          <button 
                            onClick={(e) => { e.stopPropagation(); setActiveMenu(activeMenu?.id === doc.id ? null : { type: "doc", id: doc.id }); }}
                            className="p-1 rounded-lg text-zinc-500 hover:text-white hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-all"
                          >
                            <MoreVertical size={16} />
                          </button>
                        </div>
                        <span className="text-sm font-medium text-zinc-200 truncate mb-1">{doc.name}</span>
                        <div className="flex items-center justify-between text-xs text-zinc-500">
                          <span>{formatBytes(doc.file_size)}</span>
                          <span className={`capitalize ${doc.status === 'completed' ? 'text-emerald-500/80' : 'text-amber-500/80'}`}>{doc.status}</span>
                        </div>

                        {/* Dropdown */}
                        {activeMenu?.id === doc.id && (
                          <div className="absolute right-4 top-10 w-48 bg-zinc-900 border border-white/10 rounded-xl shadow-xl py-1 z-50">
                            <button onClick={(e) => { e.stopPropagation(); handleDelete("doc", doc.id); }} className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-white/5 flex items-center gap-2">
                              <Trash2 size={14} /> Delete
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* List View */}
        {viewMode === "list" && (filteredFolders.length > 0 || filteredDocs.length > 0) && (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-white/5 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                  <th className="py-3 px-4 w-1/2">Name</th>
                  <th className="py-3 px-4">Size</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4 text-right"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {/* List Folders */}
                {filteredFolders.map(folder => (
                  <tr key={folder.id} onDoubleClick={() => setCurrentFolderId(folder.id)} className="hover:bg-white/[0.02] transition-colors cursor-pointer group">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <Folder size={18} className="text-zinc-400 group-hover:text-emerald-400" />
                        <span className="text-sm font-medium text-zinc-200">{folder.name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-sm text-zinc-500">—</td>
                    <td className="py-3 px-4 text-sm text-zinc-500">—</td>
                    <td className="py-3 px-4 text-sm text-zinc-500">{new Date(folder.created_at).toLocaleDateString()}</td>
                    <td className="py-3 px-4 text-right">
                      <button onClick={(e) => { e.stopPropagation(); handleDelete("folder", folder.id); }} className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all">
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
                
                {/* List Documents */}
                {filteredDocs.map(doc => {
                  const Icon = getFileIcon(doc.file_type);
                  return (
                    <tr key={doc.id} onClick={() => router.push(`/dashboard/documents/${doc.id}`)} className="hover:bg-white/[0.02] transition-colors group cursor-pointer">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <Icon size={18} className={doc.status === 'completed' ? 'text-emerald-400' : 'text-amber-400'} />
                          <span className="text-sm font-medium text-zinc-200">{doc.name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm text-zinc-500">{formatBytes(doc.file_size)}</td>
                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${doc.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20'}`}>
                          {doc.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm text-zinc-500">{new Date(doc.created_at).toLocaleDateString()}</td>
                      <td className="py-3 px-4 text-right relative">
                        <button onClick={(e) => { e.stopPropagation(); setActiveMenu(activeMenu?.id === doc.id ? null : { type: "doc", id: doc.id }); }} className="p-1.5 rounded-lg text-zinc-500 hover:text-white hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-all">
                          <MoreVertical size={16} />
                        </button>
                        {/* Dropdown */}
                        {activeMenu?.id === doc.id && (
                          <div className="absolute right-10 top-5 w-48 bg-zinc-900 border border-white/10 rounded-xl shadow-xl py-1 z-50">
                            <button onClick={(e) => { e.stopPropagation(); handleDelete("doc", doc.id); }} className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-white/5 flex items-center gap-2">
                              <Trash2 size={14} /> Delete
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* New Folder Modal */}
      {isNewFolderModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={() => setIsNewFolderModalOpen(false)}>
          <div className="max-w-md w-full glass-panel rounded-3xl p-6 shadow-2xl border border-white/10" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-white">New Folder</h3>
              <button onClick={() => setIsNewFolderModalOpen(false)} className="text-zinc-500 hover:text-white transition-colors">
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateFolder}>
              <input
                type="text"
                autoFocus
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="Folder name"
                className="w-full px-4 py-3 rounded-xl bg-zinc-900 border border-white/10 text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors mb-6"
              />
              <div className="flex justify-end gap-3">
                <button type="button" onClick={() => setIsNewFolderModalOpen(false)} className="px-5 py-2.5 rounded-xl font-semibold text-zinc-400 hover:text-white transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={!newFolderName.trim()} className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold transition-all">
                  Create Folder
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
