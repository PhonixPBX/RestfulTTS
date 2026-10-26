import re


def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert 'hx-post="/ui/synthesize"' in r.text
    assert "Thorsten" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]


def test_voices_partial(client):
    r = client.get("/ui/voices", params={"language": "en"})
    assert re.search(r'value="af_heart"[^>]* selected', r.text)
    assert "thorsten" not in r.text


def test_synthesize_partial_and_history(client):
    r = client.post("/ui/synthesize", data={"text": "Hallo", "language": "de", "voice": "thorsten", "format": "ulaw"})
    assert r.status_code == 200
    assert r.headers["hx-trigger"] == "history-changed"
    assert re.search(r'<audio[^>]+src="/api/v1/audio/[0-9a-f]{64}\.wav"', r.text)
    assert re.search(r'href="/api/v1/audio/[0-9a-f]{64}\.ulaw"', r.text)
    assert "Hallo" in client.get("/ui/history").text


def test_synthesize_partial_error(client):
    r = client.post("/ui/synthesize", data={"text": "", "language": "de"})
    assert r.status_code == 422
    assert "alert-danger" in r.text


def test_login_flow_and_csrf(secured):
    assert secured.get("/", follow_redirects=False).headers["location"] == "/login"
    assert secured.get("/ui/history", headers={"HX-Request": "true"}).headers["hx-redirect"] == "/login"
    assert secured.post("/login", data={"token": "nope"}).status_code == 401

    r = secured.post("/login", data={"token": "s3cret"}, follow_redirects=False)
    assert r.status_code == 303
    page = secured.get("/")
    assert page.status_code == 200
    csrf = re.search(r'name="csrf-token" content="([0-9a-f]+)"', page.text).group(1)

    data = {"text": "Hallo", "language": "de"}
    assert secured.post("/ui/synthesize", data=data, follow_redirects=False).status_code == 303
    assert secured.post("/ui/synthesize", data=data, headers={"X-CSRF-Token": csrf}).status_code == 200
    # the UI session also opens the REST API, the audio player loads /api/v1/audio/...
    assert secured.get("/api/v1/voices").status_code == 200


def test_delete_from_history(client):
    client.post("/ui/synthesize", data={"text": "Weg damit", "language": "de"})
    page = client.get("/").text
    key = re.search(r'hx-delete="/ui/audio/([0-9a-f]{64})"', page).group(1)
    r = client.delete(f"/ui/audio/{key}")
    assert r.status_code == 200
    assert "Weg damit" not in r.text
    assert "Noch nichts erzeugt." in r.text
