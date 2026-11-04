import asyncio
import sys
from types import SimpleNamespace

import pytest

from voice_robot.asr import ASRError, GradioASRClient, build_asr
from voice_robot.config import Settings


def install_gradio_client(monkeypatch, client_cls):
    module = SimpleNamespace(Client=client_cls, handle_file=lambda path: {"path": path})
    monkeypatch.setitem(sys.modules, "gradio_client", module)


def test_calls_the_transcribe_endpoint(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, url, verbose=True):
            self.url = url

        def predict(self, **kwargs):
            calls.append((self.url, kwargs))
            return "  forward three seconds \n"

    install_gradio_client(monkeypatch, FakeClient)

    text = asyncio.run(GradioASRClient("http://asr:7860", "English").transcribe("speech.wav"))

    assert text == "forward three seconds"
    assert calls == [
        (
            "http://asr:7860",
            {
                "audio_filepath": {"path": "speech.wav"},
                "src_lang": "English",
                "tgt_lang": "English",
                "pnc": False,
                "api_name": "/transcribe",
            },
        )
    ]


def test_missing_dependency_explains_how_to_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "gradio_client", None)

    with pytest.raises(ASRError, match="uv sync --extra asr"):
        asyncio.run(GradioASRClient("http://asr:7860").transcribe("speech.wav"))


def test_unreachable_server_names_the_url_and_retries_the_connection(monkeypatch):
    attempts = []

    class FakeClient:
        def __init__(self, url, verbose=True):
            attempts.append(url)
            raise ConnectionError("connection refused")

    install_gradio_client(monkeypatch, FakeClient)
    client = GradioASRClient("http://asr:7860")

    for _ in range(2):
        with pytest.raises(ASRError, match=r"http://asr:7860.*compose\.yaml"):
            asyncio.run(client.transcribe("speech.wav"))
    assert len(attempts) == 2


def test_empty_url_disables_asr():
    assert build_asr(Settings(_env_file=None, asr_url="")) is None
    assert isinstance(build_asr(Settings(_env_file=None)), GradioASRClient)
