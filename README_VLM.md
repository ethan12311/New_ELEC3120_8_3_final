# Network Learning Hub - VLM Support

This version of the Network Learning Hub includes **Vision Language Model (VLM) support**, allowing students to upload network diagram images for AI analysis!

## New Features

### Image Upload for Diagram Analysis
- Students can now upload images of network diagrams, topology drawings, or quiz questions
- The AI uses **Qwen-VL** (a Vision Language Model) to analyze the images
- The AI can:
  - Identify network components (routers, switches, hosts, etc.)
  - Explain the network topology and architecture
  - Describe data flow and communication patterns
  - Answer questions about what's shown in the diagram
  - Help solve diagram-based quiz questions

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

Edit `.env` with your OpenRouter API key:
```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Get your API key from: https://openrouter.ai/keys

### 3. Start the FastAPI Backend
```bash
python main.py
```
or
```bash
uvicorn main:app --reload --port 8000
```

### 4. Start the Flask Frontend
In a new terminal:
```bash
python quiz_app_ai.py
```

### 5. Open in Browser
Navigate to: http://localhost:5000

## Using the Image Upload Feature

1. Click the **purple image icon** button in the chat input area
2. Select an image file (JPEG, PNG, GIF, or WebP, max 10MB)
3. Optionally type a question about the image
4. Click the send button
5. The AI will analyze the image and provide insights!

## API Endpoints

### New VLM Endpoint
- **POST** `/chat/with-image` - Send a message with an image for VLM analysis
  - Parameters:
    - `message` (string, optional): Your question about the image
    - `session_id` (string, optional): Conversation session ID
    - `image` (file, required): The image file to analyze

### Existing Endpoints
- **POST** `/chat` - Regular text-only chat
- **GET** `/health` - Health check with VLM status
- **GET** `/providers` - List available AI providers

## VLM Model Used

Default: `qwen/qwen2.5-vl-72b-instruct`

This is Qwen's Vision Language Model which excels at:
- Understanding network diagrams and topology drawings
- Reading text within images (OCR capability)
- Answering questions about visual content
- Analyzing complex technical diagrams

You can change the VLM model in `.env`:
```
VLM_MODEL=qwen/qwen2.5-vl-72b-instruct
```

Other VLM options on OpenRouter:
- `qwen/qwen2-vl-72b-instruct`
- `anthropic/claude-3-opus-20240229` (has vision)
- `google/gemini-pro-vision`

## File Structure

```
├── main.py              # FastAPI backend with VLM support
├── quiz_app_ai.py       # Flask frontend with upload button
├── ai_services.py       # AI service with image encoding
├── config.py            # Configuration with VLM settings
├── database.py          # Supabase integration
├── concept_analyzer.py  # Learning analytics
├── requirements.txt     # Python dependencies
└── .env.example         # Environment template
```

## Troubleshooting

### Image too large
- Maximum file size is 10MB (configurable in `.env`)
- Try compressing the image before uploading

### VLM not responding
- Check that your OpenRouter API key is valid
- Verify the backend is running: http://localhost:8000/health
- Check that the VLM model is available on OpenRouter

### Upload button not working
- Make sure you're using a modern browser
- Check browser console for JavaScript errors
- Ensure Flask frontend can reach FastAPI backend

## License

For educational use in ELEC3120 Network course.
