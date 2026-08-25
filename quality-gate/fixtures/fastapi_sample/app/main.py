import subprocess

from fastapi import FastAPI

app = FastAPI()

SECRET_KEY = "AKIAIOSFODNN7EXAMPLE"  # planted secret for quality-gate tests
DATABASE_URL = (
    "postgres://admin:sup3rsecret1@db:5432/app"  # planted secret (trufflehog)
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/items/{item_id}")
def get_item(item_id: int):
    # planted vuln: shell=True is flagged by semgrep curated rules
    out = subprocess.run(
        f"echo {item_id}", shell=True, capture_output=True, text=True, check=False
    )
    return {"stdout": out.stdout.strip()}
