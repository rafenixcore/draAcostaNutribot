import subprocess

from django.http import JsonResponse

SECRET = "AKIAIOSFODNN7EXAMPLE"  # planted secret for quality-gate tests
DATABASE_URL = (
    "postgres://admin:sup3rsecret1@db:5432/app"  # planted secret (trufflehog)
)


def health(request):
    return JsonResponse({"status": "ok"})


def echo(request, value):
    # planted vuln: shell=True is flagged by semgrep curated rules
    out = subprocess.run(
        f"echo {value}", shell=True, capture_output=True, text=True, check=False
    )
    return JsonResponse({"stdout": out.stdout.strip()})
