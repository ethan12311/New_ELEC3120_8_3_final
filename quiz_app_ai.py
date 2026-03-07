"""
ELEC3120 Network Learning Hub - AI Enhanced Version with VLM & PDF Support
Students can now upload diagram images AND PDF documents for analysis!
"""

from flask import Flask, render_template_string, request, jsonify
import json
import re
import requests
import uuid
from datetime import datetime

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

AI_BACKEND_URL = "http://localhost:8000"
USE_AI_BACKEND = True

# ============================================================
# Knowledge Base & Assistant
# ============================================================

knowledge_base = {
    "protocols": {
        "tcp": "TCP is a connection-oriented protocol providing reliable transmission, flow control, and congestion control. Uses three-way handshake.",
        "udp": "UDP is a connectionless protocol providing best-effort transmission. Faster but unreliable. Used for real-time applications.",
        "http": "HTTP is an application layer protocol for transmitting hypertext. HTTP/1.1 supports persistent connections, HTTP/2 supports multiplexing.",
        "https": "HTTPS is the secure version of HTTP using TLS/SSL encryption. Default port 443.",
        "dns": "DNS translates domain names to IP addresses. Uses UDP port 53, large responses use TCP."
    }
}

class NetworkAssistant:
    def __init__(self):
        self.qa_patterns = {
            r"tcp.*udp.*difference": "TCP is connection-oriented, reliable, with flow and congestion control. UDP is connectionless, unreliable, but has lower latency. TCP is used for web browsing, email; UDP for video streaming, DNS queries.",
            r"http.*1\.1.*2.*difference": "HTTP/1.1 uses persistent connections but has head-of-line blocking. HTTP/2 uses binary framing, multiplexing, header compression, and server push for better performance.",
            r"dns.*work": "DNS query process: 1. Local cache 2. Recursive resolver 3. Root server 4. TLD server 5. Authoritative server. Uses UDP port 53, large responses switch to TCP.",
            r"osi.*model": "OSI model has 7 layers: Physical, Data Link, Network, Transport, Session, Presentation, Application. Each layer has specific functions and protocols.",
        }
    
    def find_answer(self, question: str) -> str:
        question_lower = question.lower()
        for pattern, answer in self.qa_patterns.items():
            if re.search(pattern, question_lower, re.IGNORECASE):
                return answer
        for protocol, description in knowledge_base["protocols"].items():
            if protocol in question_lower:
                return f"{protocol.upper()}: {description}"
        return None

assistant = NetworkAssistant()

# ============================================================
# Quiz Question Bank (Simplified)
# ============================================================

QUIZ_QUESTIONS = {
    "tcp-basics": [
        {
            "id": "q-tcp-basics-1",
            "title": "Question 1: TCP Reliability",
            "question": "Which mechanism handles out-of-order packets in Selective Repeat ARQ?",
            "type": "multiple_choice",
            "options": ["a) Discard them", "b) Store in buffer", "c) Acknowledge last"],
            "answer": "b",
            "explanation": "Selective Repeat stores out-of-order packets in a receiver buffer."
        }
    ],
    "real-life-scenarios": [
        {
            "id": "q-scenario-1",
            "title": "Scenario: Home Wi-Fi",
            "question": "Video freezes while roommate downloads game. What's the solution?",
            "type": "multiple_choice",
            "options": [
                "a) Restart router",
                "b) Implement QoS",
                "c) Change DNS",
                "d) Use wired connection"
            ],
            "answer": "b",
            "explanation": "QoS prioritizes time-sensitive traffic like video calls."
        }
    ]
}

# ============================================================
# Flask Routes
# ============================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/ai_status')
def ai_status():
    try:
        response = requests.get(f"{AI_BACKEND_URL}/health", timeout=2)
        data = response.json()
        return jsonify({
            'available': response.status_code == 200,
            'vlm': data.get('vlm_support', False),
            'pdf': data.get('pdf_support', False)
        })
    except:
        return jsonify({'available': False, 'vlm': False, 'pdf': False})

@app.route('/quiz/questions', methods=['GET'])
def get_quiz_questions():
    return jsonify(QUIZ_QUESTIONS)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '')
        session_id = data.get('session_id')
        
        # Check for local response first
        local_response = assistant.find_answer(message)
        if local_response:
            return jsonify({
                'response': local_response,
                'session_id': session_id or str(uuid.uuid4()),
                'provider': 'local'
            })
        
        # Use AI backend
        try:
            response = requests.post(
                f"{AI_BACKEND_URL}/chat",
                json={'message': message, 'session_id': session_id},
                timeout=30
            )
            if response.status_code == 200:
                return jsonify(response.json())
        except:
            pass
        
        return jsonify({
            'response': "I'm a network assistant. Ask me about networking!",
            'session_id': session_id or str(uuid.uuid4()),
            'provider': 'local'
        })
        
    except Exception as e:
        return jsonify({
            'response': f"Error: {str(e)}",
            'session_id': data.get('session_id', str(uuid.uuid4())),
            'provider': 'error'
        })


