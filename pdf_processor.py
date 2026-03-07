"""
PDF Processing Module
Handles PDF upload, text extraction, and content analysis
"""

import io
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Try to import PDF libraries with better error handling
PDFPLUMBER_AVAILABLE = False
PYPDF2_AVAILABLE = False
pdfplumber = None
PdfReader = None

try:
    import pdfplumber as _pdfplumber
    pdfplumber = _pdfplumber
    PDFPLUMBER_AVAILABLE = True
    print("[PDF] pdfplumber loaded successfully")
except ImportError as e:
    print(f"[PDF] pdfplumber not available: {e}")

try:
    from PyPDF2 import PdfReader as _PdfReader
    PdfReader = _PdfReader
    PYPDF2_AVAILABLE = True
    print("[PDF] PyPDF2 loaded successfully")
except ImportError as e:
    print(f"[PDF] PyPDF2 not available: {e}")

from config import config


@dataclass
class PDFExtractedContent:
    """Data class for extracted PDF content"""
    text: str
    total_pages: int
    extracted_pages: int
    metadata: Dict[str, Any]
    truncated: bool
    file_name: str
    file_size_mb: float


class PDFProcessor:
    """Process PDF files and extract text content"""
    
    def __init__(self):
        self.max_pages = config.MAX_PDF_PAGES
        self.chunk_size = config.PDF_TEXT_CHUNK_SIZE
    
    def extract_text(self, pdf_data: bytes, file_name: str = "document.pdf") -> PDFExtractedContent:
        """
        Extract text from PDF bytes
        """
        # Check if PDF libraries are available
        if not PDFPLUMBER_AVAILABLE and not PYPDF2_AVAILABLE:
            raise ImportError(
                "No PDF extraction library available. "
                "Please install pdfplumber: pip install pdfplumber "
                "or PyPDF2: pip install PyPDF2"
            )
        
        file_size_mb = len(pdf_data) / (1024 * 1024)
        
        # Try pdfplumber first (better text extraction)
        if PDFPLUMBER_AVAILABLE:
            try:
                return self._extract_with_pdfplumber(pdf_data, file_name, file_size_mb)
            except Exception as e:
                print(f"[PDF] pdfplumber failed: {e}")
                if not PYPDF2_AVAILABLE:
                    raise
        
        # Fallback to PyPDF2
        if PYPDF2_AVAILABLE:
            try:
                return self._extract_with_pypdf2(pdf_data, file_name, file_size_mb)
            except Exception as e:
                print(f"[PDF] PyPDF2 failed: {e}")
                raise
        
        raise ValueError("Failed to extract text from PDF with all available libraries.")
    
    def _extract_with_pdfplumber(self, pdf_data: bytes, file_name: str, file_size_mb: float) -> PDFExtractedContent:
        """Extract text using pdfplumber"""
        
        text_parts = []
        metadata = {}
        extracted_pages = 0
        total_chars = 0
        truncated = False
        
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            total_pages = len(pdf.pages)
            metadata = dict(pdf.metadata) if pdf.metadata else {}
            
            pages_to_process = min(total_pages, self.max_pages)
            
            for page_num in range(pages_to_process):
                try:
                    page = pdf.pages[page_num]
                    page_text = page.extract_text()
                    
                    if page_text:
                        page_text = self._clean_text(page_text)
                        text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                        total_chars += len(page_text)
                        extracted_pages += 1
                        
                        if total_chars >= self.chunk_size * self.max_pages:
                            truncated = True
                            break
                            
                except Exception as e:
                    print(f"[PDF] Error extracting page {page_num + 1}: {e}")
                    continue
        
        full_text = "\n\n".join(text_parts)
        
        if len(full_text) > self.chunk_size * self.max_pages:
            full_text = full_text[:self.chunk_size * self.max_pages] + "\n\n[... PDF content truncated ...]"
            truncated = True
        
        return PDFExtractedContent(
            text=full_text,
            total_pages=total_pages,
            extracted_pages=extracted_pages,
            metadata=metadata,
            truncated=truncated,
            file_name=file_name,
            file_size_mb=file_size_mb
        )
    
    def _extract_with_pypdf2(self, pdf_data: bytes, file_name: str, file_size_mb: float) -> PDFExtractedContent:
        """Extract text using PyPDF2"""
        
        reader = PdfReader(io.BytesIO(pdf_data))
        text_parts = []
        metadata = dict(reader.metadata) if reader.metadata else {}
        extracted_pages = 0
        total_chars = 0
        truncated = False
        
        total_pages = len(reader.pages)
        pages_to_process = min(total_pages, self.max_pages)
        
        for page_num in range(pages_to_process):
            try:
                page = reader.pages[page_num]
                page_text = page.extract_text()
                
                if page_text:
                    page_text = self._clean_text(page_text)
                    text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                    total_chars += len(page_text)
                    extracted_pages += 1
                    
                    if total_chars >= self.chunk_size * self.max_pages:
                        truncated = True
                        break
                        
            except Exception as e:
                print(f"[PDF] Error extracting page {page_num + 1}: {e}")
                continue
        
        full_text = "\n\n".join(text_parts)
        
        if len(full_text) > self.chunk_size * self.max_pages:
            full_text = full_text[:self.chunk_size * self.max_pages] + "\n\n[... PDF content truncated ...]"
            truncated = True
        
        return PDFExtractedContent(
            text=full_text,
            total_pages=total_pages,
            extracted_pages=extracted_pages,
            metadata=metadata,
            truncated=truncated,
            file_name=file_name,
            file_size_mb=file_size_mb
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)
    
    def get_file_info(self, pdf_data: bytes, file_name: str) -> Dict[str, Any]:
        """Get basic info about a PDF without full text extraction"""
        try:
            if PDFPLUMBER_AVAILABLE:
                with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
                    metadata = pdf.metadata or {}
                    return {
                        "valid": True,
                        "file_name": file_name,
                        "file_size_mb": round(len(pdf_data) / (1024 * 1024), 2),
                        "total_pages": len(pdf.pages),
                        "has_metadata": bool(pdf.metadata),
                        "title": metadata.get('title', 'Unknown'),
                        "author": metadata.get('author', 'Unknown')
                    }
            elif PYPDF2_AVAILABLE:
                reader = PdfReader(io.BytesIO(pdf_data))
                metadata = reader.metadata or {}
                return {
                    "valid": True,
                    "file_name": file_name,
                    "file_size_mb": round(len(pdf_data) / (1024 * 1024), 2),
                    "total_pages": len(reader.pages),
                    "has_metadata": bool(reader.metadata),
                    "title": metadata.get('/Title', 'Unknown'),
                    "author": metadata.get('/Author', 'Unknown')
                }
        except Exception as e:
            return {
                "valid": False,
                "file_name": file_name,
                "error": str(e),
                "file_size_mb": round(len(pdf_data) / (1024 * 1024), 2)
            }


# Create global instance
pdf_processor = PDFProcessor()