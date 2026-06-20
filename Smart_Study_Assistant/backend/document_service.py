from pathlib import Path
from fastapi import UploadFile
from pypdf import PdfReader
from docx import Document


async def save_uploaded_file(file: UploadFile, upload_dir: Path) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    path = upload_dir / safe_name
    content = await file.read()
    path.write_bytes(content)
    return path


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)

    if suffix == ".docx":
        doc = Document(str(path))
        return "\n".join([p.text for p in doc.paragraphs])

    raise ValueError("Unsupported file type. Upload .txt, .pdf, or .docx only.")


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)