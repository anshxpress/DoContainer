"use client";

import React from 'react';

import { Bot, Search, Image as ImageIcon, Type, Activity } from 'lucide-react';

export type SearchMode = 'hybrid' | 'vision' | 'text' | 'keyword';

interface SearchModeToggleProps {
  mode: SearchMode;
  onChange: (mode: SearchMode) => void;
}

export function SearchModeToggle({ mode, onChange }: SearchModeToggleProps) {
  const modes: { id: SearchMode; label: string; icon: React.ReactNode; desc: string }[] = [
    { 
      id: 'hybrid', 
      label: 'Hybrid Fusion', 
      icon: <Activity size={16} />, 
      desc: 'RRF-fused Vision + Text + Keyword (Best Quality)'
    },
    { 
      id: 'vision', 
      label: 'Vision (ColQwen2)', 
      icon: <ImageIcon size={16} />, 
      desc: 'Visual semantics only'
    },
    { 
      id: 'text', 
      label: 'Text (BGE-M3)', 
      icon: <Bot size={16} />, 
      desc: 'Dense semantic chunks only'
    },
    { 
      id: 'keyword', 
      label: 'Keyword (FTS)', 
      icon: <Type size={16} />, 
      desc: 'Exact word matching'
    }
  ];

  return (
    <div className="flex bg-zinc-900/50 p-1 rounded-xl border border-white/5 w-fit">
      {modes.map(m => {
        const isActive = mode === m.id;
        return (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            title={m.desc}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
              ${isActive 
                ? 'bg-emerald-500/20 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.1)]' 
                : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5'}
            `}
          >
            {m.icon}
            {m.label}
          </button>
        );
      })}
    </div>
  );
}
