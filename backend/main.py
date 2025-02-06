from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
from pinecone import Pinecone, ServerlessSpec
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
from openai import OpenAI
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1"
)

# Initialize Pinecone
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME")

if not all([PINECONE_API_KEY, PINECONE_ENV, PINECONE_INDEX]):
    raise ValueError(
        "Missing Pinecone configuration. Please set PINECONE_API_KEY, "
        "PINECONE_ENVIRONMENT, and PINECONE_INDEX_NAME in your .env file."
    )

try:
    print("Initializing Pinecone...")
    pc = Pinecone(
        api_key=PINECONE_API_KEY,
        environment=PINECONE_ENV
    )
    print("Pinecone client created successfully.")

    # Check if index exists, create if not
    existing_indexes = pc.list_indexes().names()
    if PINECONE_INDEX not in existing_indexes:
        print(f"Index '{PINECONE_INDEX}' not found. Creating...")
        pc.create_index(
            name=PINECONE_INDEX,
            dimension=1536,
            metric='cosine',  # or "euclidean", depending on your use case
            spec=ServerlessSpec(
                cloud='aws',        # or "gcp"
                region=PINECONE_ENV
            )
        )
        print(f"Index '{PINECONE_INDEX}' created successfully.")

    # Connect to the index
    print(f"Connecting to index: {PINECONE_INDEX}")
    index = pc.Index(PINECONE_INDEX)
    print("Connected to index successfully.")
    
    # Test the connection
    print("Testing connection with describe_index_stats...")
    stats = index.describe_index_stats()
    print(f"Index stats: {stats}")
except Exception as e:
    print(f"Error initializing Pinecone: {str(e)}")
    raise ValueError(
        "Failed to initialize Pinecone. Please check your API key, environment, "
        "and index name in your .env file."
    )

class DocumentRequest(BaseModel):
    url: str

class ChatRequest(BaseModel):
    question: str
    conversation_history: List[Dict[str, str]] = []

def process_documentation(url: str):
    """Fetch and process API documentation from a given URL."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type.lower() and 'application/json' not in content_type.lower():
            raise HTTPException(status_code=400, detail=f"Unsupported content type: {content_type}")
        
        # For JSON content, return it directly
        if 'application/json' in content_type.lower():
            return response.text
        
        # For HTML content, parse it
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try different common documentation structures
        content = None
        selectors = [
            'main',  # Standard HTML5 main content
            'article',  # Article content
            '.content',  # Common content class
            '.documentation',  # Common documentation class
            '#docs-content',  # Common documentation ID
            '.markdown-body',  # GitHub-style documentation
            '.api-content'  # API documentation specific
        ]
        
        for selector in selectors:
            if selector.startswith('.'):
                content = soup.find('div', {'class': selector[1:]})
            elif selector.startswith('#'):
                content = soup.find('div', {'id': selector[1:]})
            else:
                content = soup.find(selector)
            
            if content:
                break
        
        if not content:
            # If no specific content area found, try to get the body
            content = soup.find('body')
            if not content:
                content = soup
        
        # Clean the content
        # Remove script and style elements
        for element in content.find_all(['script', 'style', 'nav', 'footer']):
            element.decompose()
        
        text = content.get_text(separator='\n', strip=True)
        return text
        
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if '403' in error_msg:
            raise HTTPException(status_code=400, detail=f"Access denied by the website. Try visiting the documentation directly: {url}")
        elif '404' in error_msg:
            raise HTTPException(status_code=400, detail=f"Documentation page not found: {url}")
        elif 'timeout' in error_msg.lower():
            raise HTTPException(status_code=400, detail=f"Request timed out. The server might be slow or down.")
        else:
            raise HTTPException(status_code=400, detail=f"Error accessing documentation: {error_msg}")
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
    try:
        if not request.url:
            raise HTTPException(status_code=400, detail="URL cannot be empty")

        # Validate URL format
        if not request.url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Invalid URL format. Must start with http:// or https://")

        content = process_documentation(request.url)
        if not content:
            raise HTTPException(status_code=400, detail="No content could be extracted from the URL")

        chunks = chunk_text(content)
        print(f"Processing {len(chunks)} chunks from {request.url}")

        # Get embeddings and store in Pinecone
        for i, chunk in enumerate(chunks):
            try:
                response = client.embeddings.create(
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
            except Exception as e:
                print(f"Error processing chunk {i}: {str(e)}")
                continue

        return {"message": "Documentation processed successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in process_doc_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing documentation: {str(e)}")

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
            embedding_response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=request.question
            )
            question_embedding = embedding_response.data[0].embedding
        except Exception as e:
            print(f"Error creating embedding: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating question embedding: {str(e)}")
        
        try:
            # Query Pinecone for relevant context
            try:
                query_response = index.query(
                    vector=question_embedding,
                    top_k=3,
                    include_metadata=True
                )
            except Exception as e:
                print(f"Error querying Pinecone: {str(e)}")
                if 'not found' in str(e).lower() or 'failed to resolve' in str(e).lower():
                    raise HTTPException(
                        status_code=500,
                        detail="Unable to connect to Pinecone. Please check your index name and environment settings."
                    )
                raise HTTPException(
                    status_code=500,
                    detail=f"Error querying Pinecone: {str(e)}"
                )
        except Exception as e:
            print(f"Error querying Pinecone: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error querying Pinecone: {str(e)}")
        
        # Prepare conversation context
        if not query_response.get('matches'):
            context = "I don't have enough context about this API documentation yet. Could you try asking about something else, or try processing the documentation first?"
        else:
            context = "\n".join([match.get('metadata', {}).get('text', '') for match in query_response['matches']])
            if not context.strip():
                context = "I don't have enough context about this API documentation yet. Could you try asking about something else, or try processing the documentation first?"
        
        # Prepare conversation history
        conversation = []
        for msg in request.conversation_history:
            conversation.append({"role": msg["role"], "content": msg["content"]})
        
        try:
            # Create chat completion
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI assistant helping developers understand API documentation. "
                                  "Provide clear, concise answers and include code examples when relevant."
                    },
                    {
                        "role": "user",
                        "content": f"Given this API documentation context:\n{context}\n\nQuestion: {request.question}"
                    }
                ] + conversation
            )
            
            return {"response": response.choices[0].message.content}
        except Exception as e:
            print(f"Error creating chat completion: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating chat completion: {str(e)}")
            
    except HTTPException as he:
        print(f"HTTP Exception in chat endpoint: {str(he)}")
        raise he
    except Exception as e:
        error_msg = str(e)
        print(f"Unexpected error in chat endpoint: {error_msg}")
        if 'matches' in error_msg:
            raise HTTPException(
                status_code=500,
                detail="No matching documentation found. Please try processing the documentation first."
            )
        elif 'api_key' in error_msg.lower():
            raise HTTPException(
                status_code=500,
                detail="API key configuration error. Please check your OpenAI and Pinecone settings."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"An unexpected error occurred: {error_msg}"
            )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
