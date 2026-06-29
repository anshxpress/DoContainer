"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Send, Loader2, FileText, MessageSquare, Plus, ChevronLeft,
  ChevronRight, Sparkles, User, X, BookOpen,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Citation {
  doc_name: string;
  page_number: number;
  s3_signed_url?: string;
}

interface ContextPage {
  doc_name: string;
  page_number: number;
  text_snippet: string;
  s3_signed_url: string;
  page_id: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  streaming?: boolean;
}

interface Session {
  id: string;
  title: string;
}

// ─── Citation chip component ─────────────────────────────────────────────────

function CitationChip({
  citation,
  onClick,
}: {
  citation: Citation;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 px-2 py-0.5 mx-0.5 rounded-md bg-emerald-500/15 text-emerald-400 text-[11px] font-semibold border border-emerald-500/20 hover:bg-emerald-500/25 hover:border-emerald-400/40 transition-all duration-200 cursor-pointer"
    >
      <BookOpen size={9} />
      {citation.doc_name.replace(/\.[^.]+$/, "")}, p.{citation.page_number}
    </button>
  );
}

// ─── Render message content with interactive citation chips ──────────────────

function MessageContent({
  content,
  citations,
  onCitationClick,
}: {
  content: string;
  citations: Citation[];
  onCitationClick: (c: Citation) => void;
}) {
  // Replace [DocName, Page N] patterns with CitationChip components
  const parts: React.ReactNode[] = [];
  const citationPattern = /\[([^\],]+),\s*Page\s*(\d+)\]/gi;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = citationPattern.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index));
    }
    const docName = match[1].trim();
    const pageNum = parseInt(match[2], 10);
    const citation = { doc_name: docName, page_number: pageNum };
    parts.push(
      <CitationChip
        key={`${match.index}`}
        citation={citation}
        onClick={() => onCitationClick(citation)}
      />
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex));
  }

  // Format markdown-like bold
  const renderText = (text: string, key: string) => {
    const boldPattern = /\*\*([^*]+)\*\*/g;
    const textParts: React.ReactNode[] = [];
    let tLast = 0;
    let bMatch: RegExpExecArray | null;
    while ((bMatch = boldPattern.exec(text)) !== null) {
      if (bMatch.index > tLast) textParts.push(text.slice(tLast, bMatch.index));
      textParts.push(<strong key={bMatch.index} className="text-zinc-100 font-semibold">{bMatch[1]}</strong>);
      tLast = bMatch.index + bMatch[0].length;
    }
    if (tLast < text.length) textParts.push(text.slice(tLast));
    return <span key={key}>{textParts}</span>;
  };

  return (
    <span className="whitespace-pre-wrap leading-relaxed">
      {parts.map((part, i) =>
        typeof part === "string" ? renderText(part, `t${i}`) : part
      )}
    </span>
  );
}

// ─── Page Viewer Panel ────────────────────────────────────────────────────────

