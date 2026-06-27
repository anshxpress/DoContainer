"use client";

import React, { useState, useRef, useCallback } from "react";
import {
  UploadCloud, FileText, X, CheckCircle2, AlertCircle,
  Loader2, File, Image, FileSpreadsheet, Presentation,
} from "lucide-react";

const STEPS = [
  { id: "upload",    label: "Uploading",        desc: "Transferring file to server" },
  { id: "scan",      label: "Malware Scan",      desc: "ClamAV security scan" },
  { id: "convert",   label: "Converting",        desc: "PDF conversion via LibreOffice" },
  { id: "render",    label: "Rendering Pages",   desc: "PNG export at 200 DPI" },
  { id: "index",     label: "AI Indexing",       desc: "Multi-vector embedding + Qdrant" },
  { id: "done",      label: "Complete",          desc: "Document ready for search & chat" },
];

type StepStatus = "pending" | "active" | "done" | "error";

interface FileEntry {
  id: string;
  file: File;
  progress: StepStatus[];
  currentStep: number;
  error?: string;
}

function getFileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase();
  if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext ?? "")) return Image;
  if (["xls", "xlsx", "csv"].includes(ext ?? "")) return FileSpreadsheet;
  if (["ppt", "pptx"].includes(ext ?? "")) return Presentation;
  return FileText;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const [dragging, setDragging] = useState(false);
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [demoMode, setDemoMode] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((raw: File[]) => {
    const allowed = raw.filter((f) => {
      const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
      return ["pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "png", "jpg", "jpeg"].includes(ext);
    });
    const entries: FileEntry[] = allowed.map((f) => ({
      id: crypto.randomUUID(),
      file: f,
      progress: STEPS.map(() => "pending" as StepStatus),
      currentStep: -1,
    }));
    setFiles((prev) => [...prev, ...entries]);
  }, []);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  };

  const removeFile = (id: string) =>
    setFiles((prev) => prev.filter((f) => f.id !== id));

  /** Simulate the 5-step ingestion pipeline with realistic delays */
  const simulateIngestion = async (id: string) => {
    for (let step = 0; step < STEPS.length; step++) {
      setFiles((prev) =>
        prev.map((f) =>
          f.id === id
            ? {
                ...f,
                currentStep: step,
                progress: f.progress.map((s, i) =>
                  i < step ? "done" : i === step ? "active" : "pending"
                ) as StepStatus[],
              }
            : f
        )
      );
      // Simulate variable delay per step
      const delays = [800, 1200, 2000, 3000, 2500, 400];
      await new Promise((r) => setTimeout(r, delays[step]));
    }
    // Mark all done
    setFiles((prev) =>
      prev.map((f) =>
        f.id === id
          ? {
              ...f,
              currentStep: STEPS.length,
              progress: STEPS.map(() => "done" as StepStatus),
            }
          : f
      )
    );
  };

  const uploadAndPoll = async (entry: FileEntry) => {
    // 1. Mark upload step as active
    setFiles((prev) =>
      prev.map((f) =>
        f.id === entry.id
          ? {
              ...f,
              currentStep: 0,
              progress: f.progress.map((s, i) =>
                i === 0 ? "active" : "pending"
              ) as StepStatus[],
            }
          : f
      )
    );

    const token = typeof window !== "undefined" ? localStorage.getItem("docscope_token") : null;
    const formData = new FormData();
    formData.append("file", entry.file);

    try {
      const response = await fetch("/api/v1/documents/upload", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed with status ${response.status}`);
      }

      const docData = await response.json();
      const docId = docData.id;

      // 2. Mark upload step as done and transition to scan
      setFiles((prev) =>
        prev.map((f) =>
          f.id === entry.id
            ? {
                ...f,
                currentStep: 1,
                progress: f.progress.map((s, i) =>
                  i === 0 ? "done" : i === 1 ? "active" : "pending"
                ) as StepStatus[],
              }
            : f
        )
      );

      // Start polling backend status
      const pollInterval = 1500;
      let virtualStep = 1; // 1=scan, 2=convert, 3=render, 4=index
      
      const pollTimer = setInterval(async () => {
        try {
          const pollResponse = await fetch(`/api/v1/documents/${docId}`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          
          if (!pollResponse.ok) {
            return; // ignore temporary network hiccups during polling
          }
          
          const pollData = await pollResponse.json();
          const backendStatus = pollData.status; // queued, processing, completed, failed
          const errorMessage = pollData.error_message;

          if (backendStatus === "failed") {
            clearInterval(pollTimer);
            setFiles((prev) =>
              prev.map((f) =>
                f.id === entry.id
                  ? {
                      ...f,
                      error: errorMessage || "Ingestion processing failed.",
                      progress: f.progress.map((s, i) =>
                        i === f.currentStep ? "error" : s
                      ) as StepStatus[],
                    }
                  : f
              )
            );
            return;
          }

          if (backendStatus === "completed") {
            clearInterval(pollTimer);
            setFiles((prev) =>
              prev.map((f) =>
                f.id === entry.id
                  ? {
                      ...f,
                      currentStep: STEPS.length,
                      progress: STEPS.map(() => "done" as StepStatus),
                    }
                  : f
              )
            );
            return;
          }

          if (backendStatus === "processing") {
            // Gradually advance virtual steps to keep UI interactive
            if (virtualStep < 4) {
              virtualStep += 1;
              setFiles((prev) =>
                prev.map((f) =>
                  f.id === entry.id
                    ? {
                        ...f,
                        currentStep: virtualStep,
                        progress: f.progress.map((s, i) =>
                          i < virtualStep ? "done" : i === virtualStep ? "active" : "pending"
                        ) as StepStatus[],
                      }
                    : f
                )
              );
            }
          }
        } catch (pollErr) {
          console.error("Polling error:", pollErr);
        }
      }, pollInterval);

    } catch (err) {
      console.warn("Real API upload failed, falling back to local simulation mode:", err);
      setDemoMode(true);
      simulateIngestion(entry.id);
    }
  };

  const uploadAll = () => {
    files.forEach((f) => {
      if (f.currentStep === -1) uploadAndPoll(f);
    });
  };

  const pendingCount = files.filter((f) => f.currentStep === -1).length;
  const completedCount = files.filter((f) => f.currentStep === STEPS.length).length;

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
            Upload Documents
          </h1>
          {demoMode && (
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 border border-amber-500/30 text-amber-400 uppercase tracking-wider animate-pulse">
              Demo Mode (Backend Offline)
            </span>
          )}
        </div>
        <p className="text-sm text-zinc-400 mt-1">
          Upload PDFs, Office files, and images. DOCSCOPE AI will scan, render, and index them automatically.
        </p>
      </div>

      {/* Drop Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          relative cursor-pointer rounded-2xl border-2 border-dashed transition-all duration-300
          flex flex-col items-center justify-center py-16 px-8 text-center
          ${dragging
            ? "border-emerald-400 bg-emerald-500/5 scale-[1.01]"
            : "border-white/10 bg-zinc-900/30 hover:border-emerald-500/40 hover:bg-emerald-500/5"
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.png,.jpg,.jpeg"
          className="hidden"
          onChange={(e) => addFiles(Array.from(e.target.files ?? []))}
        />
        <div className={`p-5 rounded-2xl mb-4 transition-colors ${dragging ? "bg-emerald-500/20" : "bg-zinc-800"}`}>
          <UploadCloud size={40} className={dragging ? "text-emerald-400" : "text-zinc-500"} />
        </div>
        <p className="text-zinc-200 font-semibold text-lg">
          {dragging ? "Drop files here" : "Drag & drop files or click to browse"}
        </p>
        <p className="text-zinc-500 text-sm mt-1">
          PDF, Word, PowerPoint, Excel, PNG, JPG — up to 100 MB each
        </p>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-300">
              {files.length} file{files.length !== 1 ? "s" : ""} —{" "}
              <span className="text-emerald-400">{completedCount} complete</span>
            </h2>
            {pendingCount > 0 && (
              <button
                onClick={uploadAll}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow-lg shadow-emerald-600/20 transition-all duration-200"
              >
                <UploadCloud size={16} />
                Upload {pendingCount} file{pendingCount !== 1 ? "s" : ""}
              </button>
            )}
          </div>

          <div className="space-y-3">
            {files.map((entry) => {
              const Icon = getFileIcon(entry.file.name);
              const isDone = entry.currentStep === STEPS.length;
              const isError = entry.progress.includes("error");
              const isActive = entry.currentStep >= 0 && !isDone && !isError;
              const activeStep = STEPS[entry.currentStep];

              return (
                <div key={entry.id} className="glass-card rounded-2xl overflow-hidden">
                  {/* File Header Row */}
                  <div className="flex items-center gap-4 p-4">
                    <div className={`p-3 rounded-xl ${isDone ? "bg-emerald-500/15" : isError ? "bg-red-500/15" : "bg-zinc-800"}`}>
                      <Icon size={22} className={isDone ? "text-emerald-400" : isError ? "text-red-400" : "text-zinc-400"} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-zinc-200 truncate">{entry.file.name}</p>
                      <p className="text-xs text-zinc-500">{formatSize(entry.file.size)}</p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {isDone && <CheckCircle2 size={20} className="text-emerald-400" />}
                      {isError && <AlertCircle size={20} className="text-red-400" />}
                      {isActive && <Loader2 size={20} className="text-emerald-400 animate-spin" />}
                      {entry.currentStep === -1 && (
                        <button
                          onClick={() => removeFile(entry.id)}
                          className="p-1 text-zinc-500 hover:text-red-400 transition-colors"
                        >
                          <X size={16} />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Progress Steps — visible once active */}
                  {(isActive || isDone || isError) && (
                    <div className="px-4 pb-4">
                      <div className="flex items-center gap-0">
                        {STEPS.map((step, i) => {
                          const status = entry.progress[i];
                          return (
                            <React.Fragment key={step.id}>
                              <div className="flex flex-col items-center">
                                <div
                                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500
                                    ${status === "done" ? "bg-emerald-500 text-white" :
                                      status === "active" ? "bg-emerald-500/30 text-emerald-400 ring-2 ring-emerald-400/50 animate-pulse" :
                                      status === "error" ? "bg-red-500 text-white" :
                                      "bg-zinc-800 text-zinc-500"}
                                  `}
                                >
                                  {status === "done" ? "✓" : status === "error" ? "✗" : i + 1}
                                </div>
                                <span className={`text-[9px] mt-1 text-center w-14 leading-tight ${
                                  status === "active" ? "text-emerald-400" :
                                  status === "done" ? "text-emerald-400/70" :
                                  status === "error" ? "text-red-400" : "text-zinc-600"
                                }`}>
                                  {step.label}
                                </span>
                              </div>
                              {i < STEPS.length - 1 && (
                                <div className={`flex-1 h-px mb-4 transition-colors duration-500 ${
                                  status === "done" ? "bg-emerald-500/50" :
                                  status === "error" && i === entry.currentStep ? "bg-red-500/50" : "bg-zinc-700"
                                }`} />
                              )}
                            </React.Fragment>
                          );
                        })}
                      </div>
                      {isActive && activeStep && (
                        <p className="text-xs text-zinc-500 text-center mt-2 animate-pulse">
                          {activeStep.desc}…
                        </p>
                      )}
                      {isDone && (
                        <p className="text-xs text-emerald-400 text-center mt-2 font-semibold">
                          ✓ Document indexed and ready for search & chat
                        </p>
                      )}
                      {isError && entry.error && (
                        <p className="text-xs text-red-400 text-center mt-2 font-semibold flex items-center justify-center gap-1.5">
                          <AlertCircle size={12} />
                          Failed: {entry.error}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Supported formats */}
      <div className="glass-panel rounded-2xl p-5 border border-white/5">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Supported Formats</h3>
        <div className="flex flex-wrap gap-2">
          {["PDF", "DOCX", "DOC", "PPTX", "PPT", "XLSX", "XLS", "PNG", "JPG", "JPEG"].map((fmt) => (
            <span key={fmt} className="px-2.5 py-1 rounded-lg bg-zinc-800 text-zinc-300 text-xs font-mono">
              .{fmt.toLowerCase()}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
