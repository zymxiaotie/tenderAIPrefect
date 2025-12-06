# main.py
import hashlib
import uuid
from pathlib import Path
from typing import List
import fitz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from jinja2 import Environment, FileSystemLoader
from prefect import flow, task, serve
from prefect.events import EventTrigger
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from prompts import MASTER_PROMPT_V2
from parser import parse_markdown_table
from models import QSCriterion
from context_builder import build_context
from utils.db import init_db_pool, get_db
from config import Config, LLMProvider
import structlog
import argparse

# LLM Client
def get_llm_client(provider: LLMProvider, model: str, openai_key: str, gemini_key: str, xai_key: str):
    if provider == LLMProvider.OPENAI:
        from openai import OpenAI
        return OpenAI(api_key=openai_key)
    elif provider == LLMProvider.GROK:
        from openai import OpenAI
        return OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
    elif provider == LLMProvider.GEMINI:
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        return genai.GenerativeModel(model)
    elif provider == LLMProvider.OLLAMA:
        import ollama
        return ollama
    raise ValueError(f"Unsupported LLM provider: {provider}")

# Init
config = Config()
init_db_pool()
llm_client = get_llm_client(config.LLM_PROVIDER, config.LLM_MODEL, config.OPENAI_API_KEY, config.GEMINI_API_KEY, config.XAI_API_KEY)
embedder = SentenceTransformer(config.EMBEDDING_MODEL)
env = Environment(loader=FileSystemLoader("templates"))
splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
structlog.configure(processors=[structlog.processors.JSONRenderer()])
logger = structlog.get_logger()

def llm_chat(provider: LLMProvider, client, model: str, messages: List[dict], max_tokens: int = 3000) -> str:
    prompt = messages[-1]["content"]
    try:
        if provider in [LLMProvider.OPENAI, LLMProvider.GROK]:
            resp = client.chat.completions.create(model=model, messages=messages, temperature=0.0, max_tokens=max_tokens)
            return resp.choices[0].message.content.strip()
        elif provider == LLMProvider.GEMINI:
            response = client.generate_content(prompt)
            return response.text.strip()
        elif provider == LLMProvider.OLLAMA:
            resp = client.chat(model=model, messages=messages)
            return resp['message']['content'].strip()
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return ""

@task(retries=2, retry_delay_seconds=10)
def download_pdf(file_id: str, file_name: str) -> Path:
    creds = service_account.Credentials.from_service_account_file(config.GOOGLE_CREDENTIALS_FILE, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    service = build("drive", "v3", credentials=creds)
    path = Path("downloads") / file_name
    path.parent.mkdir(exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    with path.open("wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
    return path

@task
def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    text = "\n\n".join(p.get_text() for p in doc)
    doc.close()
    return text

@task
def extract_criteria(text: str) -> List[QSCriterion]:
    chunks = [c.page_content for c in splitter.create_documents([text])]
    all_criteria = []
    messages = [{"role": "user", "content": ""}]
    for chunk in chunks:
        messages[-1]["content"] = MASTER_PROMPT_V2.replace("[PASTE FULL EXTRACTED TEXT HERE]", chunk)
        raw = llm_chat(config.LLM_PROVIDER, llm_client, config.LLM_MODEL, messages)
        try:
            all_criteria.extend(parse_markdown_table(raw))
        except:
            continue
    seen = set()
    uniq = []
    for c in all_criteria:
        key = (c.tag_name, c.extracted_clause[:100])
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq

@task
def infer_is_met(criteria: List[QSCriterion], tender_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        for c in criteria:
            # GIN first
            cur.execute(
                "SELECT is_met, notes FROM company_knowledge "
                "WHERE search_text @@ plainto_tsquery('english', %s) "
                "ORDER BY ts_rank(search_text, plainto_tsquery('english', %s)) DESC LIMIT 1",
                (c.extracted_clause, c.extracted_clause)
            )
            match = cur.fetchone()
            if match:
                is_met = match[0]
                notes = match[1]
            else:
                # LLM backup
                messages = [{"role": "user", "content": f"Does the company meet this criterion: {c.extracted_clause}? Company knowledge: [all knowledge descriptions]"}]
                raw = llm_chat(config.LLM_PROVIDER, llm_client, config.LLM_MODEL, messages, 200)
                is_met = 'yes' in raw.lower()
                notes = raw[:500]

            # Save
            cur.execute(
                "UPDATE tender_qualification_criteria SET is_met=%s, notes=%s "
                "WHERE tender_id=%s AND tag_id=(SELECT tag_id FROM criteria_register WHERE tag_name=%s)",
                (is_met, notes, tender_id, c.tag_name)
            )
        conn.commit()

@task
def justify_criteria(tender_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT tqc.raw_text, tqc.is_met, tqc.notes FROM tender_qualification_criteria tqc WHERE tender_id=%s",
            (tender_id,)
        )
        rows = cur.fetchall()
        for raw, is_met, notes in rows:
            messages = [{"role": "user", "content": f"Criterion: {raw}. Met: {is_met}. Notes: {notes}. Justify in 2-4 sentences, and list actions if needed."}]
            raw_just = llm_chat(config.LLM_PROVIDER, llm_client, config.LLM_MODEL, messages, 300)
            try:
                just = json.loads(raw_just)
                justification = just["justification"]
                actions = json.dumps(just["actions"])
            except:
                justification = raw_just
                actions = "[]"
            cur.execute(
                "UPDATE tender_qualification_criteria SET justification=%s, actions=%s "
                "WHERE tender_id=%s AND raw_text=%s",
                (justification, actions, tender_id, raw)
            )
        conn.commit()

@flow
def process_tender(file_id: str, file_name: str, file_hash: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM gdrive_file_tracking WHERE file_hash=%s AND processing_status='completed'", (file_hash,))
        if cur.fetchone():
            logger.info(f"Already processed: {file_name}")
            return
        cur.execute(
            "INSERT INTO gdrive_file_tracking (gdrive_file_id, file_name, file_path, file_hash, processing_status) VALUES (%s,%s,%s,%s,'processing') "
            "ON CONFLICT DO UPDATE SET processing_status='processing'",
            (file_id, file_name, f"downloads/{file_name}", file_hash)
        )
        cur.execute(
            "INSERT INTO tenders (tender_title, tender_reference_number) VALUES (%s, %s) "
            "ON CONFLICT (tender_reference_number) DO UPDATE SET tender_title=EXCLUDED.tender_title "
            "RETURNING tender_id",
            (file_name, file_name)
        )
        tender_id = cur.fetchone()[0]

    pdf_path = download_pdf(file_id, file_name)
    text = extract_text(pdf_path)
    criteria = extract_criteria(text)
    infer_is_met(criteria, tender_id)
    justify_criteria(tender_id)

    context = build_context(tender_id)
    html = env.get_template("report.html").render(**context)
    path = Path("outputs") / f"report_{file_name}_{uuid.uuid4().hex[:8]}.html"
    path.write_text(html)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE gdrive_file_tracking SET processing_status='completed', tender_id=%s WHERE file_hash=%s", (tender_id, file_hash))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-pdf", type=str)
    args = parser.parse_args()
    if args.local_pdf:
        path = Path(args.local_pdf)
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        process_tender("local", path.name, file_hash)
    else:
        process_tender.serve(
            name="gdrive-tender-processor",
            trigger=EventTrigger(events=["gdrive.pdf_uploaded"], parameters={"file_id": "{{ event.payload.file_id }}", "file_name": "{{ event.payload.file_name }}", "file_hash": "{{ event.payload.file_hash }}"})
        )