function PageViewer({
  pages,
  highlightedPage,
}: {
  pages: ContextPage[];
  highlightedPage: { doc_name: string; page_number: number } | null;
}) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const pageRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (!highlightedPage) return;
    const idx = pages.findIndex(
      (p) =>
        p.doc_name.toLowerCase() === highlightedPage.doc_name.toLowerCase() &&
        p.page_number === highlightedPage.page_number
    );
    if (idx >= 0) {
      setCurrentIdx(idx);
      pageRefs.current[idx]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [highlightedPage, pages]);

  if (pages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8 gap-4">
        <div className="p-5 rounded-2xl bg-zinc-800/60">
          <FileText size={36} className="text-zinc-600" />
        </div>
        <p className="text-zinc-500 text-sm font-medium">Ask a question to see relevant pages here</p>
        <p className="text-zinc-600 text-xs">Source pages appear as visual citations</p>
      </div>
    );
  }

  const page = pages[currentIdx];
  const isHighlighted =
    highlightedPage &&
    page.doc_name.toLowerCase() === highlightedPage.doc_name.toLowerCase() &&
    page.page_number === highlightedPage.page_number;

  return (
    <div className="flex flex-col h-full">
      {/* Page nav header */}
      <div className="shrink-0 p-3 border-b border-white/5 flex items-center justify-between bg-zinc-900/50">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-zinc-200 truncate">{page.doc_name}</p>
          <p className="text-[10px] text-zinc-500">Page {page.page_number} of {pages.length} pages</p>
        </div>
        <div className="flex items-center gap-1 shrink-0 ml-2">
          <button
            disabled={currentIdx === 0}
            onClick={() => setCurrentIdx((i) => i - 1)}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white disabled:opacity-30 hover:bg-white/5 transition-colors"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="text-[10px] text-zinc-500 w-10 text-center">{currentIdx + 1}/{pages.length}</span>
          <button
            disabled={currentIdx === pages.length - 1}
            onClick={() => setCurrentIdx((i) => i + 1)}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white disabled:opacity-30 hover:bg-white/5 transition-colors"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Page image */}
      <div className={`flex-1 overflow-auto transition-all duration-500 ${isHighlighted ? "ring-2 ring-emerald-400/50" : ""}`}>
        {page.s3_signed_url ? (
          <img
            src={page.s3_signed_url}
            alt={`${page.doc_name} page ${page.page_number}`}
            className="w-full object-contain"
          />
        ) : (
          <div className="h-full flex flex-col items-center justify-center gap-4 p-6">
            <div className={`p-5 rounded-2xl transition-colors ${isHighlighted ? "bg-emerald-500/15" : "bg-zinc-800/60"}`}>
              <FileText size={40} className={isHighlighted ? "text-emerald-400" : "text-zinc-600"} />
            </div>
            <div className="text-center">
              <p className="text-zinc-300 text-sm font-semibold">{page.doc_name}</p>
              <p className="text-zinc-500 text-xs">Page {page.page_number}</p>
            </div>
            {page.text_snippet && (
              <p className="text-zinc-500 text-xs italic text-center leading-relaxed max-w-xs">
                "{page.text_snippet.slice(0, 150)}…"
              </p>
            )}
          </div>
        )}
      </div>

      {/* Thumbnail strip */}
      {pages.length > 1 && (
        <div className="shrink-0 flex gap-2 p-2 overflow-x-auto border-t border-white/5">
          {pages.map((p, i) => {
            const isActive = i === currentIdx;
            const isHl = highlightedPage &&
              p.doc_name.toLowerCase() === highlightedPage.doc_name.toLowerCase() &&
              p.page_number === highlightedPage.page_number;
            return (
              <button
                key={p.page_id}
                ref={(el) => { pageRefs.current[i] = el; }}
                onClick={() => setCurrentIdx(i)}
                className={`shrink-0 w-12 h-16 rounded-lg overflow-hidden border-2 transition-all duration-200 ${
                  isActive ? "border-emerald-400" :
                  isHl ? "border-emerald-400/50" :
                  "border-transparent hover:border-white/20"
                }`}
              >
                {p.s3_signed_url ? (
                  <img src={p.s3_signed_url} alt="" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full bg-zinc-800 flex items-center justify-center">
                    <FileText size={14} className="text-zinc-600" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Main Chat Page ───────────────────────────────────────────────────────────

const DEMO_SESSION = "demo-session";

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hello! I'm DoContainer AI. Ask me anything about your uploaded documents. I'll answer with precise citations pointing to the exact pages.\n\nTry: *\"What was the revenue in Q3?\"* or *\"Summarize the vendor agreement terms.\"*",
      citations: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [contextPages, setContextPages] = useState<ContextPage[]>([]);
  const [highlightedCitation, setHighlightedCitation] = useState<Citation | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [showSessions, setShowSessions] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleCitationClick = useCallback((citation: Citation) => {
    setHighlightedCitation(citation);
  }, []);

  const sendMessage = async () => {
    const q = input.trim();
    if (!q || streaming) return;
    setInput("");

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
      citations: [],
    };
    const assistantId = crypto.randomUUID();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      citations: [],
      streaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setStreaming(true);

    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("docscope_token") : null;
      const params = new URLSearchParams({
        query: q,
        top_k: "5",
        ...(sessionId ? { session_id: sessionId } : {}),
      });

      const baseUrl = `http://127.0.0.1:8001/api/v1/chat/ask?${params}`;
      const resp = await fetch(baseUrl, {
        method: "POST",
        headers: {
          Accept: "text/event-stream",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      if (!resp.ok || !resp.body) throw new Error("Stream failed");

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(line.slice(6));
            if (payload.event === "session_id") {
              setSessionId(payload.session_id);
            } else if (payload.event === "context_pages") {
              setContextPages(payload.pages ?? []);
            } else if (payload.event === "token") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + payload.token }
                    : m
                )
              );
            } else if (payload.event === "done") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, streaming: false, citations: payload.citations ?? [] }
                    : m
                )
              );
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch {
      // Demo fallback — mock SSE stream
      const mockAnswer =
        `Based on your documents, here is what I found:\n\n` +
        `The Q3 report shows revenue of **$4.2M** [Q3_Report_Final.pdf, Page 5], ` +
        `an increase of **12.3% YoY** [Q3_Report_Final.pdf, Page 8].\n\n` +
        `Operating margins improved to **23.4%** due to efficiency initiatives [Q3_Report_Final.pdf, Page 8].`;

      for (const word of mockAnswer.split(" ")) {
        await new Promise((r) => setTimeout(r, 40));
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + word + " " } : m
          )
        );
      }
      const demoCitations = [
        { doc_name: "Q3_Report_Final.pdf", page_number: 5 },
        { doc_name: "Q3_Report_Final.pdf", page_number: 8 },
      ];
      setContextPages([
        { page_id: "1", doc_name: "Q3_Report_Final.pdf", page_number: 5, text_snippet: "Revenue for Q3 reached $4.2M, a 12.3% increase YoY...", s3_signed_url: "" },
        { page_id: "2", doc_name: "Q3_Report_Final.pdf", page_number: 8, text_snippet: "Operating margins improved to 23.4%...", s3_signed_url: "" },
      ]);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, streaming: false, citations: demoCitations } : m
        )
      );
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-5rem)] gap-0 -m-6 md:-m-10 overflow-hidden">

      {/* ── Left: Sessions Drawer ── */}
      {showSessions && (
        <div className="w-64 shrink-0 glass-panel border-r border-white/5 flex flex-col">
          <div className="p-4 border-b border-white/5 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-200">History</h3>
            <button onClick={() => setShowSessions(false)} className="text-zinc-500 hover:text-white transition-colors">
              <X size={16} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {sessions.length === 0 && (
              <p className="text-xs text-zinc-600 text-center py-6">No past sessions</p>
            )}
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => { setSessionId(s.id); setShowSessions(false); }}
                className={`w-full text-left px-3 py-2.5 rounded-xl text-xs transition-colors truncate ${
                  s.id === sessionId ? "bg-emerald-500/10 text-emerald-400" : "text-zinc-400 hover:bg-white/5 hover:text-zinc-200"
                }`}
              >
                {s.title}
              </button>
            ))}
          </div>
          <div className="p-3 border-t border-white/5">
            <button
              onClick={() => { setSessionId(null); setMessages([]); setContextPages([]); }}
              className="w-full flex items-center gap-2 px-3 py-2.5 rounded-xl text-xs text-zinc-400 hover:text-emerald-400 hover:bg-white/5 transition-colors"
            >
              <Plus size={14} /> New Chat
            </button>
          </div>
        </div>
      )}

      {/* ── Center: Chat Panel ── */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-white/5">
        {/* Chat header */}
        <div className="shrink-0 px-6 py-4 border-b border-white/5 flex items-center gap-3">
          <button
            onClick={() => setShowSessions(!showSessions)}
            className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <MessageSquare size={18} />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-semibold text-zinc-200">Document AI Chat</h1>
            <p className="text-[10px] text-zinc-500">Answers grounded in your documents with visual citations</p>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-emerald-400 font-semibold">Gemini 1.5 Flash</span>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
            >
              {/* Avatar */}
              <div className={`shrink-0 w-8 h-8 rounded-xl flex items-center justify-center text-xs font-bold ${
                msg.role === "user" ? "bg-zinc-700 text-zinc-300" : "bg-emerald-500/20 text-emerald-400"
              }`}>
                {msg.role === "user" ? <User size={14} /> : <Sparkles size={14} />}
              </div>

              {/* Bubble */}
              <div className={`max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1`}>
                <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-emerald-600/30 text-zinc-100 rounded-tr-sm border border-emerald-500/20"
                    : "glass-card text-zinc-200 rounded-tl-sm"
                }`}>
                  <MessageContent
                    content={msg.content}
                    citations={msg.citations}
                    onCitationClick={handleCitationClick}
                  />
                  {msg.streaming && (
                    <span className="inline-block w-0.5 h-4 bg-emerald-400 ml-0.5 animate-pulse align-middle" />
                  )}
                </div>
                {msg.citations.length > 0 && (
                  <div className="flex flex-wrap gap-1 px-1">
                    {msg.citations.map((c, i) => (
                      <CitationChip key={i} citation={c} onClick={() => handleCitationClick(c)} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 p-4 border-t border-white/5">
          <div className="flex gap-3 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
              }}
              placeholder="Ask a question about your documents… (Shift+Enter for newline)"
              rows={2}
              className="flex-1 resize-none rounded-2xl bg-zinc-900/80 border border-white/8 text-zinc-200 placeholder-zinc-600 text-sm px-4 py-3 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 transition-all"
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || streaming}
              className="p-3.5 rounded-2xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-all duration-200 shrink-0"
            >
              {streaming ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
            </button>
          </div>
        </div>
      </div>

      {/* ── Right: Page Viewer Panel ── */}
      <div className="w-80 xl:w-96 shrink-0 flex flex-col glass-panel">
        <div className="shrink-0 px-4 py-3 border-b border-white/5">
          <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
            <FileText size={12} />
            Source Pages
            {contextPages.length > 0 && (
              <span className="ml-auto text-emerald-400 font-bold normal-case">{contextPages.length} pages</span>
            )}
          </h2>
        </div>
        <div className="flex-1 overflow-hidden">
          <PageViewer pages={contextPages} highlightedPage={highlightedCitation} />
        </div>
      </div>
    </div>
  );
}
