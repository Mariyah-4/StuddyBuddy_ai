# StudySync AI — Smart Attendance Tracker & AI Study Companion

StudySync AI is a full-stack Flask web application for students. It combines attendance tracking, subject and syllabus management, saved AI-generated notes, an AI study chat, and a study planner in one responsive dashboard.

## Features

- Registration, login/logout, password hashing, session management, and CSRF-protected forms.
- Per-user subjects with configurable attendance targets.
- Attendance records with date, Present/Absent status, topic covered, faculty, and class notes.
- Attendance percentages, missed/present counts, and the number of consecutive attended classes needed to reach a target.
- PDF, DOCX, and TXT syllabus upload with text extraction and extracted-text preview.
- Automatic AI note generation after upload when an OpenAI API key is configured; retry generation from the syllabus page.
- Persistent notes with search, subject filter, edit, favorite, delete, TXT download, and PDF download.
- AI study assistant with saved conversations and optional subject/syllabus/note context.
- Study tasks with subject, deadline, completion state, and delete actions.
- Responsive interface and GitHub-ready project files.

## Technology

Python 3.10+, Flask, Flask-Login, Flask-SQLAlchemy, Flask-WTF, SQLite, Bootstrap 5, OpenAI Python SDK, pypdf, python-docx, and ReportLab.

## Quick start (Windows PowerShell)

1. Install Python 3.10 or newer.
2. Extract this folder and open PowerShell in `studysync-ai`.
3. Create a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

5. Copy the environment example:

   ```powershell
   Copy-Item .env.example .env
   ```

6. Open `.env`. Replace `SECRET_KEY` with a long random value. To enable AI features, add your own API key to `OPENAI_API_KEY` and set `OPENAI_MODEL` to a model available to your account. Keep `.env` private.
7. Start the app:

   ```powershell
   python app.py
   ```

8. Open `http://127.0.0.1:5000` in your browser and register an account.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

The SQLite database is created under `instance/` at first run. Uploaded documents are stored in `uploads/` using server-generated names. Both are ignored by Git.

## OpenAI setup

- Create or access an OpenAI API account and obtain an API key through the official platform.
- Put the key in `.env` as `OPENAI_API_KEY=...`.
- Configure `OPENAI_MODEL` with a model available to your API account.
- Restart the app after changing environment variables.

AI use may incur API charges and requires API access. The rest of the application (attendance, subjects, uploads, and saved notes) works without AI configured. If AI generation fails, the syllabus remains saved and you can retry after fixing the configuration.

## GitHub upload

1. Make sure `.env` is not staged or committed.
2. Check that no private syllabus files, database, or API key are included.
3. Create a new repository on GitHub.
4. In this folder, run:

   ```bash
   git init
   git add .
   git commit -m "Build StudySync AI study companion"
   git branch -M main
   git remote add origin YOUR_GITHUB_REPOSITORY_URL
   git push -u origin main
   ```

Never put API keys or private student data in the repository.

## Run tests

```bash
pytest
```

The tests use a temporary SQLite database and do not call the real AI API.

## Project structure

```text
studysync-ai/
├── app.py
├── config.py
├── models.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── services/
│   ├── ai_service.py
│   ├── attendance_service.py
│   └── syllabus_service.py
├── templates/
├── static/
│   ├── css/style.css
│   └── js/
├── uploads/
└── tests/
```

## Screenshot placeholders

Add screenshots after running the application:

- `docs/screenshots/dashboard.png` — Dashboard and attendance overview.
- `docs/screenshots/attendance.png` — Attendance form and history.
- `docs/screenshots/syllabus-upload.png` — Syllabus uploader and extracted preview.
- `docs/screenshots/notes.png` — Saved notes library.
- `docs/screenshots/ai-chat.png` — AI study assistant.

## Important implementation notes

- This is a local-development starter project. Before public deployment, configure HTTPS, a strong production secret, secure cookie settings, production database/migrations, logging, backups, and appropriate request rate limits.
- AI note generation currently runs during the upload request and may take time for large files. For production, move long-running AI work to a background worker and show job status.
- Text extraction does not perform OCR on scanned PDFs. Use a text-based PDF, DOCX, or TXT file if a PDF has no selectable text.
- AI output is educational assistance and can contain errors; verify important information against official course materials.
