"""Container images pinned by digest. No :latest at runtime (spec §3)."""

IMAGES = {
    "trufflehog": "trufflesecurity/trufflehog@sha256:deb2af10659a488a14d262a323addcde099d99827a1cf1dc4e93c17915c39f08",
    "trivy": "aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969",
    "k6": "grafana/k6@sha256:5221b620a4f874faff6e32ba597aa667c058391fe4898b1c6f6377f062c6cdec",
    "postgres": "postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73",
    "redis": "redis:7-alpine@sha256:ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf",
}
