"""
Configuration settings for the Network Chatbot AI Backend
Loads settings from environment variables (.env file)
"""

import os
from dotenv import load_dotenv, find_dotenv
from typing import Optional, List

# ============================================================================
# Load .env file explicitly from backend folder
# ============================================================================

# Get the directory where this config.py file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, '.env')

print(f"[Config] Loading .env from: {ENV_PATH}")

# Load with override=True to ensure fresh values
load_dotenv(dotenv_path=ENV_PATH, override=True, verbose=True)

# ============================================================================

class Config:
    """Application configuration - All settings from environment variables"""
    
    # AI Service API Keys (from .env)
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    
    # AI Service Settings
    AI_TIMEOUT: int = int(os.getenv("AI_TIMEOUT", "300"))
    
    # Model Settings - Updated to use VLM models for image analysis
    # Qwen VL models for diagram analysis
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "qwen/qwen2.5-vl-72b-instruct")
    VLM_MODEL: str = os.getenv("VLM_MODEL", "qwen/qwen2.5-vl-72b-instruct")
    DEFAULT_AI_PROVIDER: str = os.getenv("DEFAULT_AI_PROVIDER", "openrouter")
    
    # Image upload settings
    MAX_IMAGE_SIZE_MB: int = int(os.getenv("MAX_IMAGE_SIZE_MB", "10"))
    SUPPORTED_IMAGE_FORMATS: list = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    
    # PDF Upload Settings - NEW
    MAX_PDF_SIZE_MB: int = int(os.getenv("MAX_PDF_SIZE_MB", "20"))
    SUPPORTED_PDF_FORMATS: List[str] = ["application/pdf"]
    MAX_PDF_PAGES: int = int(os.getenv("MAX_PDF_PAGES", "50"))
    PDF_TEXT_CHUNK_SIZE: int = int(os.getenv("PDF_TEXT_CHUNK_SIZE", "4000"))  # Characters per chunk
    
    # Supabase Configuration (from .env)
    SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: Optional[str] = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    USE_SUPABASE: bool = os.getenv("USE_SUPABASE", "true").lower() == "true"
    
    # Application Settings
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # API Endpoints
    OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    # Network Knowledge Base Context - Complete version with VLM support
    NETWORKING_CONTEXT = (
        "You are an expert Computer Networks university tutor. "
        "You help students understand networking concepts including TCP/IP, OSI model, "
        "routing protocols (OSPF, BGP, RIP), subnetting, DNS, HTTP/HTTPS, switching, "
        "and network security. Provide clear, educational explanations with examples. "
        "Be encouraging but accurate. If a student asks about non-networking topics, "
        "gently redirect them to networking concepts. Use analogies where helpful. "
        "When analyzing network diagrams, identify components, explain their functions, "
        "and help students understand the topology and data flow."
    )
    
    # VLM-specific context for image analysis
    VLM_CONTEXT = (
        "You are an expert Computer Networks tutor analyzing network diagrams and images. "
        "When shown a diagram: 1) Identify all network components (routers, switches, hosts, etc.) "
        "2) Explain the network topology and architecture "
        "3) Describe the data flow and communication patterns "
        "4) Point out any configuration details visible in the diagram "
        "5) Answer specific questions about what is shown. "
        "If the image contains a quiz question, read it carefully and provide a detailed explanation."
    )
    
    # PDF Analysis Context - NEW
    PDF_CONTEXT = (
        "You are an expert Computer Networks tutor analyzing PDF documents. "
        "When given PDF content: 1) Summarize the key networking concepts covered "
        "2) Identify important protocols, configurations, or diagrams mentioned "
        "3) Explain technical terms and acronyms found in the document "
        "4) Highlight any configuration examples or command outputs "
        "5) Answer specific questions about the content "
        "If the PDF contains questions or exercises, help solve them step by step."
    )


# Create global config instance
config = Config()

# Debug output
print(f"[Config] OPENROUTER_API_KEY loaded: {bool(config.OPENROUTER_API_KEY)}")
if config.OPENROUTER_API_KEY:
    print(f"[Config] Key starts with: {config.OPENROUTER_API_KEY[:15]}...")
print(f"[Config] VLM Model: {config.VLM_MODEL}")
print(f"[Config] PDF Support Enabled: Max {config.MAX_PDF_SIZE_MB}MB, {config.MAX_PDF_PAGES} pages max")


def check_api_keys() -> dict:
    """Check which API keys are configured"""
    openrouter_key = config.OPENROUTER_API_KEY
    
    is_valid = bool(
        openrouter_key 
        and len(openrouter_key) > 20
        and openrouter_key.startswith("sk-or")
    )
    
    return {"openrouter": is_valid}


def get_available_providers() -> list:
    """Get list of available AI providers"""
    keys = check_api_keys()
    available = []
    
    if keys["openrouter"]:
        available.append("openrouter")
    
    return available


def check_supabase_config() -> dict:
    """Check Supabase configuration status"""
    return {
        "enabled": config.USE_SUPABASE,
        "url_configured": bool(config.SUPABASE_URL),
        "key_configured": bool(config.SUPABASE_KEY),
        "fully_configured": bool(
            config.USE_SUPABASE and 
            config.SUPABASE_URL and 
            config.SUPABASE_KEY
        )
    }