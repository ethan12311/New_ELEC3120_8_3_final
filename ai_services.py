
"""
AI Service Integration Module
Handles calls to OpenRouter API (supports Qwen, DeepSeek, etc.)
Now supports PDF analysis!
"""

import httpx
import asyncio
import hashlib
import time
import base64
from typing import Optional, List, Dict, Any

from config import config, get_available_providers

# Import PDF processor - make sure this is at module level
try:
    from pdf_processor import pdf_processor, PDFExtractedContent
    PDF_PROCESSOR_AVAILABLE = True
except ImportError as e:
    print(f"[AI Services] PDF processor not available: {e}")
    PDF_PROCESSOR_AVAILABLE = False
    pdf_processor = None
    PDFExtractedContent = None

# Simple in-memory cache
_response_cache: Dict[str, Dict[str, Any]] = {}


def _get_cache_key(message: str) -> str:
    """Generate a cache key from the message"""
    return hashlib.md5(message.lower().strip().encode()).hexdigest()


def _get_cached_response(message: str) -> Optional[str]:
    """Get cached response if available and not expired"""
    if not config.ENABLE_CACHE:
        return None
    
    cache_key = _get_cache_key(message)
    cached = _response_cache.get(cache_key)
    
    if cached:
        if time.time() - cached["timestamp"] < config.CACHE_TTL:
            if config.DEBUG:
                print(f"[CACHE HIT] Using cached response for: {message[:50]}...")
            return cached["response"]
        else:
            del _response_cache[cache_key]
    
    return None


def _cache_response(message: str, response: str):
    """Cache a response"""
    if not config.ENABLE_CACHE:
        return
    
    cache_key = _get_cache_key(message)
    _response_cache[cache_key] = {
        "response": response,
        "timestamp": time.time()
    }
    
    # Limit cache size to prevent memory issues
    if len(_response_cache) > 100:
        oldest_key = min(_response_cache.keys(), key=lambda k: _response_cache[k]["timestamp"])
        del _response_cache[oldest_key]


