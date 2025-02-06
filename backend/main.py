from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import pinecone
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import tiktoken
from typing import List, Dict

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize Pinecone
pinecone.init(
    api_key=os.getenv("PINECONE_API_KEY"),
    environment=os.getenv("PINECONE_ENVIRONMENT")
)
index = pinecone.Index(os.getenv("PINECONE_INDEX_NAME"))

class DocumentRequest(BaseModel):
    url: str

class ChatRequest(BaseModel):
    question: str
    context: str
    conversation_history: List[Dict[str, str]]

def process_documentation(url: str):
    """Fetch and process API documentation from a given URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract main content (customize based on common documentation structures)
        main_content = soup.find('main') or soup.find('article') or soup.find('div', {'class': 'content'})
        if not main_content:
            return response.text
        
        return main_content.get_text()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing documentation: {str(e)}")

def chunk_text(text: str, chunk_size: int = 1000):
    """Split text into chunks for processing."""
    words = text.split()
    chunks = []
    current_chunk = []
    current_size = 0
    
    for word in words:
        current_chunk.append(word)
        current_size += len(word) + 1  # +1 for space
        
        if current_size >= chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_size = 0
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

@app.post("/process-documentation")
async def process_doc_endpoint(request: DocumentRequest):
    """Process and store API documentation in Pinecone."""
    content = process_documentation(request.url)
    chunks = chunk_text(content)
    
    # Get embeddings and store in Pinecone
    for i, chunk in enumerate(chunks):
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=chunk
        )
        embedding = response.data[0].embedding
        
        # Store in Pinecone
        index.upsert(vectors=[{
            'id': f"{request.url}-{i}",
            'values': embedding,
            'metadata': {'text': chunk, 'url': request.url}
        }])
    
    return {"message": "Documentation processed successfully"}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        print("Received chat request:", request.dict())
        if not request.question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        # Validate conversation history format
        for msg in request.conversation_history:
            if 'role' not in msg or 'content' not in msg:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid message format in conversation history. Expected 'role' and 'content', got: {msg}"
                )
        
        try:
            # Create embedding for the question
            question_embedding = openai.embeddings.create(
                model="text-embedding-ada-002",
                input=request.question
            ).data[0].embedding
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating question embedding: {str(e)}")
        
        try:
            # Query Pinecone for relevant context
            query_response = index.query(
                vector=question_embedding,
                top_k=3,
                include_metadata=True
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error querying Pinecone: {str(e)}")
        
        # Prepare conversation context
        context = "\n".join([match['metadata']['text'] for match in query_response['matches']])
        
        # Prepare conversation history
        conversation = []
        for msg in request.conversation_history:
            conversation.append({"role": msg["role"], "content": msg["content"]})
        
        try:
            # Create chat completion
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an AI assistant helping developers understand API documentation. "
                                                "Provide clear, concise answers and include code examples when relevant."},
                    {"role": "user", "content": f"Given this API documentation context:\n{context}\n\nQuestion: {request.question}"}
                ] + conversation
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating chat completion: {str(e)}")
        
        return {"response": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error handling chat request: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
