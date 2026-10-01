

# ── harness: tests through the doc's other fixtures (each one's responses are requested) ─────────────
import httpx  # noqa: E402


def test_harness_s3_upload_then_download(mock_s3: HTTPXMock) -> None:
    with httpx.Client() as client:
        put = client.put("https://test-bucket.s3.amazonaws.com/a/b.txt", content=b"data")
        assert put.headers["ETag"] == '"test-etag"'
        assert client.get("https://test-bucket.s3.amazonaws.com/a/b.txt").content == b"file content here"


def test_harness_s3_upload_only(mock_s3: HTTPXMock) -> None:
    with httpx.Client() as client:
        assert client.put("https://test-bucket.s3.amazonaws.com/x", content=b"1").status_code == 200


def test_harness_openai(mock_openai: HTTPXMock) -> None:
    with httpx.Client() as client:
        body = client.post("https://api.openai.com/v1/chat/completions", json={"model": "x"}).json()
    assert body["choices"][0]["message"]["content"] == "Mock response."


def test_harness_anthropic(mock_anthropic: HTTPXMock) -> None:
    with httpx.Client() as client:
        body = client.post("https://api.anthropic.com/v1/messages", json={"model": "x"}).json()
    assert body["content"][0]["text"] == "Mock response."
