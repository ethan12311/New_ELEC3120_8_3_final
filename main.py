"""
Network Chatbot AI Backend - FastAPI Application
Main entry point for the AI-powered chatbot backend
Now with VLM support for image/diagram analysis AND PDF support!
"""

from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from config import config, check_api_keys, get_available_providers, check_supabase_config
from ai_services import get_smart_response, clear_cache, get_cache_stats
from database import db  # NEW: Import Supabase database

# Create FastAPI application
app = FastAPI(
    title="Network Chatbot AI Backend",
    description="AI-powered backend for Computer Networks tutoring chatbot with VLM and PDF support",
    version="1.3.0"  # Updated version with PDF support
)

# Enable CORS - allows your Flask frontend to call this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage (fallback when Supabase is unavailable)
# Structure: {session_id: [{role, content, timestamp, has_image, has_pdf}, ...]}
conversation_sessions: Dict[str, List[Dict[str, Any]]] = {}


# ============================================================================
# Pydantic Models (Request/Response validation)
# ============================================================================

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str
    session_id: Optional[str] = None
    preferred_provider: Optional[str] = None  # 'deepseek', 'qwen', 'huggingface', 'auto'


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    session_id: str
    provider: str
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    available_providers: List[str]
    api_keys_configured: Dict[str, bool]
    database_status: Dict[str, Any]
    vlm_support: bool
    pdf_support: bool  # NEW: PDF support indicator


# ============================================================================
# Helper Functions
# ============================================================================

def get_or_create_session(session_id: Optional[str]) -> str:
    """Get existing session or create new one"""
    if not session_id:
        session_id = str(uuid.uuid4())
        
        # NEW: Create in Supabase if available
        if db.is_enabled():
            db.create_conversation(session_id, title="New Conversation")
        else:
            conversation_sessions[session_id] = []
    
    # Check if exists in Supabase or memory
    elif session_id:
        if db.is_enabled():
            conv = db.get_conversation(session_id)
            if not conv:
                db.create_conversation(session_id, title="New Conversation")
        elif session_id not in conversation_sessions:
            conversation_sessions[session_id] = []
    
    return session_id


def add_to_history(session_id: str, role: str, content: str, has_image: bool = False, has_pdf: bool = False):
    """Add a message to conversation history"""
    # NEW: Save to Supabase if available
    if db.is_enabled():
        db.add_message(session_id, role, content)
    else:
        # Fallback to in-memory
        if session_id not in conversation_sessions:
            conversation_sessions[session_id] = []
        
        conversation_sessions[session_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "has_image": has_image,
            "has_pdf": has_pdf
        })
        
        # Keep only last 10 messages to manage memory
        conversation_sessions[session_id] = conversation_sessions[session_id][-10:]


def get_conversation_history(session_id: str) -> List[Dict[str, str]]:
    """Get conversation history for a session (formatted for AI APIs)"""
    # NEW: Try Supabase first
    if db.is_enabled():
        return db.get_messages_for_ai(session_id, limit=10)
    
    # Fallback to in-memory
    if session_id not in conversation_sessions:
        return []
    
    # Return only role and content (without timestamp)
    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation_sessions[session_id]
    ]


def generate_title_from_message(message: str) -> str:
    """Generate a conversation title from the first user message"""
    # Take first 40 chars or first line
    title = message.strip().split('\n')[0][:40]
    if len(message) > 40:
        title += "..."
    return title