@app.route('/chat/with-image', methods=['POST'])
def chat_with_image():
    """Proxy endpoint for image upload to FastAPI backend"""
    try:
        message = request.form.get('message', '')
        session_id = request.form.get('session_id')
        
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image']
        
        # Forward to FastAPI backend
        files = {'image': (image_file.filename, image_file.stream, image_file.content_type)}
        data = {'message': message, 'session_id': session_id}
        
        response = requests.post(
            f"{AI_BACKEND_URL}/chat/with-image",
            files=files,
            data=data,
            timeout=60
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to analyze image', 'details': response.text}), response.status_code
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# NEW: PDF Upload Endpoint
@app.route('/chat/with-pdf', methods=['POST'])
def chat_with_pdf():
    """Proxy endpoint for PDF upload to FastAPI backend"""
    try:
        message = request.form.get('message', '')
        session_id = request.form.get('session_id')
        
        if 'pdf' not in request.files:
            return jsonify({'error': 'No PDF file provided'}), 400
        
        pdf_file = request.files['pdf']
        
        # Validate PDF extension
        if not pdf_file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'File must be a PDF'}), 400
        
        # Forward to FastAPI backend
        files = {'pdf': (pdf_file.filename, pdf_file.stream, pdf_file.content_type)}
        data = {'message': message, 'session_id': session_id}
        
        response = requests.post(
            f"{AI_BACKEND_URL}/chat/with-pdf",
            files=files,
            data=data,
            timeout=120  # Longer timeout for PDF processing
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to analyze PDF', 'details': response.text}), response.status_code
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# NEW: PDF Validation Endpoint
@app.route('/pdf/validate', methods=['POST'])
def validate_pdf():
    """Proxy endpoint for PDF validation"""
    try:
        if 'pdf' not in request.files:
            return jsonify({'error': 'No PDF file provided'}), 400
        
        pdf_file = request.files['pdf']
        
        # Forward to FastAPI backend
        files = {'pdf': (pdf_file.filename, pdf_file.stream, pdf_file.content_type)}
        
        response = requests.post(
            f"{AI_BACKEND_URL}/pdf/validate",
            files=files,
            timeout=10
        )
        
        return jsonify(response.json()), response.status_code
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/conversations', methods=['GET'])
def list_conversations():
    """Get all conversations from FastAPI backend"""
    try:
        response = requests.get(f"{AI_BACKEND_URL}/conversations", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Ensure consistent format
            conversations = data.get('conversations', [])
            # Add preview field if missing (for backwards compatibility)
            for conv in conversations:
                if 'preview' not in conv and 'title' in conv:
                    conv['preview'] = conv['title']
            return jsonify(data)
    except Exception as e:
        print(f"[Flask] Error fetching conversations: {e}")
        import traceback
        traceback.print_exc()
    
    return jsonify({'conversations': [], 'storage': 'error', 'count': 0})

@app.route('/conversation/new', methods=['POST'])
def new_conversation():
    """Create a new conversation"""
    session_id = str(uuid.uuid4())
    return jsonify({'session_id': session_id})

@app.route('/conversation/<session_id>', methods=['GET'])
def get_conversation(session_id):
    """Get messages for a specific conversation"""
    try:
        # Try to get from FastAPI backend
        response = requests.get(f"{AI_BACKEND_URL}/session/{session_id}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"[Flask] Got conversation data: {data}")  # Debug log
            
            # Ensure we have the right structure
            messages = data.get('messages', [])
            
            # Format messages properly for frontend
            formatted_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    # Map Supabase fields to frontend expected fields
                    formatted_msg = {
                        'role': msg.get('role', 'unknown'),
                        'content': msg.get('content', ''),
                        'provider': msg.get('provider', 'ai'),  # Default to 'ai'
                        'timestamp': msg.get('created_at') or msg.get('timestamp', datetime.now().isoformat()),
                        'has_image': msg.get('has_image', False),
                        'has_pdf': msg.get('has_pdf', False)  # NEW: PDF indicator
                    }
                    formatted_messages.append(formatted_msg)
            
            return jsonify({
                'session_id': session_id,
                'messages': formatted_messages,
                'storage': data.get('storage', 'unknown')
            })
        else:
            print(f"[Flask] Backend returned status {response.status_code}")
            
    except Exception as e:
        print(f"[Flask] Error fetching conversation {session_id}: {e}")
        import traceback
        traceback.print_exc()
    
    # Return empty if not found
    return jsonify({
        'session_id': session_id,
        'messages': [],
        'storage': 'not_found'
    })

@app.route('/conversation/<session_id>', methods=['DELETE'])
def delete_conversation_route(session_id):
    """Delete a conversation"""
    try:
        response = requests.delete(f"{AI_BACKEND_URL}/session/{session_id}", timeout=5)
        if response.status_code == 200:
            return jsonify({'message': 'Deleted'})
    except:
        pass
    
    return jsonify({'message': 'Deleted from frontend cache'})

# ============================================================
# HTML Template with PDF Upload Button - FIXED VERSION
# ============================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Network Learning Hub - VLM & PDF Support</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; background: #f5f5f5; height: 100vh; }
        .app-container { display: flex; height: 100vh; }
        
        /* Sidebar */
        .sidebar { width: 260px; background: #202123; color: white; display: flex; flex-direction: column; }
        .sidebar-header { padding: 15px; border-bottom: 1px solid #4d4d4f; }
        .new-chat-btn { width: 100%; padding: 12px; background: transparent; border: 1px solid #4d4d4f; color: white; border-radius: 6px; cursor: pointer; display: flex; align-items: center; gap: 10px; }
        .new-chat-btn:hover { background: #2d2d2e; }
        .conversation-list { flex: 1; overflow-y: auto; padding: 10px; }
        .conversation-item { padding: 12px; margin-bottom: 5px; border-radius: 6px; cursor: pointer; display: flex; align-items: center; gap: 10px; color: #ececf1; }
        .conversation-item:hover { background: #2d2d2e; }
        .conversation-item.active { background: #343541; }
        .conversation-preview { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
        .delete-btn { opacity: 0; background: none; border: none; color: #8e8ea0; cursor: pointer; padding: 4px; }
        .conversation-item:hover .delete-btn { opacity: 1; }
        .sidebar-footer { padding: 15px; border-top: 1px solid #4d4d4f; font-size: 12px; color: #8e8ea0; }
        
        /* Main Content */
        .main-content { flex: 1; display: flex; flex-direction: column; background: white; }
        .chat-header { padding: 15px 20px; border-bottom: 1px solid #e5e5e5; display: flex; justify-content: space-between; align-items: center; }
        .chat-header h1 { font-size: 18px; }
        .ai-status { display: flex; align-items: center; gap: 6px; font-size: 13px; padding: 6px 12px; border-radius: 20px; }
        .ai-status.online { background: #d1fae5; color: #065f46; }
        .ai-status.offline { background: #fee2e2; color: #991b1b; }
        .vlm-badge { background: linear-gradient(135deg, #8b5cf6, #6366f1); color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px; margin-left: 8px; }
        .pdf-badge { background: linear-gradient(135deg, #ef4444, #f97316); color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px; margin-left: 8px; }
        
        .chat-messages { flex: 1; overflow-y: auto; padding: 20px; }
        .message { max-width: 800px; margin: 0 auto 20px; padding: 20px; border-radius: 12px; }
        .user-message { background: #f7f7f8; border: 1px solid #e5e5e5; }
        .bot-message { background: white; border: 1px solid #e5e5e5; }
        .message-role { font-weight: 600; margin-bottom: 8px; color: #374151; }
        .message-content { color: #1f2937; line-height: 1.6; }
        .message-image { max-width: 300px; max-height: 200px; border-radius: 8px; margin-top: 10px; border: 1px solid #e5e5e5; }
        .message-pdf { 
            display: inline-flex; 
            align-items: center; 
            gap: 8px; 
            background: #fef3c7; 
            color: #92400e; 
            padding: 8px 12px; 
            border-radius: 8px; 
            font-size: 13px; 
            margin-top: 10px;
            border: 1px solid #fcd34d;
        }
        
        .input-area { border-top: 1px solid #e5e5e5; padding: 20px; }
        .input-container { max-width: 800px; margin: 0 auto; position: relative; }
        .message-input { width: 100%; padding: 15px 140px 15px 20px; border: 1px solid #d1d5db; border-radius: 12px; font-size: 15px; resize: none; outline: none; }
        .send-btn { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: #3b82f6; color: white; border: none; width: 36px; height: 36px; border-radius: 8px; cursor: pointer; }
        
        /* Upload buttons container - FIXED */
        .upload-buttons { 
            position: absolute; 
            right: 50px; 
            top: 50%; 
            transform: translateY(-50%); 
            display: flex; 
            gap: 6px; 
            z-index: 10;
        }
        
        .upload-btn { 
            background: #8b5cf6; 
            color: white; 
            border: none; 
            width: 36px; 
            height: 36px; 
            border-radius: 8px; 
            cursor: pointer; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            position: relative;
            flex-shrink: 0;
        }
        .upload-btn:hover { background: #7c3aed; }
        .upload-btn.has-file { background: #10b981; }
        
        /* PDF button specific styling - FIXED */
        .pdf-btn {
            background: #ef4444 !important;
        }
        .pdf-btn:hover {
            background: #dc2626 !important;
        }
        .pdf-btn.has-file {
            background: #10b981 !important;
        }
        
        /* Image preview */
        .image-preview-container { 
            max-width: 800px; 
            margin: 0 auto 10px; 
            padding: 10px; 
            background: #f9fafb; 
            border-radius: 8px; 
            display: none;
            align-items: center;
            gap: 10px;
        }
        .image-preview-container.show { display: flex; }
        .image-preview { max-width: 100px; max-height: 80px; border-radius: 6px; border: 1px solid #e5e5e5; }
        .image-preview-name { font-size: 13px; color: #6b7280; flex: 1; }
        .image-preview-remove { background: #ef4444; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        
        /* PDF preview */
        .pdf-preview-container { 
            max-width: 800px; 
            margin: 0 auto 10px; 
            padding: 10px; 
            background: #fef3c7; 
            border-radius: 8px; 
            display: none;
            align-items: center;
            gap: 10px;
            border: 1px solid #fcd34d;
        }
        .pdf-preview-container.show { display: flex; }
        .pdf-preview-icon { 
            width: 40px; 
            height: 40px; 
            background: #ef4444; 
            border-radius: 6px; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            color: white;
            font-size: 12px;
            font-weight: bold;
        }
        .pdf-preview-name { font-size: 13px; color: #92400e; flex: 1; }
        .pdf-preview-info { font-size: 11px; color: #b45309; }
        .pdf-preview-remove { background: #ef4444; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        
        /* Hidden file inputs */
        #image-input, #pdf-input { display: none; }
        
        /* Quiz Styles */
        .quiz-container { max-width: 800px; margin: 0 auto; padding: 20px; background: #fafafa; border-radius: 12px; border: 1px solid #e5e5e5; }
        .question-container { background: white; border: 1px solid #e5e5e5; border-radius: 8px; padding: 20px; margin: 15px 0; }
        .explanation { 
            color: #4b5563; 
            font-style: italic; 
            margin-top: 15px; 
            padding: 15px; 
            background: #f9fafb; 
            border-left: 4px solid #3b82f6; 
            border-radius: 0 6px 6px 0; 
            display: none;
        }
        .explanation.show { display: block; }
        .quiz-btn { padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; margin-right: 8px; margin-top: 10px; }
        .quiz-btn.secondary { background: #6b7280; }
        
        /* Empty state */
        .empty-state { text-align: center; padding: 60px 20px; color: #6b7280; }
        .empty-state h2 { margin-bottom: 10px; color: #111827; }
        
        /* Animation */
        @keyframes bounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-4px); }
        }
        
        /* Upload hints */
        .upload-hint {
            position: absolute;
            bottom: -25px;
            left: 0;
            font-size: 11px;
            color: #8b5cf6;
            display: none;
            white-space: nowrap;
        }
        .upload-btn:hover .upload-hint { display: block; }
        
        .pdf-hint {
            color: #ef4444;
        }
        .pdf-btn:hover .pdf-hint { display: block; }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <button class="new-chat-btn" onclick="startNewChat()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                    New chat
                </button>
                <button class="new-chat-btn" onclick="startQuiz()" style="margin-top: 10px; background: linear-gradient(135deg, #3b82f6, #2563eb);">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"></path>
                    </svg>
                    Start Quiz
                </button>
            </div>
            <div class="conversation-list" id="conversation-list"></div>
            <div class="sidebar-footer">
                Network Learning Hub
                <div style="margin-top: 5px; font-size: 11px; color: #8b5cf6;">VLM & PDF Support Enabled</div>
                <div id="storage-status" style="margin-top: 5px; font-size: 11px;">Loading...</div>
            </div>
        </div>
        
        <!-- Main Content -->
        <div class="main-content">
            <div class="chat-header">
                <h1>Network Assistant <span class="vlm-badge">VLM</span><span class="pdf-badge">PDF</span></h1>
                <div id="ai-status" class="ai-status offline">
                    <span id="ai-status-text">Checking...</span>
                </div>
            </div>
            <div class="chat-messages" id="chat-messages">
                <div class="empty-state">
                    <h2>Welcome to Network Learning Hub</h2>
                    <p>Ask me about TCP/IP, OSI model, BGP, subnetting, or any networking topic.</p>
                    <p style="margin-top: 10px; color: #8b5cf6;">Upload diagram images for AI analysis!</p>
                    <p style="margin-top: 5px; color: #ef4444;">Upload PDF documents for content analysis!</p>
                </div>
            </div>
            
            <!-- Image Preview -->
            <div class="image-preview-container" id="image-preview-container">
                <img class="image-preview" id="image-preview" src="" alt="Preview">
                <span class="image-preview-name" id="image-preview-name"></span>
                <button class="image-preview-remove" onclick="removeImage()">Remove</button>
            </div>
            
            <!-- PDF Preview -->
            <div class="pdf-preview-container" id="pdf-preview-container">
                <div class="pdf-preview-icon">PDF</div>
                <div style="flex: 1;">
                    <div class="pdf-preview-name" id="pdf-preview-name"></div>
                    <div class="pdf-preview-info" id="pdf-preview-info"></div>
                </div>
                <button class="pdf-preview-remove" onclick="removePDF()">Remove</button>
            </div>
            
            <div class="input-area">
                <div class="input-container">
                    <textarea class="message-input" id="message-input" rows="1" placeholder="Ask about networking concepts, upload a diagram, or upload a PDF..."></textarea>
                    
                    <!-- Upload Buttons - PDF First (Left), Image Second (Right) -->
                    <div class="upload-buttons">
                        <!-- PDF Upload Button (RED) -->
                        <button class="upload-btn pdf-btn" id="pdf-btn" onclick="triggerPDFUpload()" title="Upload PDF document">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                                <path d="M12 18v-6"></path>
                                <path d="M9 15l3 3 3-3"></path>
                            </svg>
                            <span class="upload-hint pdf-hint">Upload PDF</span>
                        </button>
                        <input type="file" id="pdf-input" accept=".pdf,application/pdf" onchange="handlePDFSelect(event)">
                        
                        <!-- Image Upload Button (PURPLE) -->
                        <button class="upload-btn" id="upload-btn" onclick="triggerImageUpload()" title="Upload diagram image">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                                <polyline points="21 15 16 10 5 21"></polyline>
                            </svg>
                            <span class="upload-hint">Upload Image</span>
                        </button>
                        <input type="file" id="image-input" accept="image/*" onchange="handleImageSelect(event)">
                    </div>
                    
                    <button class="send-btn" onclick="sendMessage()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global state
        let currentSessionId = null;
        let isTyping = false;
        let selectedImage = null;
        let selectedPDF = null;
        let pdfInfo = null;
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            checkAIStatus();
            startNewChat();
            updateSidebar();
            
            document.getElementById('message-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        });
        
        async function checkAIStatus() {
            try {
                const response = await fetch('/ai_status');
                const data = await response.json();
                const statusDiv = document.getElementById('ai-status');
                const statusText = document.getElementById('ai-status-text');
                if (data.available) {
                    statusDiv.className = 'ai-status online';
                    let features = [];
                    if (data.vlm) features.push('VLM');
                    if (data.pdf) features.push('PDF');
                    statusText.textContent = features.length > 0 ? `AI + ${features.join(' + ')} Online` : 'AI Online';
                } else {
                    statusDiv.className = 'ai-status offline';
                    statusText.textContent = 'AI Offline';
                }
            } catch (error) {
                console.error('Status check failed:', error);
            }
        }
        
        // ============================================================
        // IMAGE UPLOAD FUNCTIONS
        // ============================================================
        
        function triggerImageUpload() {
            document.getElementById('image-input').click();
        }
        
        function handleImageSelect(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            // Validate file type
            if (!file.type.startsWith('image/')) {
                alert('Please select an image file (JPEG, PNG, GIF, WebP)');
                return;
            }
            
            // Validate file size (max 10MB)
            if (file.size > 10 * 1024 * 1024) {
                alert('Image too large. Maximum size is 10MB.');
                return;
            }
            
            selectedImage = file;
            selectedPDF = null; // Clear PDF if image selected
            removePDF(); // Clear PDF preview
            
            // Show preview
            const reader = new FileReader();
            reader.onload = function(e) {
                document.getElementById('image-preview').src = e.target.result;
                document.getElementById('image-preview-name').textContent = file.name;
                document.getElementById('image-preview-container').classList.add('show');
                document.getElementById('upload-btn').classList.add('has-file');
            };
            reader.readAsDataURL(file);
        }
        
        function removeImage() {
            selectedImage = null;
            document.getElementById('image-input').value = '';
            document.getElementById('image-preview-container').classList.remove('show');
            document.getElementById('upload-btn').classList.remove('has-file');
        }
        
        // ============================================================
        // PDF UPLOAD FUNCTIONS - NEW
        // ============================================================
        
        function triggerPDFUpload() {
            document.getElementById('pdf-input').click();
        }
        
        async function handlePDFSelect(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            // Validate file type
            if (!file.name.toLowerCase().endsWith('.pdf')) {
                alert('Please select a PDF file (.pdf)');
                return;
            }
            
            // Validate file size (max 20MB)
            if (file.size > 20 * 1024 * 1024) {
                alert('PDF too large. Maximum size is 20MB.');
                return;
            }
            
            selectedPDF = file;
            selectedImage = null; // Clear image if PDF selected
            removeImage(); // Clear image preview
            
            // Show preview with validation
            document.getElementById('pdf-preview-name').textContent = file.name;
            document.getElementById('pdf-preview-info').textContent = `Size: ${(file.size / 1024 / 1024).toFixed(2)} MB - Validating...`;
            document.getElementById('pdf-preview-container').classList.add('show');
            document.getElementById('pdf-btn').classList.add('has-file');
            
            // Validate PDF with backend
            try {
                const formData = new FormData();
                formData.append('pdf', file);
                
                const response = await fetch('/pdf/validate', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.valid) {
                    pdfInfo = data;
                    document.getElementById('pdf-preview-info').textContent = 
                        `Size: ${data.file_size_mb} MB | Pages: ${data.total_pages} ${data.truncated ? '| Truncated' : ''}`;
                } else {
                    document.getElementById('pdf-preview-info').textContent = 
                        `Error: ${data.error || 'Invalid PDF'}`;
                    document.getElementById('pdf-preview-info').style.color = '#ef4444';
                }
            } catch (error) {
                console.error('PDF validation error:', error);
                document.getElementById('pdf-preview-info').textContent = 
                    `Size: ${(file.size / 1024 / 1024).toFixed(2)} MB`;
            }
        }
        
        function removePDF() {
            selectedPDF = null;
            pdfInfo = null;
            document.getElementById('pdf-input').value = '';
            document.getElementById('pdf-preview-container').classList.remove('show');
            document.getElementById('pdf-btn').classList.remove('has-file');
            document.getElementById('pdf-preview-info').style.color = '#b45309';
        }
        
        // ============================================================
        // CONVERSATION FUNCTIONS
        // ============================================================
        
        async function updateSidebar() {
            const listDiv = document.getElementById('conversation-list');
            listDiv.innerHTML = '<div style="padding: 10px; color: #8e8ea0; text-align: center;">Loading...</div>';
            
            try {
                const response = await fetch('/conversations');
                if (!response.ok) throw new Error('Failed to fetch conversations');
                
                const data = await response.json();
                listDiv.innerHTML = '';
                
                if (data.conversations && data.conversations.length > 0) {
                    document.getElementById('storage-status').textContent = 
                        `${data.conversations.length} conversations (${data.storage || 'database'})`;
                    
                    data.conversations.forEach(conv => {
                        const item = document.createElement('div');
                        item.className = 'conversation-item' + (conv.session_id === currentSessionId ? ' active' : '');
                        item.setAttribute('data-session-id', conv.session_id);
                        
                        // Use preview or title, with fallback
                        let preview = conv.preview || conv.title || 'New Conversation';
                        
                        item.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                            </svg>
                            <span class="conversation-preview">${escapeHtml(preview)}</span>
                            <button class="delete-btn" title="Delete conversation">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="3 6 5 6 21 6"></polyline>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                </svg>
                            </button>
                        `;
                        
                        // Click on item loads conversation
                        item.addEventListener('click', function(e) {
                            // Don't trigger if delete button was clicked
                            if (e.target.closest('.delete-btn')) return;
                            loadConversation(conv.session_id);
                        });
                        
                        // Delete button handler
                        const deleteBtn = item.querySelector('.delete-btn');
                        deleteBtn.addEventListener('click', function(e) {
                            e.stopPropagation();
                            deleteConversation(conv.session_id);
                        });
                        
                        listDiv.appendChild(item);
                    });
                } else {
                    document.getElementById('storage-status').textContent = 'No conversations';
                    listDiv.innerHTML = '<div style="padding: 20px; color: #8e8ea0; text-align: center;">No conversations yet</div>';
                }
            } catch (error) {
                console.error('Failed to load conversations:', error);
                document.getElementById('storage-status').textContent = 'Error loading';
                listDiv.innerHTML = '<div style="padding: 20px; color: #ef4444; text-align: center;">Failed to load</div>';
            }
        }
        
        async function startNewChat() {
            try {
                const response = await fetch('/conversation/new', {method: 'POST'});
                const data = await response.json();
                currentSessionId = data.session_id;
                
                // Clear any selected files
                removeImage();
                removePDF();
                
                const messagesDiv = document.getElementById('chat-messages');
                messagesDiv.innerHTML = `
                    <div class="empty-state">
                        <h2>New Conversation Started</h2>
                        <p>Ask me anything about computer networking!</p>
                        <p style="margin-top: 10px; color: #8b5cf6;">Upload diagram images for AI analysis</p>
                        <p style="margin-top: 5px; color: #ef4444;">Upload PDF documents for content analysis</p>
                    </div>
                `;
                
                await updateSidebar();
                document.getElementById('message-input').focus();
                
            } catch (error) {
                console.error('Failed to start new chat:', error);
                currentSessionId = 'local-' + Date.now();
            }
        }
        
        async function loadConversation(sessionId) {
            console.log('Loading conversation:', sessionId);
            currentSessionId = sessionId;
            
            // Clear any selected files
            removeImage();
            removePDF();
            
            // Update active state in sidebar
            document.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.remove('active');
            });
            const activeItem = document.querySelector(`.conversation-item[data-session-id="${sessionId}"]`);
            if (activeItem) activeItem.classList.add('active');
            
            try {
                const response = await fetch(`/conversation/${sessionId}`);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                
                const data = await response.json();
                console.log('Conversation data received:', data);
                
                const messagesDiv = document.getElementById('chat-messages');
                messagesDiv.innerHTML = '';
                
                if (data.messages && data.messages.length > 0) {
                    console.log(`Rendering ${data.messages.length} messages`);
                    data.messages.forEach((msg, index) => {
                        console.log(`Message ${index}:`, msg);
                        if (msg.role === 'user') {
                            addMessage(msg.content, 'user', null, msg.has_image, null, msg.has_pdf);
                        } else if (msg.role === 'assistant') {
                            addMessage(msg.content, 'bot', msg.provider || 'ai');
                        } else {
                            console.warn('Unknown message role:', msg.role);
                        }
                    });
                } else {
                    console.log('No messages in conversation');
                    messagesDiv.innerHTML = `
                        <div class="empty-state">
                            <h2>No Messages</h2>
                            <p>This conversation has no messages yet.</p>
                        </div>
                    `;
                }
                
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                
            } catch (error) {
                console.error('Failed to load conversation:', error);
                document.getElementById('chat-messages').innerHTML = `
                    <div class="empty-state">
                        <h2>Error Loading Conversation</h2>
                        <p>${escapeHtml(error.message)}</p>
                    </div>
                `;
            }
        }
        
        async function deleteConversation(sessionId) {
            if (!confirm('Delete this conversation?')) return;
            
            try {
                const response = await fetch(`/conversation/${sessionId}`, {method: 'DELETE'});
                if (response.ok) {
                    if (sessionId === currentSessionId) {
                        await startNewChat();
                    }
                    await updateSidebar();
                }
            } catch (error) {
                console.error('Delete failed:', error);
            }
        }
        
        // ============================================================
        // CHAT FUNCTIONS (with image and PDF support)
        // ============================================================
        
        async function sendMessage() {
            const input = document.getElementById('message-input');
            const message = input.value.trim();
            
            // Allow sending if there's a message, image, or PDF
            if ((!message && !selectedImage && !selectedPDF) || isTyping) return;
            
            const messagesDiv = document.getElementById('chat-messages');
            if (messagesDiv.querySelector('.empty-state')) {
                messagesDiv.innerHTML = '';
            }
            
            // Show user message with appropriate preview
            if (selectedImage) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    addMessage(message || '[Image uploaded]', 'user', null, true, e.target.result, false);
                };
                reader.readAsDataURL(selectedImage);
            } else if (selectedPDF) {
                addMessage(message || `[PDF uploaded: ${selectedPDF.name}]`, 'user', null, false, null, true, selectedPDF.name);
            } else {
                addMessage(message, 'user');
            }
            
            input.value = '';
            showTyping();
            
            try {
                let response;
                
                if (selectedImage) {
                    // Send with image to VLM endpoint
                    const formData = new FormData();
                    formData.append('message', message);
                    formData.append('session_id', currentSessionId || '');
                    formData.append('image', selectedImage);
                    
                    response = await fetch('/chat/with-image', {
                        method: 'POST',
                        body: formData
                    });
                    
                    // Clear selected image after sending
                    removeImage();
                    
                } else if (selectedPDF) {
                    // Send with PDF to PDF endpoint
                    const formData = new FormData();
                    formData.append('message', message);
                    formData.append('session_id', currentSessionId || '');
                    formData.append('pdf', selectedPDF);
                    
                    response = await fetch('/chat/with-pdf', {
                        method: 'POST',
                        body: formData
                    });
                    
                    // Clear selected PDF after sending
                    removePDF();
                    
                } else {
                    // Regular text chat
                    response = await fetch('/chat', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            message: message,
                            session_id: currentSessionId
                        })
                    });
                }
                
                const data = await response.json();
                hideTyping();
                
                if (data.session_id) {
                    currentSessionId = data.session_id;
                }
                
                addMessage(data.response, 'bot', data.provider);
                await updateSidebar();
                
            } catch (error) {
                hideTyping();
                addMessage('Error: ' + error.message, 'bot', 'error');
            }
        }
        
        function addMessage(content, role, provider, hasImage = false, imageData = null, hasPDF = false, pdfName = null) {
            const messagesDiv = document.getElementById('chat-messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${role}-message`;
            
            const roleLabel = role === 'user' ? 'You' : 'Assistant';
            let providerBadge = provider && provider !== 'local' && provider !== 'error' 
                ? `<span style="background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 8px;">${provider}</span>`
                : '';
            
            let attachmentHtml = '';
            if (hasImage && imageData) {
                attachmentHtml = `<img src="${imageData}" class="message-image" alt="Uploaded diagram">`;
            } else if (hasImage) {
                attachmentHtml = `<div style="color: #8b5cf6; font-size: 12px; margin-top: 5px;">[Image attached]</div>`;
            } else if (hasPDF) {
                attachmentHtml = `
                    <div class="message-pdf">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                        </svg>
                        <span>${pdfName || 'PDF Document'}</span>
                    </div>
                `;
            }
            
            messageDiv.innerHTML = `
                <div class="message-role">${roleLabel}${providerBadge}</div>
                <div class="message-content">${escapeHtml(content).replace(/\\n/g, '<br>')}</div>
                ${attachmentHtml}
            `;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function showTyping() {
            isTyping = true;
            const messagesDiv = document.getElementById('chat-messages');
            const typingDiv = document.createElement('div');
            typingDiv.className = 'message bot-message';
            typingDiv.id = 'typing-indicator';
            typingDiv.innerHTML = `
                <div class="message-role">Assistant</div>
                <div style="display: flex; gap: 4px; padding: 12px 0;">
                    <span style="width: 8px; height: 8px; background: #9ca3af; border-radius: 50%; animation: bounce 1.4s infinite;"></span>
                    <span style="width: 8px; height: 8px; background: #9ca3af; border-radius: 50%; animation: bounce 1.4s infinite 0.2s;"></span>
                    <span style="width: 8px; height: 8px; background: #9ca3af; border-radius: 50%; animation: bounce 1.4s infinite 0.4s;"></span>
                </div>
            `;
            messagesDiv.appendChild(typingDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function hideTyping() {
            isTyping = false;
            const typingDiv = document.getElementById('typing-indicator');
            if (typingDiv) {
                typingDiv.remove();
            }
        }
        
        // ============================================================
        // QUIZ FUNCTIONS
        // ============================================================
        
        function startQuiz() {
            const messagesDiv = document.getElementById('chat-messages');
            messagesDiv.innerHTML = `
                <div class="message bot-message">
                    <div class="message-role">Quiz</div>
                    <div class="message-content">
                        <div class="quiz-container">
                            <h2>Network Quiz</h2>
                            <div class="question-container">
                                <h3>TCP Basics</h3>
                                <p>Which mechanism handles out-of-order packets in Selective Repeat ARQ?</p>
                                <label><input type="radio" name="q1" value="a"> a) Discard them</label><br>
                                <label><input type="radio" name="q1" value="b"> b) Store in buffer</label><br>
                                <label><input type="radio" name="q1" value="c"> c) Acknowledge last</label><br>
                                <button class="quiz-btn" onclick="checkAnswer('q1', 'b')">Check Answer</button>
                                <button class="quiz-btn secondary" onclick="showExplanation('exp1')">Show Explanation</button>
                                <div id="exp1" class="explanation">
                                    <strong>Answer: b</strong><br>
                                    Selective Repeat stores out-of-order packets in a receiver buffer.
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        function checkAnswer(questionId, correctAnswer) {
            const selected = document.querySelector(`input[name="${questionId}"]:checked`);
            if (!selected) {
                alert('Please select an answer first!');
                return;
            }
            
            const isCorrect = selected.value === correctAnswer;
            alert(isCorrect ? '✓ Correct!' : '✗ Incorrect. Try again!');
        }
        
        function showExplanation(expId) {
            const expElement = document.getElementById(expId);
            if (expElement) {
                expElement.classList.toggle('show');
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("=" * 60)
    print("  Network Learning Hub - VLM & PDF ENABLED")
    print("=" * 60)
    print("  Students can now upload diagram images AND PDF documents!")
    print("  Uses Qwen-VL for image analysis")
    print("  Uses AI text analysis for PDF content")
    print("=" * 60)
    print("  Starting on http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, port=5000, use_reloader=False)