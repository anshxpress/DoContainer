import logging
from typing import List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SemanticChunk:
    content: str
    page_number: int
    chunk_type: str
    section: Optional[str] = None
    heading: Optional[str] = None
    hierarchy: Optional[str] = None
    parent_section: Optional[str] = None

class SemanticChunkEngine:
    """
    Engine to group parsed document elements into semantically meaningful chunks.
    It adaptively adjusts chunk sizes based on the document type and ensures that
    structured elements like tables and lists are kept intact.
    """
    
    def __init__(self, target_size: int = 500, overlap_size: int = 50, document_type: Optional[str] = None):
        self.target_size = target_size
        self.overlap_size = overlap_size
        self.document_type = document_type or ""
        
        # Adaptive chunking logic based on doc type
        doc_type_lower = self.document_type.lower()
        if "contract" in doc_type_lower:
            self.target_size = 400
        elif "research" in doc_type_lower or "paper" in doc_type_lower:
            self.target_size = 600
        elif "manual" in doc_type_lower:
            self.target_size = 500
            
    def _estimate_tokens(self, text: str) -> int:
        # Simple heuristic: ~4 characters per token
        return len(text) // 4
        
    def process_elements(self, elements: List[Any]) -> List[SemanticChunk]:
        chunks: List[SemanticChunk] = []
        
        current_section = None
        current_heading = None
        current_parent_section = None
        hierarchy_stack: List[str] = []
        
        current_chunk_text = ""
        current_chunk_page = 1
        
        def commit_chunk(force_type: Optional[str] = None):
            nonlocal current_chunk_text
            if not current_chunk_text.strip():
                return
                
            chunks.append(SemanticChunk(
                content=current_chunk_text.strip(),
                page_number=current_chunk_page,
                chunk_type=force_type or "paragraph",
                section=current_section,
                heading=current_heading,
                hierarchy=" > ".join(hierarchy_stack) if hierarchy_stack else None,
                parent_section=current_parent_section
            ))
            
            # Simple overlap handling for continuous text
            if not force_type and len(current_chunk_text) > self.overlap_size * 4:
                # Keep roughly the last 'overlap_size' tokens
                current_chunk_text = current_chunk_text[-(self.overlap_size * 4):]
            else:
                current_chunk_text = ""
        
        for el in elements:
            text = getattr(el, "content", None) or getattr(el, "text", None)
            if not text or not text.strip():
                continue
                
            el_type = getattr(el, "element_type", "paragraph")
            page_no = getattr(el, "page_number", 1)
                
            if el_type == "heading":
                commit_chunk() # Flush previous
                
                # Keep text reasonably sized for DB columns
                heading_text = text.strip()[:255]
                current_heading = heading_text
                
                if not hierarchy_stack:
                    current_parent_section = heading_text
                    current_section = heading_text
                else:
                    current_section = heading_text
                    
                # Manage hierarchy up to 3 levels deep
                if len(hierarchy_stack) >= 3:
                    hierarchy_stack.pop()
                hierarchy_stack.append(heading_text[:50])
                
                current_chunk_text = text + "\n\n"
                current_chunk_page = page_no
                
            elif el_type in ["table", "list"]:
                # NEVER split tables or lists. Commit current buffer, then commit the table/list as a single block
                commit_chunk()
                current_chunk_page = page_no
                current_chunk_text = text
                commit_chunk(force_type=el_type)
                
            else:
                # Standard paragraph / text block
                if current_chunk_text:
                    if self._estimate_tokens(current_chunk_text + "\n" + text) > self.target_size:
                        commit_chunk()
                        current_chunk_page = page_no
                        current_chunk_text = text
                    else:
                        current_chunk_text += "\n" + text
                else:
                    current_chunk_page = page_no
                    current_chunk_text = text
                    
        commit_chunk()
        return chunks
