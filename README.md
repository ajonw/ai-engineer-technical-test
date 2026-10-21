# AI Engineer Coding Test


## Run the application

**Requirements:** Docker Desktop (or Docker Engine with Compose).

From the project folder:

```bash
docker compose up --build -d
```

Open **http://localhost:8000** to upload food receipts and ask questions. API documentation is at **http://localhost:8000/docs**.

Example questions after uploading receipts:

- What food did I buy yesterday?
- Give me total expenses for food on 20 June 2026.
- Where did I buy hamburger from last 7 days?

The **Ask (SQL tools)** option works without an LLM. **Ask via Ollama** is optional and needs a running Ollama server and the `OLLAMA_URL` setting in the API container.


## Run the CSV analysis

**Requirement:** Python 3.12 or later. Keep the original customer CSV files on your computer; they are not needed by the receipt application.

From the project folder, adjust the paths to your CSV files:

```bash
python scripts/profile_memory.py csv/customers-100000.csv --output reports/small.json
python scripts/profile_memory.py csv/customers-2000000.csv --output reports/large.json
```

The reports contain row counts, missing values, sampled category statistics, numeric statistics, processing time, and peak process memory. See `docs/CSV_RESULTS.md` for the results from both datasets.

## Project files

| File or folder | Purpose |
| --- | --- |
| `app/main.py` | FastAPI web interface and API endpoints |
| `app/receipt.py` | OCR and receipt-field extraction |
| `app/db.py` | SQLite receipt and item storage |
| `app/qa.py` | SQL queries for food, expenses, and merchants |
| `app/agent.py` | Optional Ollama tool selection |
| `app/vector.py` | Qdrant vector indexing/search and manual cosine similarity |
| `csv_insights.py` | Streaming CSV parser and statistics |
| `scripts/profile_memory.py` | CSV processing-time and memory measurements |
| `docs/CSV_RESULTS.md` | Findings from the 100K and 2M CSV files |
| `ANSWERS.md` | Written answers to the engineering questions |
| `Dockerfile` | FastAPI application container image |
| `docker-compose.yml` | Runs the API and Qdrant services |
| `.github/workflows/ci.yml` | GitHub Actions Docker image build |

**Data storage:** SQLite saves receipt details; Qdrant stores receipt vectors for search. Generated CSV reports are saved under `reports/`. Do not commit original customer CSVs or personal receipts to a public repository.
