import React, { useState } from 'react';
import { Eye, EyeOff, FileText, CheckCircle2 } from 'lucide-react';

export interface OcrChunk {
  id: string;
  page_number: number;
  text: string;
  confidence: number;
  bbox_x0: number | null;
  bbox_y0: number | null;
  bbox_x1: number | null;
  bbox_y1: number | null;
}

interface OCROverlayProps {
  imageUrl: string;
  chunks: OcrChunk[];
  pageNumber: number;
}

export function OCROverlay({ imageUrl, chunks, pageNumber }: OCROverlayProps) {
  const [showBoxes, setShowBoxes] = useState(true);
  const [hoveredChunk, setHoveredChunk] = useState<string | null>(null);

  const pageChunks = chunks.filter(c => c.page_number === pageNumber);

  return (
    <div className="flex flex-col h-full bg-zinc-950 rounded-2xl border border-white/5 overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-3 bg-zinc-900 border-b border-white/5">
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-emerald-400" />
          <span className="text-sm font-medium text-zinc-200">Page {pageNumber} OCR</span>
          <span className="px-2 py-0.5 rounded-full bg-zinc-800 text-[10px] text-zinc-400">
            {pageChunks.length} regions
          </span>
        </div>
        
        <button
          onClick={() => setShowBoxes(!showBoxes)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
            ${showBoxes ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/5 text-zinc-400 hover:text-zinc-200'}
          `}
        >
          {showBoxes ? <Eye size={14} /> : <EyeOff size={14} />}
          {showBoxes ? 'Hide Regions' : 'Show Regions'}
        </button>
      </div>

      {/* Interactive Image Container */}
      <div className="flex-1 relative overflow-auto p-4 flex items-center justify-center bg-black/20">
        <div className="relative inline-block shadow-2xl">
          {/* Base Image */}
          <img 
            src={imageUrl} 
            alt={`Page ${pageNumber}`} 
            className="block max-w-full h-auto object-contain bg-white rounded shadow-inner"
            style={{ maxHeight: 'calc(100vh - 200px)' }}
          />

          {/* Bounding Boxes */}
          {showBoxes && pageChunks.map(chunk => {
            if (chunk.bbox_x0 === null || chunk.bbox_y0 === null || chunk.bbox_x1 === null || chunk.bbox_y1 === null) {
              return null;
            }

            const isHovered = hoveredChunk === chunk.id;
            
            // Convert 0.0-1.0 normalized coordinates to percentages
            const top = `${chunk.bbox_y0 * 100}%`;
            const left = `${chunk.bbox_x0 * 100}%`;
            const width = `${(chunk.bbox_x1 - chunk.bbox_x0) * 100}%`;
            const height = `${(chunk.bbox_y1 - chunk.bbox_y0) * 100}%`;

            return (
              <div
                key={chunk.id}
                onMouseEnter={() => setHoveredChunk(chunk.id)}
                onMouseLeave={() => setHoveredChunk(null)}
                className={`absolute border-2 transition-all duration-200 cursor-help
                  ${isHovered 
                    ? 'border-emerald-400 bg-emerald-400/20 z-10' 
                    : 'border-emerald-500/40 bg-emerald-500/5 hover:border-emerald-400'}
                `}
                style={{ top, left, width, height }}
              >
                {/* Tooltip */}
                {isHovered && (
                  <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-max max-w-xs bg-zinc-900 border border-emerald-500/30 rounded-lg p-2 shadow-2xl z-50">
                    <p className="text-xs text-zinc-200 mb-1">{chunk.text}</p>
                    <div className="flex items-center gap-1 text-[10px] text-emerald-400">
                      <CheckCircle2 size={10} />
                      {Math.round(chunk.confidence * 100)}% confidence
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