async def get_openrouter_response(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
    image_data: Optional[bytes] = None,
    pdf_content: Optional[Any] = None  # PDFExtractedContent or None
) -> str:
    """
    Get response from OpenRouter API (Qwen, DeepSeek, etc.)
    Supports multimodal input with images and PDF analysis.
    """
    if not config.OPENROUTER_API_KEY:
        raise ValueError("OpenRouter API key not configured")
    
    # Check cache only for text-only messages (no images or PDFs)
    if not image_data and not pdf_content:
        cached = _get_cached_response(message)
        if cached:
            return cached
    
    # Determine which model and context to use
    if image_data:
        model = config.VLM_MODEL  # Use vision model for images
        system_content = config.VLM_CONTEXT
        print(f"[VLM] Using model: {model} for image analysis")
    elif pdf_content:
        model = config.OPENROUTER_MODEL  # Use standard model for PDFs
        system_content = config.PDF_CONTEXT
        print(f"[PDF] Using model: {model} for PDF analysis")
    else:
        model = config.OPENROUTER_MODEL
        system_content = config.NETWORKING_CONTEXT
    
    # Build messages array with system context
    messages = [{"role": "system", "content": system_content}]
    
    # Add conversation history (last 5 messages for context)
    if conversation_history:
        messages.extend(conversation_history[-5:])
    
    # Build user message content
    if image_data:
        # Convert image to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Determine image MIME type (default to jpeg)
        mime_type = "image/jpeg"
        
        # Multimodal message format for VLM
        user_content = [
            {
                "type": "text",
                "text": message if message else "Analyze this network diagram."
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}"
                }
            }
        ]
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        if config.DEBUG:
            print(f"[VLM] Sending image: {len(image_data)} bytes, message: {message[:50] if message else 'None'}...")
    
    elif pdf_content:
        # PDF analysis - create comprehensive prompt
        # Build metadata info
        metadata_info = []
        if pdf_content.metadata.get('title'):
            metadata_info.append(f"Title: {pdf_content.metadata['title']}")
        if pdf_content.metadata.get('author'):
            metadata_info.append(f"Author: {pdf_content.metadata['author']}")
        
        metadata_str = "\n".join(metadata_info) if metadata_info else "No metadata available"
        
        pdf_prompt = f"""I have uploaded a PDF document with the following information:

File: {pdf_content.file_name}
Size: {pdf_content.file_size_mb:.2f} MB
Total Pages: {pdf_content.total_pages}
Extracted Pages: {pdf_content.extracted_pages}
{metadata_str}

Here is the content of the PDF:

--- BEGIN PDF CONTENT ---

{pdf_content.text}

--- END PDF CONTENT ---
"""
        
        if pdf_content.truncated:
            pdf_prompt += "\n\nNote: The PDF content was truncated due to length limits.\n"
        
        if message:
            pdf_prompt += f"\n\nBased on this PDF content, please answer the following question:\n{message}"
        else:
            pdf_prompt += "\n\nPlease provide a comprehensive summary of this PDF document, highlighting key networking concepts, protocols mentioned, and any important technical details."
        
        messages.append({
            "role": "user",
            "content": pdf_prompt
        })
        
        if config.DEBUG:
            print(f"[PDF] Analyzing PDF: {pdf_content.file_name}, {pdf_content.total_pages} pages, {pdf_content.file_size_mb:.2f}MB")
    
    else:
        # Text-only message
        messages.append({
            "role": "user",
            "content": message
        })
    
    async with httpx.AsyncClient(timeout=config.AI_TIMEOUT) as client:
        try:
            response = await client.post(
                config.OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:5000",
                    "X-Title": "Network Chatbot AI"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 2500,  # Increased for detailed PDF analysis
                    "temperature": 0.7
                }
            )
            response.raise_for_status()
            
            data = response.json()
            ai_response = data["choices"][0]["message"]["content"]
            
            # Cache only text-only responses
            if not image_data and not pdf_content:
                _cache_response(message, ai_response)
            
            return ai_response
            
        except httpx.TimeoutException:
            return "I'm sorry, the AI service is taking too long to respond. Please try again."
        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = f" - {error_data.get('error', {}).get('message', '')}"
            except:
                pass
            
            if e.response.status_code == 401:
                return "Error: Invalid OpenRouter API key. Please check your configuration."
            elif e.response.status_code == 429:
                return "Error: Rate limit exceeded. Please wait a moment and try again."
            elif e.response.status_code == 400:
                return f"Error: Bad request{error_detail}. The file might be too large or in an unsupported format."
            else:
                return f"Error calling OpenRouter API: {e.response.status_code}{error_detail}"
        except Exception as e:
            if config.DEBUG:
                print(f"[OpenRouter Error] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return "I'm sorry, I encountered an error. Please try again."


async def get_smart_response(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
    preferred_provider: Optional[str] = None,
    image_data: Optional[bytes] = None,
    pdf_data: Optional[bytes] = None,
    pdf_filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get AI response from OpenRouter with fallback handling
    Now supports image analysis via VLM and PDF analysis!
    """
    available = get_available_providers()
    
    if not available:
        return {
            "response": "No AI providers are configured. Please add API keys to your .env file.",
            "provider": "none",
            "success": False
        }
    
    # Check if PDF processor is available
    if pdf_data and not PDF_PROCESSOR_AVAILABLE:
        return {
            "response": "PDF processing is not available. Please install pdfplumber: pip install pdfplumber",
            "provider": "none",
            "success": False
        }
    
    # Process PDF if provided
    pdf_content = None
    if pdf_data and PDF_PROCESSOR_AVAILABLE:
        try:
            pdf_content = pdf_processor.extract_text(pdf_data, pdf_filename or "document.pdf")
            
            if pdf_content is None:
                return {
                    "response": "Error: Could not extract text from PDF. The file may be corrupted, password protected, or contain only images.",
                    "provider": "none",
                    "success": False
                }
                
        except Exception as e:
            return {
                "response": f"Error processing PDF: {str(e)}",
                "provider": "none",
                "success": False
            }
    
    try:
        provider_name = "openrouter"

        # Determine model based on input type
        if image_data:
            model_used = config.VLM_MODEL
            feature = "image_analysis"
        elif pdf_content:
            model_used = config.OPENROUTER_MODEL
            feature = "pdf_analysis"
        else:
            model_used = config.OPENROUTER_MODEL
            feature = "text_chat"

        if config.DEBUG:
            if image_data:
                print(f"[AI Service] Analyzing image with VLM: {model_used}...")
            elif pdf_content:
                print(f"[AI Service] Analyzing PDF with AI: {pdf_content.file_name} ({pdf_content.total_pages} pages)...")
            else:
                print(f"[AI Service] Text query with: {model_used}...")

        response = await get_openrouter_response(
            message=message,
            conversation_history=conversation_history,
            image_data=image_data,
            pdf_content=pdf_content
        )

        # Check if response is an error message
        if response.startswith("Error:") or response.startswith("I'm sorry, I encountered"):
            return {
                "response": response,
                "provider": provider_name,
                "success": False
            }

        result = {
            "response": response,
            "provider": f"{provider_name}-{model_used.split('/')[-1]}",
            "success": True,
            "feature": feature
        }

        # Add PDF metadata if applicable
        if pdf_content:
            result["pdf_info"] = {
                "file_name": pdf_content.file_name,
                "total_pages": pdf_content.total_pages,
                "extracted_pages": pdf_content.extracted_pages,
                "file_size_mb": round(pdf_content.file_size_mb, 2),
                "truncated": pdf_content.truncated
            }

        return result

    except Exception as e:
        if config.DEBUG:
            print(f"[AI Service] OpenRouter failed: {e}")

        return {
            "response": f"OpenRouter API error: {str(e)}",
            "provider": "none",
            "success": False
        }


def clear_cache():
    """Clear the response cache"""
    global _response_cache
    _response_cache = {}
    if config.DEBUG:
        print("[CACHE] Cleared all cached responses")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    return {
        "entries": len(_response_cache),
        "enabled": config.ENABLE_CACHE,
        "ttl_seconds": config.CACHE_TTL
    }
