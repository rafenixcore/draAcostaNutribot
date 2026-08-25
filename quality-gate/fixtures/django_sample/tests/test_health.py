from django.test import Client

client = Client()


def test_health():
    assert client.get("/health").status_code == 200
