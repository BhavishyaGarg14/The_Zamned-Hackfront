from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from neo4j_graph import upsert_raw_debits
from pdf_parser import extract_debits_from_pdf
from routers.auth import get_current_user
from store import get_commitments

router = APIRouter(prefix="/api/upload", tags=["upload"])
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("")
def upload_statement(file: UploadFile = File(...), username: str = Depends(get_current_user)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF bank statement.")

    pdf_bytes = file.file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds 10 MB limit.")

    try:
        rows = extract_debits_from_pdf(pdf_bytes)
        if not rows:
            raise HTTPException(status_code=422, detail="No debit transactions found in this PDF.")

        inserted = upsert_raw_debits(rows, username=username, source_name=file.filename)
        commitments = get_commitments(username, refresh=True)
        return {
            "status": "ok",
            "filename": file.filename,
            "extracted_debits": inserted,
            "active_commitments": len(commitments),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
