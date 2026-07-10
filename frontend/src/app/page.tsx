"use client";

import Link from "next/link";

import {
  FileSearch2,
  MessageSquare,
  ScanLine,
  Search,
  Sparkles,
  FolderOpen,
  Star,
  Copy,
  FileText,
  ChevronRight,
  Zap,
  Shield,
  Brain,
} from "lucide-react";

// ─── Feature card ──────────────────────────────────────────────────────────────
function FeatureCard({
  icon: Icon,
  title,
  description,
  color = "emerald",
}: {
  icon: React.ComponentType<any>;
  title: string;
  description: string;
  color?: string;
}) {
  const colorMap: Record<string, string> = {
    emerald: "bg-[#0047AB]/10 text-[#82C8E5]",
    cyan: "bg-[#82C8E5]/10 text-[#82C8E5]",
    indigo: "bg-[#6D8196]/10 text-[#6D8196]",
    amber: "bg-amber-500/10 text-amber-400",
    rose: "bg-rose-500/10 text-rose-400",
    violet: "bg-violet-500/10 text-violet-400",
  };
  return (
    <div className="rounded-2xl border border-white/5 bg-zinc-900/60 p-6 flex flex-col gap-4 hover:border-[#0047AB]/20 hover:bg-zinc-900/80 transition-all duration-300 group">
      <div className={`p-3 w-fit rounded-xl ${colorMap[color]}`}>
        <Icon size={22} />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-zinc-100 mb-1">{title}</h3>
        <p className="text-xs text-zinc-500 leading-relaxed">{description}</p>
      </div>
    </div>
  );
}

// ─── Use-case row ──────────────────────────────────────────────────────────────
function UseCaseRow({
  number,
  title,
  description,
  query,
}: {
  number: string;
  title: string;
  description: string;
  query: string;
}) {
  return (
    <div className="flex gap-6 items-start">
      <span className="text-3xl font-black text-[#0047AB]/20 shrink-0 leading-none mt-1">
        {number}
      </span>
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
        <p className="text-xs text-zinc-500 leading-relaxed">{description}</p>
        <div className="flex items-center gap-2 bg-zinc-900/80 border border-white/5 rounded-xl px-4 py-2.5">
          <MessageSquare size={13} className="text-[#82C8E5] shrink-0" />
          <span className="text-xs text-zinc-400 italic">&ldquo;{query}&rdquo;</span>
        </div>
      </div>
    </div>
  );
}

