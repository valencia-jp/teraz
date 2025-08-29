# teraz

This repository contains a static mirror of the Teraz site and a Flask
application that drives the exam flow.

## Running locally

```bash
cd spi_exam_flask_app
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=app.py
flask run -p 5050
```

Open <http://127.0.0.1:5050/exam/select-mode> to begin the exam flow.

## Health check

The server exposes a simple health endpoint:

```bash
curl http://127.0.0.1:5050/healthz
```

## Exam data

Question set JSON files are loaded from the following locations (first match
wins):

1. Directory specified by the `EXAM_DATA_DIR` environment variable
2. `exams/` at the repository root
3. `spi_exam_flask_app/data/exams`

