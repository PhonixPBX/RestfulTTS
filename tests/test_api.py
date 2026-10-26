import io

import soundfile as sf


def test_health_and_meta(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert {v["id"] for v in client.get("/api/v1/voices", params={"language": "it"}).json()} == {"if_sara", "im_nicola"}
    assert "ulaw" in {f["name"] for f in client.get("/api/v1/formats").json()}
    assert client.get("/api/v1/voices", params={"language": "xx"}).status_code == 422


def test_synthesize_wav_and_cache(client, engine):
    body = {"text": "Guten Tag", "language": "de"}
    r = client.post("/api/v1/synthesize", json=body)
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
    assert (r.headers["x-cache"], r.headers["x-voice"]) == ("miss", "thorsten")
    _, rate = sf.read(io.BytesIO(r.content))
    assert rate == 24000

    again = client.post("/api/v1/synthesize", json=body)
    assert again.headers["x-cache"] == "hit"
    assert again.content == r.content
    assert len(engine.calls) == 1


def test_telephony_format_reuses_master(client, engine):
    r = client.get("/api/v1/synthesize", params={"text": "Buongiorno a tutti", "language": "it", "format": "ulaw"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/basic"
    assert len(r.content) == 8000 * 0.3  # three words of 0.1 s at 8 kHz, 1 byte each
    client.get("/api/v1/synthesize", params={"text": "Buongiorno a tutti", "language": "it", "format": "alaw"})
    assert len(engine.calls) == 1


def test_validation(client):
    assert client.post("/api/v1/synthesize", json={"text": " ", "language": "de"}).status_code == 422
    assert client.post("/api/v1/synthesize", json={"text": "x" * 201, "language": "de"}).status_code == 413
    assert client.post("/api/v1/synthesize", json={"text": "x", "voice": "nobody"}).status_code == 422
    assert client.post("/api/v1/synthesize", json={"text": "x", "language": "de", "format": "mp3"}).status_code == 422
    assert client.post("/api/v1/synthesize", json={"text": "x", "language": "de", "speed": 3}).status_code == 422


def test_legacy_tts_defaults_to_thorsten(client):
    r = client.post("/tts", json={"text": "Ja hallo, wie geht's"})
    assert r.status_code == 200
    assert r.headers["x-voice"] == "thorsten"
    assert r.content[:4] == b"RIFF"
    assert client.post("/tts", json={"text": "Hello", "voice": "af_heart"}).headers["x-voice"] == "af_heart"


def test_audio_download_by_url(client):
    r = client.post("/api/v1/synthesize", json={"text": "Bonjour", "language": "fr", "format": "sln"})
    key = r.headers["content-disposition"].split("tts-")[1][:12]
    assert key
    assert client.get("/api/v1/audio/notahash.wav").status_code == 404
    assert client.get("/api/v1/audio/../../etc/passwd").status_code == 404


def test_cache_prune(client, settings):
    service = client.app.state.service
    service.cache.max_bytes = 30_000
    for i in range(5):
        client.post("/api/v1/synthesize", json={"text": f"Satz {i}", "language": "de"})
    files = [p for p in settings.cache_dir.glob("??/*") if p.suffix != ".json"]
    assert sum(p.stat().st_size for p in files) <= 30_000
    assert len(service.history()) == len(files)


def test_auth_required_when_token_set(secured):
    body = {"text": "Hallo", "language": "de"}
    assert secured.post("/api/v1/synthesize", json=body).status_code == 401
    assert secured.post("/tts", json=body, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert secured.post("/tts", json=body, headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_delete_audio_removes_all_formats(client, settings, engine):
    params = {"text": "Bitte löschen", "language": "de"}
    client.get("/api/v1/synthesize", params=params)
    client.get("/api/v1/synthesize", params={**params, "format": "ulaw"})
    master = client.app.state.service.history()[0]
    assert len(list(settings.cache_dir.glob("??/*"))) == 4  # wav + ulaw, each with .json

    assert client.delete(f"/api/v1/audio/{master['key']}.wav").status_code == 204
    assert list(settings.cache_dir.glob("??/*")) == []
    assert client.delete(f"/api/v1/audio/{master['key']}").status_code == 404
    assert client.delete("/api/v1/audio/notahash").status_code == 404

    client.get("/api/v1/synthesize", params=params)
    assert len(engine.calls) == 2  # synthesized again


def test_delete_requires_auth(secured):
    assert secured.delete("/api/v1/audio/" + "0" * 64).status_code == 401
