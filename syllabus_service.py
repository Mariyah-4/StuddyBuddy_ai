from pathlib import Path
from docx import Document
from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

def extract_text(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".txt":
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    if suffix == ".docx":
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    if suffix == ".pdf":
        reader = PdfReader(path)
        chunks = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        text = "\n".join(chunks).strip()
        if not text:
            raise ValueError("No selectable text was found. This may be a scanned PDF; please upload a text-based PDF or TXT/DOCX file.")
        return text
    raise ValueError("Unsupported file type. Upload a PDF, DOCX, or TXT file.")
