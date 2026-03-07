"""
Supabase Database Integration for Network Chatbot
Handles persistent storage of conversations and messages
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

try:
    from postgrest import SyncPostgrestClient
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("Warning: postgrest not installed. Run: pip install postgrest-py")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, '.env')
load_dotenv(ENV_PATH, override=True)


class SupabaseDB:
    """Supabase database manager using PostgREST directly"""
    
    def __init__(self):
        self.client = None
        self.enabled = False
        
        if not SUPABASE_AVAILABLE:
            print("[Supabase] postgrest not available")
            return
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        
        print(f"[Supabase] URL found: {bool(supabase_url)}")
        print(f"[Supabase] Key found: {bool(supabase_key)}")
        
        if not supabase_url or not supabase_key:
            print("[Supabase] Credentials not found")
            return
        
        try:
            rest_url = f"{supabase_url}/rest/v1"
            self.client = SyncPostgrestClient(rest_url, headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}"
            })
            self.enabled = True
            print(f"[Supabase] Connected via PostgREST to {supabase_url[:30]}...")
        except Exception as e:
            print(f"[Supabase] Connection failed: {e}")
            import traceback
            traceback.print_exc()
    
    def is_enabled(self) -> bool:
        return self.enabled and self.client is not None
    
    def create_conversation(self, session_id: str, title: str = "New Conversation") -> bool:
        if not self.is_enabled():
            print("[Supabase] Cannot create conversation - not enabled")
            return False
        
        try:
            data = {
                "session_id": session_id,
                "title": title,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            self.client.table("conversations").insert(data).execute()
            print(f"[Supabase] Created conversation: {session_id[:8]}...")
            return True
        except Exception as e:
            print(f"[Supabase] Error creating conversation: {e}")
            return False
    
    def get_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation by session_id"""
        if not self.is_enabled():
            return None
        
        try:
            result = self.client.table("conversations")\
                .select("*")\
                .eq("session_id", session_id)\
                .execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
            
        except Exception as e:
            print(f"[Supabase] Error getting conversation: {e}")
            return None
    
    def get_all_conversations(self) -> List[Dict[str, Any]]:
        """
        Get all conversations ordered by updated_at desc
        Returns list of conversation dicts with session_id, title, created_at, updated_at
        """
        if not self.is_enabled():
            print("[Supabase] Cannot get conversations - not enabled")
            return []
        
        try:
            result = self.client.table("conversations")\
                .select("session_id,title,created_at,updated_at")\
                .order("updated_at", desc=True)\
                .execute()
            
            conversations = result.data or []
            print(f"[Supabase] Retrieved {len(conversations)} conversations")
            return conversations
            
        except Exception as e:
            print(f"[Supabase] Error getting conversations: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def update_conversation_title(self, session_id: str, title: str) -> bool:
        """Update conversation title"""
        if not self.is_enabled():
            return False
        
        try:
            self.client.table("conversations")\
                .update({"title": title, "updated_at": datetime.now().isoformat()})\
                .eq("session_id", session_id)\
                .execute()
            print(f"[Supabase] Updated title for {session_id[:8]}...")
            return True
        except Exception as e:
            print(f"[Supabase] Error updating title: {e}")
            return False
    
    def add_message(self, session_id: str, role: str, content: str) -> bool:
        """Add a message to the conversation"""
        if not self.is_enabled():
            print(f"[Supabase] Cannot add message - not enabled")
            return False
        
        try:
            data = {
                "session_id": session_id,
                "role": role,
                "content": content,
                "created_at": datetime.now().isoformat()
            }
            self.client.table("messages").insert(data).execute()
            
            # Update conversation timestamp
            self.client.table("conversations").update({
                "updated_at": datetime.now().isoformat()
            }).eq("session_id", session_id).execute()
            
            print(f"[Supabase] Added {role} message: {content[:30]}...")
            return True
        except Exception as e:
            print(f"[Supabase] Error adding message: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages for a conversation ordered by created_at asc
        Returns list of message dicts with role, content, created_at
        """
        if not self.is_enabled():
            return []
        
        try:
            result = self.client.table("messages")\
                .select("role,content,created_at")\
                .eq("session_id", session_id)\
                .order("created_at")\
                .execute()
            
            messages = result.data or []
            print(f"[Supabase] Retrieved {len(messages)} messages for {session_id[:8]}...")
            return messages
            
        except Exception as e:
            print(f"[Supabase] Error getting messages: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_messages_for_ai(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get messages formatted for AI context (only role and content)"""
        messages = self.get_messages(session_id)
        
        # Return only last 'limit' messages, formatted for AI
        formatted = []
        for msg in messages[-limit:]:
            formatted.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return formatted
    
    def delete_conversation(self, session_id: str) -> bool:
        """Delete a conversation and all its messages"""
        if not self.is_enabled():
            return False
        
        try:
            # Delete messages first (foreign key constraint)
            self.client.table("messages").delete().eq("session_id", session_id).execute()
            # Delete conversation
            self.client.table("conversations").delete().eq("session_id", session_id).execute()
            print(f"[Supabase] Deleted conversation {session_id[:8]}...")
            return True
        except Exception as e:
            print(f"[Supabase] Error deleting: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def clear_messages(self, session_id: str) -> bool:
        """Clear all messages from a conversation (keep conversation)"""
        if not self.is_enabled():
            return False
        
        try:
            self.client.table("messages")\
                .delete()\
                .eq("session_id", session_id)\
                .execute()
            print(f"[Supabase] Cleared messages for {session_id[:8]}...")
            return True
        except Exception as e:
            print(f"[Supabase] Error clearing messages: {e}")
            return False


# Create global instance
db = SupabaseDB()