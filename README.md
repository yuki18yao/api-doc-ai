# API Documentation AI Assistant

An AI-powered assistant that helps developers understand API documentation through an interactive chat interface.

## Features

- Real-time API documentation processing
- Interactive chat interface with drag-and-drop functionality
- Code snippet support with syntax highlighting
- Conversation history
- Browser extension for universal compatibility

## Setup

### Backend Setup

1. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your API keys:
```
OPENAI_API_KEY=your_openai_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_pinecone_environment
PINECONE_INDEX_NAME=your_index_name
```

4. Start the backend server:
```bash
cd backend
uvicorn main:app --reload
```

### Browser Extension Setup

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" in the top right
3. Click "Load unpacked" and select the `extension` directory

## Usage

1. Navigate to any API documentation page
2. The chat widget will appear in the bottom right corner
3. Ask questions about the API documentation
4. Drag the widget to reposition it
5. Minimize/maximize the widget as needed

## Architecture

- Backend: FastAPI + OpenAI + Pinecone
- Frontend: Vanilla JavaScript + CSS
- Browser Extension: Chrome Extension Manifest V3

## Future Improvements

1. Add support for more documentation formats
2. Implement authentication for the backend
3. Add support for more browsers
4. Create an embeddable widget version
5. Add support for offline documentation processing

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request
