# ResuMatch — AI Resume Analyzer, ATS Optimizer & Bulk Candidate Screening

ResuMatch is a full-stack AI-powered resume analysis and candidate screening platform built with **Flask, React, SQLite, and Python-based ML evaluation**. It supports bulk PDF/DOCX resume processing, job-description matching, evidence-based scoring, candidate comparison, improvement suggestions, analysis history, and PDF/CSV report generation.

> **Scoring disclaimer:** The match score is an internal estimate of relevance to a job description. It is not an official ATS score, interview probability, or hiring recommendation. A missing keyword means it was not found in the extracted resume text, not necessarily that the candidate lacks the skill.

## Folder Structure

```text
resumatch/
├── backend/       # Flask REST API, SQLite, tests, run.py, seed_jobs.py
├── frontend/      # React 18, Vite, UI components, pages, API client
├── dataset/       # Skill taxonomy, job descriptions, synthetic resumes, labels
├── ml/            # Evaluation script and results
├── .env.example
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm
- Optional: Tesseract OCR for scanned PDFs
- Optional: Gemini API key for AI-generated improvement suggestions

## Installation and Setup

### Backend — Flask REST API

Run these commands from the project root in Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\.env.example .env
python seed_jobs.py
python run.py
```

The backend API runs at `http://127.0.0.1:5000`.

The SQLite database and uploaded files are created automatically in `backend/data/` during initialization.

### Frontend — React and Vite

Open a second terminal from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. Vite proxies `/api` requests to the Flask backend.

## Core Features

- **Bulk Resume Processing:** Upload and analyze multiple PDF/DOCX resumes against a selected job description.
- **ATS-Oriented Matching:** Calculate relevance scores using skill coverage, keyword matching, experience evidence, and text similarity.
- **Evidence-Based Scoring:** Display matched, partially matched, and not-found skills with supporting resume evidence.
- **Candidate Comparison:** Compare analyzed candidates and export comparison results.
- **Resume Improvement:** Generate actionable suggestions using deterministic rules or optional Gemini API integration.
- **Analysis History:** Review previous batches, candidate results, and dashboard statistics.
- **Reporting and Export:** Generate candidate PDF reports and export batch or comparison data to CSV.
- **Error Handling:** Handle invalid files, duplicate resumes, failed processing, and retry operations.
- **Job Description Management:** Create, search, update, and delete job descriptions through the REST API.

## Dataset

The project includes a **fully synthetic dataset** for development and evaluation. It contains no real candidate information.

| File or Directory | Description |
|---|---|
| `skills_taxonomy.csv` | Approximately 100 skills, categories, synonyms, and related terms |
| `job_descriptions.csv` | Six sample job descriptions covering backend, frontend, data science, data analysis, DevOps, and marketing |
| `synthetic_resumes/` | 24 synthetic PDF/DOCX resumes across six roles and three strength levels |
| `labels.csv` | Role and level labels used for evaluation |
| `edge_cases/` | Corrupt DOCX, fake PDF, empty PDF, text-less PDF, and duplicate resume files |

Regenerate the dataset from the project root:

```powershell
python dataset/generate_dataset.py
```

Dataset generation requires `reportlab` and `python-docx`.

## Resume Matching and Scoring Methodology

The matching engine calculates a weighted relevance score from applicable components. The component weights are defined in `backend/app/matching.py` and renormalized when a component does not apply.

| Component | Weight | Evaluation Criteria |
|---|---:|---|
| Required Skill Coverage | 40% | Exact matches receive full credit, partial matches receive half credit, and not-found skills receive zero |
| Preferred Skill Coverage | 10% | Coverage of preferred skills using the same matching rules |
| Experience Evidence | 20% | Required skills supported by the resume's experience section |
| Project and Education Evidence | 10% | Skills evidenced in projects, education, or certifications |
| Job Keyword Coverage | 10% | Coverage of important non-skill keywords from the job description |
| Text Relevance | 10% | TF-IDF cosine similarity, scaled and capped at 1 |

### Skill Matching Categories