def format_message_for_frontend(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Format a message from Supabase/memory to frontend expected format"""
    return {
        "role": msg.get("role", "unknown"),
        "content": msg.get("content", ""),
        "timestamp": msg.get("created_at") or msg.get("timestamp", datetime.now().isoformat()),
        "provider": msg.get("provider", "ai"),  # Default provider if not stored
        "has_image": msg.get("has_image", False),
        "has_pdf": msg.get("has_pdf", False)  # NEW: PDF indicator
    }


def format_conversation_for_frontend(conv: Dict[str, Any]) -> Dict[str, Any]:
    """Format a conversation from Supabase to frontend expected format"""
    return {
        "session_id": conv.get("session_id"),
        "title": conv.get("title", "New Conversation"),
        "preview": conv.get("title", "New Conversation"),  # Frontend expects preview
        "created_at": conv.get("created_at"),
        "updated_at": conv.get("updated_at")
    }


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint - basic info"""
    return {
        "message": "Network Chatbot AI Backend with VLM & PDF Support",
        "version": "1.3.0",
        "docs": "/docs",
        "health": "/health",
        "features": ["text_chat", "image_analysis", "pdf_analysis", "diagram_questions"]
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    Returns status and configuration info
    """
    return HealthResponse(
        status="healthy",
        version="1.3.0",
        available_providers=get_available_providers(),
        api_keys_configured=check_api_keys(),
        database_status=check_supabase_config(),
        vlm_support=True,
        pdf_support=True  # NEW: PDF is now supported
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint (text-only)
    
    Receives a message from the user and returns an AI-generated response.
    Maintains conversation history per session.
    
    - **message**: The user's question or message
    - **session_id**: Optional session ID for conversation continuity
    - **preferred_provider**: Optional AI provider preference
    """
    try:
        # Get or create session
        session_id = get_or_create_session(request.session_id)
        
        # NEW: Update conversation title if it's the first message
        if db.is_enabled():
            messages = db.get_messages(session_id)
            if not messages:  # First message
                title = generate_title_from_message(request.message)
                db.update_conversation_title(session_id, title)
        
        # Add user message to history
        add_to_history(session_id, "user", request.message)
        
        # Get conversation history for context
        history = get_conversation_history(session_id)
        
        # Get AI response
        ai_result = await get_smart_response(
            message=request.message,
            conversation_history=history,
            preferred_provider=request.preferred_provider
        )
        
        # Add AI response to history
        add_to_history(session_id, "assistant", ai_result["response"])
        
        if config.DEBUG:
            storage = "Supabase" if db.is_enabled() else "Memory"
            print(f"[Chat] Session: {session_id[:8]}... | Provider: {ai_result['provider']} | Storage: {storage}")
        
        return ChatResponse(
            response=ai_result["response"],
            session_id=session_id,
            provider=ai_result["provider"],
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        if config.DEBUG:
            print(f"[Chat Error] {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/chat/with-image")
async def chat_with_image(
    message: str = Form(""),
    session_id: Optional[str] = Form(None),
    preferred_provider: Optional[str] = Form(None),
    image: UploadFile = File(...)
):
    """
    Chat endpoint with image upload for VLM analysis
    
    Receives a message and an image from the user and returns an AI-generated response.
    Uses Vision Language Model (Qwen-VL) to analyze diagrams and images.
    
    - **message**: The user's question about the image (optional)
    - **session_id**: Optional session ID for conversation continuity
    - **preferred_provider**: Optional AI provider preference
    - **image**: The image file to analyze (JPEG, PNG, GIF, WebP)
    """
    try:
        # Validate image
        if not image:
            raise HTTPException(status_code=400, detail="No image file provided")
        
        # Check file size
        image_content = await image.read()
        file_size_mb = len(image_content) / (1024 * 1024)
        
        if file_size_mb > config.MAX_IMAGE_SIZE_MB:
            raise HTTPException(
                status_code=413, 
                detail=f"Image too large. Max size: {config.MAX_IMAGE_SIZE_MB}MB, got: {file_size_mb:.1f}MB"
            )
        
        # Check MIME type
        if image.content_type not in config.SUPPORTED_IMAGE_FORMATS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported image format. Supported: {', '.join(config.SUPPORTED_IMAGE_FORMATS)}"
            )
        
        # Get or create session
        session_id = get_or_create_session(session_id)
        
        # Update conversation title
        if db.is_enabled():
            messages = db.get_messages(session_id)
            if not messages:
                title = "Image Analysis" if not message else generate_title_from_message(message)
                db.update_conversation_title(session_id, title)
        
        # Add user message to history (with image indicator)
        user_content = message if message else "[Image uploaded for analysis]"
        add_to_history(session_id, "user", user_content, has_image=True)
        
        # Get conversation history for context
        history = get_conversation_history(session_id)
        
        # Get AI response with image
        ai_result = await get_smart_response(
            message=message,
            conversation_history=history,
            preferred_provider=preferred_provider,
            image_data=image_content
        )
        
        # Add AI response to history
        add_to_history(session_id, "assistant", ai_result["response"])
        
        if config.DEBUG:
            storage = "Supabase" if db.is_enabled() else "Memory"
            print(f"[Chat-Image] Session: {session_id[:8]}... | Provider: {ai_result['provider']} | Size: {file_size_mb:.1f}MB | Storage: {storage}")
        
        return {
            "response": ai_result["response"],
            "session_id": session_id,
            "provider": ai_result["provider"],
            "timestamp": datetime.now().isoformat(),
            "image_analyzed": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if config.DEBUG:
            print(f"[Chat-Image Error] {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# NEW: PDF Upload Endpoint
@app.post("/chat/with-pdf")
async def chat_with_pdf(
    message: str = Form(""),
    session_id: Optional[str] = Form(None),
    preferred_provider: Optional[str] = Form(None),
    pdf: UploadFile = File(...)
):
    """
    Chat endpoint with PDF upload for document analysis
    """
    try:
        # Validate PDF
        if not pdf or not pdf.filename:
            raise HTTPException(status_code=400, detail="No PDF file provided")
        
        # Check file extension
        if not pdf.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=415,
                detail=f"File must be a PDF. Got: {pdf.filename}"
            )
        
        # Read PDF content
        pdf_content = await pdf.read()
        file_size_mb = len(pdf_content) / (1024 * 1024)
        
        # Check file size
        if file_size_mb > config.MAX_PDF_SIZE_MB:
            raise HTTPException(
                status_code=413, 
                detail=f"PDF too large. Max size: {config.MAX_PDF_SIZE_MB}MB, got: {file_size_mb:.1f}MB"
            )
        
        # Get or create session
        session_id = get_or_create_session(session_id)
        
        # Update conversation title
        if db.is_enabled():
            messages = db.get_messages(session_id)
            if not messages:
                title = f"PDF: {pdf.filename[:30]}..." if len(pdf.filename) > 30 else f"PDF: {pdf.filename}"
                db.update_conversation_title(session_id, title)
        
        # Add user message to history (with PDF indicator)
        user_content = message if message else f"[PDF uploaded: {pdf.filename}]"
        add_to_history(session_id, "user", user_content, has_pdf=True)
        
        # Get conversation history for context
        history = get_conversation_history(session_id)
        
        # Get AI response with PDF
        ai_result = await get_smart_response(
            message=message,
            conversation_history=history,
            preferred_provider=preferred_provider,
            pdf_data=pdf_content,
            pdf_filename=pdf.filename
        )
        
        # Check if AI processing failed
        if not ai_result.get("success", False):
            error_msg = ai_result.get("response", "Unknown error processing PDF")
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Add AI response to history
        add_to_history(session_id, "assistant", ai_result["response"])
        
        if config.DEBUG:
            storage = "Supabase" if db.is_enabled() else "Memory"
            pdf_info = ai_result.get("pdf_info", {})
            print(f"[Chat-PDF] Session: {session_id[:8]}... | Provider: {ai_result['provider']} | "
                  f"File: {pdf.filename} | Pages: {pdf_info.get('total_pages', '?')} | Storage: {storage}")
        
        # Prepare response
        response_data = {
            "response": ai_result["response"],
            "session_id": session_id,
            "provider": ai_result["provider"],
            "timestamp": datetime.now().isoformat(),
            "pdf_analyzed": True,
            "feature": "pdf_analysis"
        }
        
        # Add PDF info if available
        if "pdf_info" in ai_result:
            response_data["pdf_info"] = ai_result["pdf_info"]
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        if config.DEBUG:
            print(f"[Chat-PDF Error] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# NEW: PDF Info Endpoint (for quick validation without full analysis)
# NEW: PDF Info Endpoint (for quick validation without full analysis)
@app.post("/pdf/validate")
async def validate_pdf(
    pdf: UploadFile = File(...)
):
    """
    Validate a PDF file and return basic info without full AI analysis
    
    - **pdf**: The PDF file to validate
    
    Returns: File size, page count, and metadata if available
    """
    try:
        if not pdf or not pdf.filename:
            return {
                "valid": False,
                "error": "No PDF file provided",
                "file_name": "unknown",
                "file_size_mb": 0,
                "total_pages": 0,
                "max_pages_limit": config.MAX_PDF_PAGES,
                "max_size_limit_mb": config.MAX_PDF_SIZE_MB
            }
        
        if not pdf.filename.lower().endswith('.pdf'):
            return {
                "valid": False,
                "error": "File must be a PDF",
                "file_name": pdf.filename,
                "file_size_mb": 0,
                "total_pages": 0,
                "max_pages_limit": config.MAX_PDF_PAGES,
                "max_size_limit_mb": config.MAX_PDF_SIZE_MB
            }
        
        # Read PDF content
        pdf_content = await pdf.read()
        file_size_mb = len(pdf_content) / (1024 * 1024)
        
        if file_size_mb > config.MAX_PDF_SIZE_MB:
            return {
                "valid": False,
                "error": f"PDF too large. Max size: {config.MAX_PDF_SIZE_MB}MB, got: {file_size_mb:.1f}MB",
                "file_name": pdf.filename,
                "file_size_mb": round(file_size_mb, 2),
                "total_pages": 0,
                "max_pages_limit": config.MAX_PDF_PAGES,
                "max_size_limit_mb": config.MAX_PDF_SIZE_MB
            }
        
        # Get basic PDF info
        from pdf_processor import pdf_processor
        info = pdf_processor.get_file_info(pdf_content, pdf.filename)
        
        # Ensure we always return a valid response with all required fields
        if info is None:
            info = {
                "valid": False,
                "error": "Could not process PDF",
                "file_name": pdf.filename,
                "file_size_mb": round(file_size_mb, 2),
                "total_pages": 0,
                "has_metadata": False,
                "title": "Unknown",
                "author": "Unknown"
            }
        
        # Add limits to response
        info["max_pages_limit"] = config.MAX_PDF_PAGES
        info["max_size_limit_mb"] = config.MAX_PDF_SIZE_MB
        
        return info
        
    except Exception as e:
        # Return a valid JSON response even on error
        return {
            "valid": False,
            "error": str(e),
            "file_name": pdf.filename if pdf and pdf.filename else "unknown",
            "file_size_mb": 0,
            "total_pages": 0,
            "has_metadata": False,
            "title": "Unknown",
            "author": "Unknown",
            "max_pages_limit": config.MAX_PDF_PAGES,
            "max_size_limit_mb": config.MAX_PDF_SIZE_MB
        }

@app.post("/chat/simple")
async def chat_simple(message: str, session_id: Optional[str] = None):
    """
    Simplified chat endpoint (for easy testing)
    
    Usage: POST /chat/simple?message=Hello&session_id=abc123
    """
    request = ChatRequest(message=message, session_id=session_id)
    return await chat(request)


@app.get("/session/{session_id}")
async def get_session_history(session_id: str):
    """
    Get conversation history for a session
    Returns messages in frontend-compatible format
    """
    # NEW: Try Supabase first, fallback to memory
    if db.is_enabled():
        messages = db.get_messages(session_id)
        if messages:
            # Format messages for frontend compatibility
            formatted_messages = [format_message_for_frontend(msg) for msg in messages]
            return {
                "session_id": session_id,
                "messages": formatted_messages,
                "storage": "supabase"
            }
    
    # Fallback to in-memory
    if session_id not in conversation_sessions:
        return {"session_id": session_id, "messages": [], "storage": "memory"}
    
    # Format in-memory messages
    formatted_messages = [
        format_message_for_frontend(msg) 
        for msg in conversation_sessions[session_id]
    ]
    
    return {
        "session_id": session_id,
        "messages": formatted_messages,
        "storage": "memory"
    }


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear conversation history for a session
    """
    # NEW: Delete from Supabase if available
    if db.is_enabled():
        success = db.delete_conversation(session_id)
        if success:
            return {"message": f"Session {session_id} deleted from database"}
    
    # Fallback to in-memory
    if session_id in conversation_sessions:
        del conversation_sessions[session_id]
        return {"message": f"Session {session_id} cleared from memory"}
    
    return {"message": f"Session {session_id} not found"}


# NEW: List all conversations endpoint
@app.get("/conversations")
async def list_conversations():
    """
    List all conversations
    Returns conversations in frontend-compatible format with 'preview' field
    """
    if db.is_enabled():
        conversations = db.get_all_conversations()
        # Format conversations for frontend compatibility
        formatted_conversations = [
            format_conversation_for_frontend(conv) 
            for conv in conversations
        ]
        return {
            "conversations": formatted_conversations,
            "storage": "supabase",
            "count": len(formatted_conversations)
        }
    
    # Fallback to in-memory
    conversations = []
    for sid, messages in conversation_sessions.items():
        preview = "No messages"
        if messages:
            first_user_msg = next((m for m in messages if m["role"] == "user"), None)
            if first_user_msg:
                preview = first_user_msg["content"][:50] + "..."
        
        conversations.append({
            "session_id": sid,
            "title": preview,
            "preview": preview,  # Frontend expects preview field
            "message_count": len(messages)
        })
    
    return {
        "conversations": conversations,
        "storage": "memory",
        "count": len(conversations)
    }


@app.get("/providers")
async def list_providers():
    """
    List available AI providers and their status
    """
    return {
        "available": get_available_providers(),
        "configured": check_api_keys(),
        "default": config.DEFAULT_AI_PROVIDER,
        "vlm_model": config.VLM_MODEL,
        "vlm_support": True,
        "pdf_support": True,
        "pdf_max_size_mb": config.MAX_PDF_SIZE_MB,
        "pdf_max_pages": config.MAX_PDF_PAGES
    }


@app.post("/cache/clear")
async def clear_response_cache():
    """
    Clear the response cache
    """
    clear_cache()
    return {"message": "Cache cleared successfully"}


@app.get("/cache/stats")
async def cache_statistics():
    """
    Get cache statistics
    """
    return get_cache_stats()


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle any unhandled exceptions"""
    if config.DEBUG:
        print(f"[Global Error] {type(exc).__name__}: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if config.DEBUG else "An unexpected error occurred"
        }
    )


# ============================================================================
# Startup Event
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on server startup"""
    print("=" * 60)
    print("  Network Chatbot AI Backend Started")
    print("  VLM & PDF Support Enabled!")
    print("=" * 60)
    print(f"  API Documentation: http://localhost:8000/docs")
    print(f"  Health Check: http://localhost:8000/health")
    print("-" * 60)
    
    # Check API keys
    keys = check_api_keys()
    print("  API Keys Configured:")
    for provider, configured in keys.items():
        status = "✓" if configured else "✗"
        print(f"    {status} {provider.capitalize()}")
    
    # NEW: Check Supabase status
    print("-" * 60)
    db_status = check_supabase_config()
    print("  Database Configuration:")
    print(f"    Enabled: {'Yes' if db_status['enabled'] else 'No'}")
    print(f"    URL: {'✓' if db_status['url_configured'] else '✗'}")
    print(f"    Key: {'✓' if db_status['key_configured'] else '✗'}")
    print(f"    Status: {'Connected' if db.is_enabled() else 'Not Connected'}")
    
    print("-" * 60)
    print(f"  Available Providers: {get_available_providers()}")
    print(f"  VLM Model: {config.VLM_MODEL}")
    print(f"  PDF Support: Max {config.MAX_PDF_SIZE_MB}MB, {config.MAX_PDF_PAGES} pages")
    print(f"  Cache Enabled: {config.ENABLE_CACHE}")
    print(f"  Debug Mode: {config.DEBUG}")
    print("=" * 60)


# ============================================================================
# Run Server (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "=" * 60)
    print("  Starting Network Chatbot AI Backend")
    print("  With VLM & PDF Support")
    print("=" * 60)
    print("\n  To run with auto-reload:")
    print("  uvicorn main:app --reload --port 8000")
    print("\n  Or run this file directly:")
    print("  python main.py")
    print("=" * 60 + "\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )