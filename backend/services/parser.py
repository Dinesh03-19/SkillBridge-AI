import os
import re
from typing import List, Dict, Any

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF using pdfplumber with fallback."""
    text_content = []
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text.strip())
    except Exception as e:
        # Fallback to PyPDF2 or basic read if available
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    pt = page.extract_text()
                    if pt:
                        text_content.append(pt.strip())
        except Exception:
            raise RuntimeError(f"Failed to extract PDF text from {file_path}: {e}")

    return "\n\n".join(text_content)

def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX using python-docx."""
    import docx
    doc = docx.Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)

def extract_text(file_path: str) -> str:
    """Generic text extractor based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(file_path)
    elif ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported formats: PDF, DOCX, TXT, MD.")

def chunk_text(text: str, target_chunk_size: int = 450, overlap_size: int = 50) -> List[Dict[str, Any]]:
    """
    Chunk text into ~400-500 words/tokens with 50-word overlap.
    Preserves sentence boundaries where possible.
    """
    # Clean redundant whitespace while preserving paragraph structure
    text = re.sub(r'\r\n', '\n', text)
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    if not paragraphs:
        # Fallback to splitting by words if no paragraphs
        words = text.split()
        if not words:
            return []
        chunks = []
        start = 0
        idx = 0
        while start < len(words):
            end = min(start + target_chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_str = " ".join(chunk_words)
            chunks.append({
                "chunk_index": idx,
                "chunk_text": chunk_str,
                "token_count": len(chunk_words)
            })
            idx += 1
            if end == len(words):
                break
            start += (target_chunk_size - overlap_size)
        return chunks

    chunks = []
    current_chunk_words = []
    chunk_index = 0

    for paragraph in paragraphs:
        p_words = paragraph.split()
        if not p_words:
            continue

        # If a single paragraph is larger than target_chunk_size, break it up
        if len(p_words) > target_chunk_size:
            p_start = 0
            while p_start < len(p_words):
                p_end = min(p_start + target_chunk_size, len(p_words))
                sub_words = p_words[p_start:p_end]
                chunks.append({
                    "chunk_index": chunk_index,
                    "chunk_text": " ".join(sub_words),
                    "token_count": len(sub_words)
                })
                chunk_index += 1
                if p_end == len(p_words):
                    break
                p_start += (target_chunk_size - overlap_size)
            continue

        if len(current_chunk_words) + len(p_words) > target_chunk_size and current_chunk_words:
            # Emit current chunk
            chunks.append({
                "chunk_index": chunk_index,
                "chunk_text": " ".join(current_chunk_words),
                "token_count": len(current_chunk_words)
            })
            chunk_index += 1
            # Keep overlap
            overlap_words = current_chunk_words[-overlap_size:] if len(current_chunk_words) >= overlap_size else current_chunk_words
            current_chunk_words = overlap_words + p_words
        else:
            current_chunk_words.extend(p_words)

    if current_chunk_words:
        chunks.append({
            "chunk_index": chunk_index,
            "chunk_text": " ".join(current_chunk_words),
            "token_count": len(current_chunk_words)
        })

    return chunks
