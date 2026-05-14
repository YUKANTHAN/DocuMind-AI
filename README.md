# DocuMind AI - Document Q&A System

DocuMind AI is a premium, AI-powered web application that allows users to upload PDF documents and ask questions strictly based on the content of those documents. It ensures accurate, grounded answers and prevents hallucinations.

## 🚀 Features

- **PDF Upload**: Easy upload with validation.
- **AI-Powered Q&A**: Powered by Gemini 1.5 Flash for fast and accurate processing.
- **Strict Grounding**: Answers are derived ONLY from the uploaded document.
- **"Not available in document"**: Handles cases where the information is missing.
- **Premium UI**: Modern dark-mode interface with glassmorphism and smooth animations.
- **Accurate Page Citations**: Uses explicit page markers to ensure the AI correctly identifies source pages.

## 🛠️ Tech Stack

- **Frontend**: HTML5, Vanilla CSS3, JavaScript (ES6+).
- **Backend**: Python, FastAPI.
- **PDF Processing**: PyPDF2.
- **AI Model**: Google Gemini 1.5 Flash.
- **Environment**: Python 3.13+.

## 🏗️ Architecture & Flow

1. **Upload**: User selects a PDF. The frontend sends it to the `/upload` endpoint.
2. **Extraction**: The backend uses `PyPDF2` to extract text from each page and stores it in memory.
3. **Questioning**: User asks a question. The frontend sends it to the `/ask` endpoint.
4. **Processing**: The backend constructs a strict prompt for Gemini, including the document text and specific grounding instructions.
5. **Response**: Gemini generates an answer or returns "Not available in document". The answer is displayed in a chat-like interface.

## 🧠 AI Approach & Prompt Design

### Prompt Engineering
The system uses a **Strict Grounding Prompt** to ensure reliability:
- **Instruction**: "Answer ONLY using the information found in the DOCUMENT TEXT."
- **Fallback**: "If the answer is not present in the document, you MUST respond with exactly: 'Not available in document'."
- **Constraint**: "Do NOT use any external knowledge or hallucinate facts."

### Handling Hallucinations
Hallucinations are handled through:
1. **Explicit Negative Constraints**: Telling the model what NOT to do.
2. **Verification Logic**: The system prompt forces the model to acknowledge the document limits.
3. **concise Output**: Reducing the chance of extra "fluff" that might contain hallucinated info.

## ⚙️ Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repository-link>
   cd "AI powered Doc QA System"
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API Key**:
   Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

4. **Run the Application**:
   ```bash
   python main.py
   ```
   Or using uvicorn:
   ```bash
   uvicorn main:app --reload
   ```

5. **Access the UI**:
   Open `http://localhost:8000` in your browser.

## ⚠️ Limitations

- **Context Window**: Large documents are truncated to 30,000 characters in this simple version to fit within model limits without a full vector database (RAG).
- **Text Extraction**: Scanned PDFs (images) might not work as this uses basic text extraction. OCR would be needed for those.

## 📈 Possible Improvements

- **Vector Database (ChromaDB/Pinecone)**: Implement full RAG for handling massive documents.
- **OCR Support**: Add `pytesseract` or Gemini's multimodal capabilities to read scanned PDFs.
- **Multi-PDF Support**: Allow querying across multiple documents.
- **Highlighting**: Use PDF.js to highlight exact source lines in the UI.