// ─── Pipeline step ─────────────────────────────────────────────────────────────
function PipelineStep({
  label,
  sub,
  last = false,
}: {
  label: string;
  sub?: string;
  last?: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="px-5 py-2.5 rounded-xl bg-zinc-900/80 border border-white/5 text-xs font-semibold text-zinc-200 text-center whitespace-nowrap">
        {label}
        {sub && <span className="block text-[10px] text-zinc-500 font-normal mt-0.5">{sub}</span>}
      </div>
      {!last && <ChevronRight size={14} className="text-zinc-600 rotate-90" />}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#03030a] text-zinc-100 font-sans overflow-x-hidden">
      {/* ── Background glows ──────────────────────────────────────────────────── */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-[#0047AB]/8 rounded-full blur-[130px]" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-[#6D8196]/5 rounded-full blur-[120px]" />
      </div>

      {/* ── Nav ───────────────────────────────────────────────────────────────── */}
      <nav className="relative z-10 border-b border-white/5 bg-[#03030a]/80 backdrop-blur-sm sticky top-0">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[#0047AB]/10">
              <FileSearch2 size={22} className="text-[#82C8E5]" />
            </div>
            <div>
              <span className="font-bold text-base tracking-wide bg-gradient-to-r from-[#82C8E5] to-[#dff0fc] bg-clip-text text-transparent">
                DoContainer
              </span>
              <span className="ml-2 text-[10px] text-zinc-500 uppercase tracking-widest font-medium">
                Personal
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="text-sm text-zinc-400 hover:text-zinc-200 transition-colors px-4 py-2"
            >
              Sign In
            </Link>
            <Link
              href="/login"
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#0047AB] hover:bg-[#1a5fc4] text-white text-sm font-semibold shadow-lg shadow-[#0047AB]/30 transition-all duration-200"
            >
              Get Started
              <ChevronRight size={15} />
            </Link>
          </div>
        </div>
      </nav>

      <main className="relative z-10 max-w-6xl mx-auto px-6">

        {/* ── Hero ────────────────────────────────────────────────────────────── */}
        <section className="text-center py-24 space-y-8">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#0047AB]/25 bg-[#0047AB]/5 text-[#82C8E5] text-xs font-semibold">
            <Sparkles size={12} />
            AI-Powered · Semantic Search · Retrieval-Augmented Generation
          </div>

          <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-tight">
            Your documents,{" "}
            <span className="bg-gradient-to-r from-[#82C8E5] via-cyan-400 to-[#6D8196] bg-clip-text text-transparent">
              finally intelligent.
            </span>
          </h1>

          <p className="max-w-2xl mx-auto text-lg text-zinc-400 leading-relaxed">
            Upload PDFs, scan documents, and ask questions in plain English.
            DoContainer reads your files, understands them, and surfaces exactly what you
            need — in seconds.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/login"
              className="flex items-center gap-2 px-7 py-3.5 rounded-2xl bg-[#0047AB] hover:bg-[#1a5fc4] text-white font-semibold text-sm shadow-2xl shadow-[#0047AB]/35 transition-all duration-200 hover:scale-105"
            >
              Start for free
              <ChevronRight size={16} />
            </Link>
            <a
              href="#how-it-works"
              className="flex items-center gap-2 px-7 py-3.5 rounded-2xl border border-white/10 text-zinc-300 font-semibold text-sm hover:border-white/20 hover:text-white transition-all duration-200"
            >
              See how it works
            </a>
          </div>

          {/* Fake search bar demo */}
          <div className="max-w-xl mx-auto mt-6 flex items-center gap-3 px-5 py-3.5 rounded-2xl bg-zinc-900/80 border border-white/5 shadow-xl">
            <Search size={16} className="text-[#82C8E5] shrink-0" />
            <span className="text-sm text-zinc-500 italic">
              &ldquo;Summarise the key risks in my Q3 financial report&rdquo;
            </span>
          </div>
        </section>

        {/* ── Problem Statement ────────────────────────────────────────────────── */}
        <section className="py-20" id="problem">
          <div className="rounded-3xl border border-white/5 bg-zinc-900/40 p-10 md:p-14 space-y-10">
            <div className="max-w-2xl space-y-3">
              <span className="text-xs font-bold uppercase tracking-widest text-rose-400">
                The Problem
              </span>
              <h2 className="text-3xl font-black tracking-tight">
                Documents are everywhere. Knowledge is nowhere.
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {[
                {
                  emoji: "📂",
                  title: "Lost in folders",
                  body: "You know the answer is in one of those PDFs. But which one? And what page? Folder browsing doesn't scale.",
                },
                {
                  emoji: "🔍",
                  title: "Search by filename only",
                  body: "Traditional search finds the file name — not the content inside. If you don't know what the file is called, you're stuck.",
                },
                {
                  emoji: "🖼️",
                  title: "Scanned PDFs are invisible",
                  body: "Receipts, contracts, handwritten notes — none of them are searchable unless someone manually types them out. That's never going to happen.",
                },
              ].map((item) => (
                <div key={item.title} className="space-y-3">
                  <span className="text-3xl">{item.emoji}</span>
                  <h3 className="text-sm font-semibold text-zinc-200">{item.title}</h3>
                  <p className="text-xs text-zinc-500 leading-relaxed">{item.body}</p>
                </div>
              ))}
            </div>

            <div className="border-t border-white/5 pt-8">
              <p className="text-zinc-300 text-sm leading-relaxed max-w-3xl">
                <span className="font-semibold text-[#82C8E5]">DoContainer solves this</span>
                {" by converting every uploaded document into an intelligent knowledge asset — parsed, embedded, and immediately searchable in plain English. Scanned documents are automatically OCR'd. Digital PDFs go straight to semantic indexing. You ask a question. DoContainer finds the answer."}
              </p>
            </div>
          </div>
        </section>

        {/* ── Features ─────────────────────────────────────────────────────────── */}
        <section className="py-20" id="features">
          <div className="text-center mb-14 space-y-3">
            <span className="text-xs font-bold uppercase tracking-widest text-[#82C8E5]">
              What you get
            </span>
            <h2 className="text-3xl font-black tracking-tight">
              Everything you need. Nothing you don&rsquo;t.
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            <FeatureCard
              icon={ScanLine}
              color="cyan"
              title="Adaptive OCR"
              description="Scanned PDFs are automatically detected and OCR'd using PaddleOCR. Digital PDFs skip OCR entirely and go straight to semantic indexing — no wasted compute."
            />
            <FeatureCard
              icon={Brain}
              color="violet"
              title="Semantic Search"
              description="BGE-M3 embeddings + Qdrant vector search + PostgreSQL full-text search fused with Reciprocal Rank Fusion. Find documents by meaning, not by keyword."
            />
            <FeatureCard
              icon={MessageSquare}
              color="indigo"
              title="AI Chat with Documents"
              description="Ask questions in plain English. DoContainer retrieves the most relevant chunks from your documents and generates grounded answers using Gemini — with source citations."
            />
            <FeatureCard
              icon={FileText}
              color="emerald"
              title="Executive Summaries"
              description="Every uploaded document gets an AI-generated executive summary, key topics, reading time estimate, and complexity score — automatically."
            />
            <FeatureCard
              icon={Copy}
              color="amber"
              title="Duplicate Detection"
              description="Semantic similarity scoring automatically flags near-duplicate documents across your workspace so you don't end up with five versions of the same contract."
            />
            <FeatureCard
              icon={FolderOpen}
              color="rose"
              title="Folders, Tags & Favorites"
              description="Organize your workspace with nested folders, tags, and favorites. Pin your most important documents for instant access from the dashboard."
            />
          </div>
        </section>

        {/* ── Use Cases ─────────────────────────────────────────────────────────── */}
        <section className="py-20" id="use-cases">
          <div className="text-center mb-14 space-y-3">
            <span className="text-xs font-bold uppercase tracking-widest text-[#82C8E5]">
              Use Cases
            </span>
            <h2 className="text-3xl font-black tracking-tight">
              Who is DoContainer Personal for?
            </h2>
            <p className="text-zinc-500 text-sm max-w-xl mx-auto">
              Anyone who deals with documents and wishes they could just ask them a question.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <UseCaseRow
              number="01"
              title="Researchers & Students"
              description="Upload papers, thesis chapters, and lecture notes. Ask questions across your entire reading list without re-reading everything."
              query="What methods did Chen et al. use for measuring latency in their 2023 paper?"
            />
            <UseCaseRow
              number="02"
              title="Freelancers & Contractors"
              description="Keep contracts, invoices, SOWs, and client briefs in one place. Find terms and conditions without scrolling through 80-page PDFs."
              query="What is the payment schedule in my Acme Corp contract?"
            />
            <UseCaseRow
              number="03"
              title="Personal Finance"
              description="Upload bank statements, tax returns, and insurance policies. Ask what you spent on groceries last quarter or find your deductible."
              query="How much did I spend on utilities in Q2?"
            />
            <UseCaseRow
              number="04"
              title="Small Business Owners"
              description="Store your operations manuals, supplier agreements, and compliance documents. Get instant answers without calling a lawyer."
              query="What are my termination clauses with Supplier XYZ?"
            />
            <UseCaseRow
              number="05"
              title="Healthcare & Legal"
              description="Upload medical reports, lab results, and legal briefs. Summarise complex clinical language into plain English."
              query="Summarise the key findings from my MRI report."
            />
            <UseCaseRow
              number="06"
              title="Developers & Engineers"
              description="Index technical specs, API docs, RFCs, and runbooks. Search across all of them simultaneously instead of context-switching between tabs."
              query="Where is rate limiting configured in the API spec?"
            />
          </div>
        </section>

        {/* ── AI Pipeline ───────────────────────────────────────────────────────── */}
        <section className="py-20" id="how-it-works">
          <div className="text-center mb-14 space-y-3">
            <span className="text-xs font-bold uppercase tracking-widest text-[#6D8196]">
              How it works
            </span>
            <h2 className="text-3xl font-black tracking-tight">
              The adaptive AI pipeline
            </h2>
            <p className="text-zinc-500 text-sm max-w-lg mx-auto">
              Every document is processed through an adaptive pipeline that chooses the right path based on document type — no manual configuration needed.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Digital PDF path */}
            <div className="rounded-2xl border border-white/5 bg-zinc-900/40 p-8 space-y-5">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[#0047AB]/10">
                  <FileSearch2 size={18} className="text-[#82C8E5]" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-zinc-200">Digital PDF</h3>
                  <p className="text-[10px] text-zinc-500">Text-selectable, embedded content</p>
                </div>
              </div>
              <div className="flex flex-col items-start">
                <PipelineStep label="Docling Parser" sub="Structure extraction" />
                <PipelineStep label="Semantic Chunking" sub="Sentence-aware splitting" />
                <PipelineStep label="BGE-M3 Embeddings" sub="1024-dim dense vectors" />
                <PipelineStep label="Qdrant Index" sub="Vector + FTS storage" />
                <PipelineStep label="AI Metadata + Summary" last />
              </div>
            </div>

            {/* Scanned PDF path */}
            <div className="rounded-2xl border border-white/5 bg-zinc-900/40 p-8 space-y-5">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[#82C8E5]/10">
                  <ScanLine size={18} className="text-[#82C8E5]" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-zinc-200">Scanned PDF</h3>
                  <p className="text-[10px] text-zinc-500">Image-based, no embedded text</p>
                </div>
              </div>
              <div className="flex flex-col items-start">
                <PipelineStep label="PaddleOCR" sub="Text recognition + confidence filter" />
                <PipelineStep label="Docling Parser" sub="Structure extraction" />
                <PipelineStep label="BGE-M3 Embeddings" sub="1024-dim dense vectors" />
                <PipelineStep label="Qdrant Index" sub="Vector + FTS storage" />
                <PipelineStep label="AI Metadata + Summary" last />
              </div>
            </div>
          </div>

          <p className="text-center text-xs text-zinc-600 mt-6">
            OCR is <span className="text-zinc-400 font-semibold">never run on digital PDFs</span> — the pipeline detects text density per page and routes adaptively.
          </p>
        </section>

        {/* ── Trust bar ─────────────────────────────────────────────────────────── */}
        <section className="py-16">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              {
                icon: Zap,
                color: "text-amber-400",
                bg: "bg-amber-500/10",
                title: "Fast by design",
                body: "Hybrid search with RRF fusion returns results in under 200 ms. No cold-start, no waiting.",
              },
              {
                icon: Shield,
                color: "text-[#82C8E5]",
                bg: "bg-[#0047AB]/10",
                title: "Your data stays yours",
                body: "RS256 JWT authentication. Files stored in your own MinIO / S3 bucket. No third-party document access.",
              },
              {
                icon: Star,
                color: "text-violet-400",
                bg: "bg-violet-500/10",
                title: "Enterprise-ready architecture",
                body: "Built on a full enterprise backend. ACL, approvals, audit, and teams are disabled — not deleted — and can be re-enabled at any time.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="rounded-2xl border border-white/5 bg-zinc-900/40 p-7 flex flex-col gap-4"
              >
                <div className={`p-3 w-fit rounded-xl ${item.bg}`}>
                  <item.icon size={20} className={item.color} />
                </div>
                <h3 className="text-sm font-semibold text-zinc-200">{item.title}</h3>
                <p className="text-xs text-zinc-500 leading-relaxed">{item.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── CTA ───────────────────────────────────────────────────────────────── */}
        <section className="py-24 text-center space-y-8">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[#0047AB]/25 bg-[#0047AB]/5 text-[#82C8E5] text-xs font-semibold">
            <Sparkles size={12} />
            Free to self-host · Open architecture
          </div>
          <h2 className="text-4xl md:text-5xl font-black tracking-tight">
            Ready to talk to your documents?
          </h2>
          <p className="text-zinc-400 text-sm max-w-md mx-auto">
            Create your personal workspace in seconds. No organization setup. No team invites. Just you and your documents.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/login"
              className="flex items-center gap-2 px-8 py-4 rounded-2xl bg-[#0047AB] hover:bg-[#1a5fc4] text-white font-bold text-sm shadow-2xl shadow-[#0047AB]/35 transition-all duration-200 hover:scale-105"
            >
              Create my workspace
              <ChevronRight size={16} />
            </Link>
            <Link
              href="/login"
              className="flex items-center gap-2 px-8 py-4 rounded-2xl border border-white/10 text-zinc-300 font-semibold text-sm hover:border-white/20 transition-all duration-200"
            >
              Sign in
            </Link>
          </div>
        </section>

      </main>

      {/* ── Footer ──────────────────────────────────────────────────────────────── */}
      <footer className="relative z-10 border-t border-white/5 py-10">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-1.5 rounded-lg bg-[#0047AB]/10">
              <FileSearch2 size={16} className="text-[#82C8E5]" />
            </div>
            <span className="text-sm font-bold bg-gradient-to-r from-[#82C8E5] to-[#dff0fc] bg-clip-text text-transparent">
              DoContainer Personal
            </span>
          </div>
          <p className="text-xs text-zinc-600">
            Enterprise Edition preserved in codebase · Set{" "}
            <code className="font-mono text-zinc-500">APP_MODE=enterprise</code> to restore
          </p>
        </div>
      </footer>
    </div>
  );
}
