import os
import PyPDF2
import shutil
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from pydantic import BaseModel
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv

# Database Imports
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

load_dotenv()

# --- CONFIGURATION ---
api_key = os.getenv("GEMINI_API_KEY")
nvidia_key = os.getenv("NVIDIA_API_KEY")
google_client_id = os.getenv("GOOGLE_CLIENT_ID")
google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
secret_key = os.getenv("SECRET_KEY", "a-very-secret-key-123")

if api_key:
    genai.configure(api_key=api_key)

if nvidia_key:
    nvidia_client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key)

# --- DATABASE SETUP ---
DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DBUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    picture = Column(String)
    documents = relationship("DBDocument", back_populates="owner")

class DBDocument(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    file_path = Column(String)
    content = Column(Text) # Extracted text
    upload_date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("DBUser", back_populates="documents")
    chats = relationship("DBChat", back_populates="document")

class DBChat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text)
    answer = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    document_id = Column(Integer, ForeignKey("documents.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    document = relationship("DBDocument", back_populates="chats")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FASTAPI APP SETUP ---
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=secret_key)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATA MODELS & STORE ---
class LoginRequest(BaseModel):
    email: str

# In-memory session context for active doc (for performance)
active_contexts = {} # user_email -> {text, filename, doc_id}

DEFAULT_SYSTEM_PROMPT = """You are an AI assistant that answers questions based STRICTLY on the provided document.

RULES:
1. Answer ONLY using the information found in the DOCUMENT TEXT below.
2. If the answer is not present in the document, you MUST respond with exactly: "Not available in document"
3. Do NOT use any external knowledge or hallucinate facts.
4. If you find the answer, ALWAYS mention the page number(s) where the info was found (e.g., "According to page 5...").
5. The text contains markers like "--- [PAGE X] ---" to help you identify page numbers.
6. Keep the answer concise and professional."""

from typing import Optional
class QuestionRequest(BaseModel):
    question: str
    system_prompt: Optional[str] = None
    document_id: Optional[int] = None # To support switching between docs

# --- AUTH ENDPOINTS ---
@app.post("/auth/login")
async def login(request_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = request_data.email.lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    # Check if user exists in DB
    db_user = db.query(DBUser).filter(DBUser.email == email).first()
    if not db_user:
        # Create a new user with a generic name/picture
        db_user = DBUser(
            email=email, 
            name=email.split('@')[0], 
            picture=f"https://ui-avatars.com/api/?name={email}&background=random"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

    request.session["user"] = {
        "id": db_user.id,
        "email": db_user.email,
        "name": db_user.name,
        "picture": db_user.picture
    }
    return {"message": "Logged in successfully"}

@app.get("/auth/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/")

@app.get("/auth/me")
async def get_me(request: Request):
    user = request.session.get("user")
    if not user:
        return JSONResponse(content={"authenticated": False}, status_code=200)
    return {"authenticated": True, "user": user}

# --- DOCUMENT & QA ENDPOINTS ---
@app.post("/upload")
async def upload_pdf(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Please log in first")
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Setup user directory
    user_dir = os.path.join("uploads", user["email"])
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, file.filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Extract text
        pdf_reader = PyPDF2.PdfReader(file_path)
        full_text = ""
        for i, page in enumerate(pdf_reader.pages):
            text = page.extract_text() or ""
            full_text += f"\n--- [PAGE {i+1}] ---\n{text}\n"
        
        # Save to DB
        db_doc = DBDocument(
            filename=file.filename,
            file_path=file_path,
            content=full_text,
            user_id=user["id"]
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        
        # Set as active context
        active_contexts[user["email"]] = {
            "text": full_text,
            "filename": file.filename,
            "doc_id": db_doc.id
        }
        
        return {
            "message": "File uploaded and processed", 
            "id": db_doc.id,
            "filename": file.filename
        }
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

@app.get("/documents")
async def get_documents(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return []
    docs = db.query(DBDocument).filter(DBDocument.user_id == user["id"]).order_by(DBDocument.upload_date.desc()).all()
    return [{"id": d.id, "filename": d.filename, "date": d.upload_date.isoformat()} for d in docs]

@app.get("/documents/{doc_id}/context")
async def set_active_document(doc_id: int, request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401)
    
    doc = db.query(DBDocument).filter(DBDocument.id == doc_id, DBDocument.user_id == user["id"]).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    active_contexts[user["email"]] = {
        "text": doc.content,
        "filename": doc.filename,
        "doc_id": doc.id
    }
    
    # Return previous chat history for this doc
    chats = db.query(DBChat).filter(DBChat.document_id == doc_id).order_by(DBChat.timestamp.asc()).all()
    return {
        "filename": doc.filename,
        "history": [{"question": c.question, "answer": c.answer} for c in chats]
    }

@app.post("/ask")
async def ask_question(request_data: QuestionRequest, request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Please log in")

    context = active_contexts.get(user["email"])
    if not context:
        raise HTTPException(status_code=400, detail="No active document. Please select or upload one.")

    if not api_key and not nvidia_key:
        raise HTTPException(status_code=500, detail="No AI API keys configured.")

    sys_prompt = request_data.system_prompt if request_data.system_prompt else DEFAULT_SYSTEM_PROMPT
    full_prompt = f"{sys_prompt}\n\nDOCUMENT TEXT ({context['filename']}):\n{context['text'][:30000]}\n\nUSER QUESTION: {request_data.question}\n\nANSWER:"

    answer = "AI processing failed."
    # Try NVIDIA
    if nvidia_key:
        try:
            completion = nvidia_client.chat.completions.create(
                model="meta/llama-3.1-70b-instruct",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.2, max_tokens=1024,
            )
            answer = completion.choices[0].message.content.strip()
        except Exception: pass

    # Gemini Fallback
    if answer == "AI processing failed." and api_key:
        for model_name in ['gemini-1.5-flash', 'gemini-2.0-flash']:
            try:
                curr_model = genai.GenerativeModel(model_name)
                response = curr_model.generate_content(full_prompt)
                answer = response.text.strip()
                break
            except Exception: continue
    
    # Save Chat to History
    db_chat = DBChat(
        question=request_data.question,
        answer=answer,
        document_id=context["doc_id"],
        user_id=user["id"]
    )
    db.add(db_chat)
    db.commit()

    return {"answer": answer}

@app.get("/prompt/default")
async def get_default_prompt():
    return {"prompt": DEFAULT_SYSTEM_PROMPT}

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