- **Exact Match:** The skill is explicitly identified in the extracted resume text.
- **Synonym Match:** A recognized synonym from the skill taxonomy is detected.
- **Semantic Match:** A related term or sufficiently similar TF-IDF sentence is detected; this receives partial credit.
- **Not Found:** No supported match is detected in the extracted resume text.

Parsing quality and evidence coverage are reported separately from the relevance score. The skill taxonomy is limited and manually defined, so semantic matching can produce false positives and false negatives.

## Machine Learning Evaluation

Run the evaluation script from the project root:

```powershell
python ml\evaluate.py
```

The script evaluates synthetic resumes against the sample job descriptions and reports **ROC-AUC** and **Precision@K** metrics. Results are saved in `ml/results.json`.

> **Evaluation limitation:** The synthetic resumes and matching engine share the same skill taxonomy. High evaluation metrics demonstrate pipeline behavior on this constructed dataset, not generalization or predictive accuracy on real-world resumes.

## API Endpoints

All endpoints are available under `/api`. JSON errors use the structure `{"error":{"code","message"}}`.

| Method and Endpoint | Functionality |
|---|---|
| `GET /health` | API health check |
| `GET/PUT /settings` | Read and update application settings |
| `POST /settings/purge` | Delete stored application data |
| `GET/POST /jobs` | List and create job descriptions |
| `GET/PUT/DELETE /jobs/<id>` | Retrieve, update, or delete a job description |
| `POST /batches` | Upload and process a resume batch |
| `GET /batches/<id>` | Retrieve batch status |
| `GET /batches/<id>/results` | Retrieve ranked candidate results |
| `POST /batches/<id>/retry` | Retry failed resume processing |
| `DELETE /batches/<id>` | Delete a batch |
| `GET /batches/<id>/export.csv` | Export batch results |
| `GET /candidates` | Search and filter candidates |
| `GET/DELETE /candidates/<id>` | Retrieve or delete a candidate |
| `GET /candidates/<id>/file` | Access an uploaded resume |
| `POST /candidates/<id>/report` | Generate a candidate PDF report |
| `POST /candidates/<id>/improve` | Generate resume improvement suggestions |
| `POST /compare` | Compare analyzed candidates |
| `POST /compare/export` | Export candidate comparison data |
| `POST /versions/compare` | Compare analyzed resume versions |
| `GET /history` | Retrieve paginated batch history |
| `GET /dashboard` | Retrieve dashboard statistics |
| `GET /reports` | List generated reports |
| `GET/DELETE /reports/<id>` | Retrieve or delete a report |
| `GET /reports/<id>/download` | Download a generated report |

## Gemini API Integration

Gemini integration is optional. Configure the following variables in `backend/.env`:

```env
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=your_supported_model
```

Use a model available to your API key. The API key remains on the backend, and email addresses and phone numbers are removed before resume text is sent to Gemini. When Gemini is not configured, the platform uses deterministic suggestions instead of presenting rule-based output as AI-generated content.

## Testing

Run the backend unit tests:

```powershell
cd backend
python -m unittest discover -s tests -v
```

## Troubleshooting

- **Backend connection failure:** Start the Flask server using `python run.py` before launching the frontend.
- **PowerShell script execution error:** Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` if appropriate for your environment.
- **Scanned PDF extraction failure:** Install Tesseract OCR and the optional `pytesseract` package.
- **Port conflict:** Update the backend port in `backend/run.py` and the corresponding proxy configuration in `frontend/vite.config.js`.

## Known Limitations

- No authentication; intended for trusted local use rather than multi-user production deployment.
- Batch cancellation is not implemented.
- Resume-version comparison requires both versions to have been analyzed first.
- Resume matching is heuristic and does not reproduce any employer-specific ATS.
- Multi-column PDF reading order may be inaccurate.
- Only the first 30 PDF pages are analyzed.
- Candidate names are extracted heuristically and may be reported as `Not detected`.
- Resume improvement suggestions do not export a modified DOCX file; accepted text must be copied from the improvement interface.
- OCR requires a separate Tesseract installation.

