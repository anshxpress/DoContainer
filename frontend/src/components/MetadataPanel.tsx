"use client";

import React from 'react';

import { Tag, Building, Clock, FileType, AlignLeft, Hash } from 'lucide-react';

export interface Keyword {
  keyword: string;
  score: number;
}

export interface Entity {
  entity_text: string;
  entity_type: string;
}

export interface DocumentMetadata {
  summary: string | null;
  reading_time_minutes: number | null;
  complexity_score: number | null;
  document_type: string | null;
  topics: string[];
  keywords: Keyword[];
  entities: Entity[];
  category: string | null;
  department: string | null;
}

interface MetadataPanelProps {
  metadata: DocumentMetadata;
}

export function MetadataPanel({ metadata }: MetadataPanelProps) {
  return (
    <div className="flex flex-col h-full bg-zinc-950 rounded-2xl border border-white/5 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 bg-zinc-900 border-b border-white/5">
        <h3 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
          <AlignLeft size={18} className="text-emerald-400" />
          AI Document Analysis
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-8">
        
        {/* Executive Summary */}
        {metadata.summary && (
          <section>
            <h4 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wider">Executive Summary</h4>
            <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/10 text-zinc-300 text-sm leading-relaxed">
              {metadata.summary}
            </div>
          </section>
        )}

        {/* Quick Stats Grid */}
        <section className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-zinc-900 border border-white/5 flex items-start gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
              <Clock size={16} />
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Reading Time</p>
              <p className="text-sm font-medium text-zinc-200">
                {metadata.reading_time_minutes ? `~${metadata.reading_time_minutes} min` : 'Unknown'}
              </p>
            </div>
          </div>
          
          <div className="p-4 rounded-xl bg-zinc-900 border border-white/5 flex items-start gap-3">
            <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400">
              <FileType size={16} />
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Document Type</p>
              <p className="text-sm font-medium text-zinc-200 capitalize">
                {metadata.document_type || 'General'}
              </p>
            </div>
          </div>
          
          <div className="p-4 rounded-xl bg-zinc-900 border border-white/5 flex items-start gap-3">
            <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400">
              <Hash size={16} />
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Complexity Score</p>
              <div className="flex items-center gap-2 mt-1">
                <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-amber-400 rounded-full" 
                    style={{ width: `${(metadata.complexity_score || 0) * 100}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-zinc-300">
                  {Math.round((metadata.complexity_score || 0) * 10)}/10
                </span>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-900 border border-white/5 flex items-start gap-3">
            <div className="p-2 bg-pink-500/10 rounded-lg text-pink-400">
              <Building size={16} />
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-0.5">Department</p>
              <p className="text-sm font-medium text-zinc-200">
                {metadata.department || 'Cross-functional'}
              </p>
            </div>
          </div>
        </section>

        {/* Topics & Keywords */}
        <section className="space-y-4">
          {metadata.topics && metadata.topics.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wider flex items-center gap-2">
                <Hash size={14} /> Topics
              </h4>
              <div className="flex flex-wrap gap-2">
                {metadata.topics.map((topic, i) => (
                  <span key={i} className="px-3 py-1 rounded-full bg-zinc-800 text-xs font-medium text-zinc-300 border border-white/5">
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          )}

          {metadata.keywords && metadata.keywords.length > 0 && (
            <div className="pt-2">
              <h4 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wider flex items-center gap-2">
                <Tag size={14} /> Top Keywords
              </h4>
              <div className="flex flex-wrap gap-2">
                {metadata.keywords.slice(0, 15).map((kw, i) => (
                  <span 
                    key={i} 
                    className="px-2 py-1 rounded border border-emerald-500/20 bg-emerald-500/5 text-xs text-emerald-300/80"
                    title={`Score: ${Math.round(kw.score * 100)}%`}
                  >
                    {kw.keyword}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Named Entities */}
        {metadata.entities && metadata.entities.length > 0 && (
          <section className="pt-4 border-t border-white/5">
            <h4 className="text-sm font-medium text-zinc-400 mb-4 uppercase tracking-wider flex items-center gap-2">
              <Building size={14} /> Named Entities
            </h4>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
              {['ORG', 'PERSON', 'MONEY', 'DATE', 'LOCATION', 'LAW', 'PRODUCT'].map(type => {
                const typeEntities = metadata.entities.filter(e => e.entity_type === type);
                if (typeEntities.length === 0) return null;
                
                return (
                  <div key={type} className="space-y-2">
                    <p className="text-[10px] font-bold text-zinc-500 uppercase">{type}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {typeEntities.slice(0, 8).map((ent, i) => (
                        <span key={i} className="px-2 py-1 rounded bg-zinc-900 text-xs text-zinc-300 border border-white/10">
                          {ent.entity_text}
                        </span>
                      ))}
                      {typeEntities.length > 8 && (
                        <span className="px-2 py-1 rounded text-xs text-zinc-500">+{typeEntities.length - 8} more</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

      </div>
    </div>
  );
}
