"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, FileText, Loader2, MessageSquare, Info, Download, Maximize2, Share2, CornerDownRight
} from "lucide-react";
import ReactMarkdown from 'react-markdown';

type DocumentDetail = {
  id: string;
  name: string;
  status: string;
  file_type: string;
  file_size: number;
  created_at: string;
};

type DocumentPage = {
  id: string;
  page_number: number;
  image_url: string;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export default function DocumentViewerPage() {
  const params = useParams();
  const router = useRouter();
  const docId = params.id as string;

  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [pages, setPages] = useState<DocumentPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"chat" | "details">("chat");

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    fetchDocumentDetails();
    fetchDocumentPages();
  }, [docId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const fetchDocumentDetails = async () => {
    const token = localStorage.getItem("docscope_token");
    if (!token) return;

    try {
      const res = await fetch(`/api/v1/documents/${docId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setDocument(await res.json());
      }
    } catch (e) {
      console.error("Failed to fetch document", e);
    }
  };

  const fetchDocumentPages = async () => {
    const token = localStorage.getItem("docscope_token");
    if (!token) return;

    try {
      const res = await fetch(`/api/v1/documents/${docId}/pages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setPages(await res.json());
      }
    } catch (e) {
      console.error("Failed to fetch pages", e);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || isTyping) return;

    const token = localStorage.getItem("docscope_token");
    if (!token) return;

    const query = chatInput.trim();
    setChatInput("");
    setMessages(prev => [...prev, { role: "user", content: query }]);
    setIsTyping(true);

    try {
      let url = `/api/v1/chat/ask?query=${encodeURIComponent(query)}&document_id=${docId}&top_k=5`;
      if (sessionId) url += `&session_id=${sessionId}`;

      const res = await fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });

      if (!res.ok || !res.body) throw new Error("Chat stream failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      let assistantMsg = "";
      setMessages(prev => [...prev, { role: "assistant", content: "" }]);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.replace("data: ", "");
            if (!dataStr) continue;

            try {
              const data = JSON.parse(dataStr);
              if (data.event === "session_id") {
                setSessionId(data.session_id);
              } else if (data.event === "token") {
                assistantMsg += data.token;
                setMessages(prev => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1].content = assistantMsg;
                  return newMsgs;
                });
              } else if (data.event === "done") {
                setIsTyping(false);
              }
            } catch (err) {
              console.error("Error parsing SSE JSON", err);
            }
          }
        }
      }
    } catch (err) {
      console.error("Chat error:", err);
      setIsTyping(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Loader2 className="animate-spin text-emerald-500" size={32} />
      </div>
    );
  }

  if (!document) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-4rem)]">
        <p className="text-zinc-400">Document not found.</p>
        <button onClick={() => router.push("/dashboard/documents")} className="mt-4 text-emerald-500 hover:underline">
          Go back to Documents
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-zinc-950 -mx-6 -my-8 px-4 py-4 overflow-hidden">
      
      {/* Header Toolbar */}
      <div className="flex items-center justify-between pb-4 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-4">
          <button onClick={() => router.push("/dashboard/documents")} className="p-2 hover:bg-zinc-900 rounded-lg text-zinc-400 hover:text-white transition-colors">
            <ArrowLeft size={20} />
          </button>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <FileText size={20} className="text-emerald-400" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-zinc-100 truncate max-w-md">{document.name}</h1>
              <div className="flex items-center gap-2 text-xs text-zinc-500 mt-0.5">
                <span className={`px-2 py-0.5 rounded-full ${
                  document.status === "completed" ? "bg-emerald-500/20 text-emerald-400" :
                  document.status === "processing" ? "bg-amber-500/20 text-amber-400" :
                  "bg-red-500/20 text-red-400"
                }`}>
                  {document.status}
                </span>
                <span>•</span>
                <span>{(document.file_size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={() => router.push(`/dashboard/documents/${docId}/metadata`)}
            className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 rounded-lg text-xs font-semibold transition-colors"
          >
            <Info size={14} /> AI Metadata
          </button>
          <button 
            onClick={() => router.push(`/dashboard/documents/${docId}/ocr`)}
            className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 rounded-lg text-xs font-semibold transition-colors"
          >
            <Maximize2 size={14} /> Inspect OCR
          </button>
          <div className="w-px h-6 bg-white/10 mx-1"></div>
          <button className="p-2 hover:bg-zinc-900 rounded-lg text-zinc-400 hover:text-white transition-colors" title="Share">
            <Share2 size={18} />
          </button>
          <button className="p-2 hover:bg-zinc-900 rounded-lg text-zinc-400 hover:text-white transition-colors" title="Download">
            <Download size={18} />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden pt-4 gap-6">
        
        {/* Left: Document Viewer */}
        <div className="flex-1 bg-zinc-900/50 rounded-2xl border border-white/5 overflow-y-auto p-8 custom-scrollbar">
          {pages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-zinc-500">
              {document.status === "processing" ? (
                <>
                  <Loader2 className="animate-spin mb-4" size={32} />
                  <p>Processing document pages...</p>
                </>
              ) : (
                <p>No preview pages available.</p>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-8">
              {pages.map((page) => (
                <div key={page.id} className="relative group bg-white p-1 rounded-sm shadow-2xl shrink-0 w-full max-w-4xl">
                  <img src={page.image_url} alt={`Page ${page.page_number}`} className="w-full h-auto object-contain" />
                  <div className="absolute top-2 right-2 bg-black/50 backdrop-blur-sm text-white px-3 py-1 rounded-full text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                    Page {page.page_number}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Side Panel (Chat & Details) */}
        <div className="w-96 flex flex-col glass-panel rounded-2xl border border-white/5 shrink-0 overflow-hidden">
          
          {/* Panel Tabs */}
          <div className="flex border-b border-white/5">
            <button 
              onClick={() => setActiveTab("chat")}
              className={`flex-1 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                activeTab === "chat" ? "text-emerald-400 border-b-2 border-emerald-400" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <MessageSquare size={16} /> Chat
            </button>
            <button 
              onClick={() => setActiveTab("details")}
              className={`flex-1 py-3 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                activeTab === "details" ? "text-emerald-400 border-b-2 border-emerald-400" : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <Info size={16} /> Details
            </button>
          </div>

          {/* Panel Content */}
          <div className="flex-1 overflow-hidden relative">
            
            {/* Chat Tab */}
            {activeTab === "chat" && (
              <div className="absolute inset-0 flex flex-col">
                <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                  {messages.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center p-6 space-y-4">
                      <div className="w-12 h-12 bg-emerald-500/10 rounded-xl flex items-center justify-center">
                        <MessageSquare className="text-emerald-500" size={24} />
                      </div>
                      <div>
                        <h3 className="text-zinc-200 font-medium mb-1">Chat with this document</h3>
                        <p className="text-sm text-zinc-500">Ask questions, summarize, or extract key information from this specific document.</p>
                      </div>
                    </div>
                  ) : (
                    messages.map((m, idx) => (
                      <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                          m.role === 'user' 
                            ? 'bg-emerald-500 text-white' 
                            : 'bg-zinc-800/80 text-zinc-300 border border-white/5'
                        }`}>
                          <div className="prose prose-invert max-w-none text-sm">
                            <ReactMarkdown>
                              {m.content}
                            </ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                  {isTyping && (
                    <div className="flex justify-start">
                      <div className="bg-zinc-800/80 rounded-2xl px-4 py-3 border border-white/5 flex gap-1 items-center h-10">
                        <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce"></span>
                        <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></span>
                        <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }}></span>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                <div className="p-4 border-t border-white/5 bg-zinc-900/50">
                  <form onSubmit={handleSendMessage} className="relative">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="Ask anything..."
                      disabled={isTyping}
                      className="w-full bg-zinc-950 border border-white/10 rounded-xl pl-4 pr-12 py-3 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500/50 transition-colors disabled:opacity-50"
                    />
                    <button 
                      type="submit"
                      disabled={isTyping || !chatInput.trim()}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-emerald-500 hover:bg-emerald-500/10 rounded-lg transition-colors disabled:opacity-50 disabled:hover:bg-transparent"
                    >
                      <CornerDownRight size={18} />
                    </button>
                  </form>
                </div>
              </div>
            )}

            {/* Details Tab */}
            {activeTab === "details" && (
              <div className="absolute inset-0 overflow-y-auto p-6 text-sm text-zinc-400 space-y-6">
                <div>
                  <h4 className="text-zinc-200 font-medium mb-3">Document Info</h4>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span>Type</span>
                      <span className="text-zinc-200 uppercase">{document.file_type}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Size</span>
                      <span className="text-zinc-200">{(document.file_size / 1024 / 1024).toFixed(2)} MB</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Uploaded</span>
                      <span className="text-zinc-200">{new Date(document.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Pages</span>
                      <span className="text-zinc-200">{pages.length}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
