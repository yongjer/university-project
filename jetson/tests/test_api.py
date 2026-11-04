import asyncio

import httpx
import pytest

from voice_robot.asr import ASRError, StubASRClient
from voice_robot.config import Settings
from voice_robot.link import LINK_ERROR_PREFIX, MockLink
from voice_robot.server import create_app


def api(scenario, *, link=None, asr=None, **settings):
    """Run ``scenario(client, link)`` against an app with its lifespan active."""
    settings = {"asr_url": "", "ack_timeout_s": 0.2, **settings}
    link = link or MockLink(time_scale=0.01)
    app = create_app(Settings(_env_file=None, **settings), link=link, asr=asr)

    async def main():
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://robot")
        async with app.router.lifespan_context(app), client:
            return await scenario(client, link)

    return asyncio.run(main())


def test_health_reports_link_and_settings():
    async def scenario(client, _):
        return (await client.get("/health")).json()

    body = api(scenario)
    assert body["status"] == "ok"
    assert body["link"] == {
        "kind": "mock",
        "connected": True,
        "firmware": "voice-robot-fw/2.0.0 (mock)",
        "error": None,
    }
    assert body["busy"] is False
    assert body["settings"]["intent_backend"] == "rule"
    assert body["settings"]["asr_enabled"] is False


def test_health_never_exposes_the_llm_key():
    async def scenario(client, _):
        return (await client.get("/health")).text

    assert "sk-secret" not in api(scenario, llm_api_key="sk-secret")


def test_text_command_runs_the_whole_plan():
    async def scenario(client, link):
        response = await client.post(
            "/command/text", json={"text": "move forward 3 seconds then turn right 2 seconds"}
        )
        return response, list(link.received)

    response, received = api(scenario)

    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "rule"
    assert [c["action"] for c in body["commands"]] == ["forward", "right"]
    assert body["execution"]["status"] == "completed"
    assert [r["status"] for r in body["execution"]["results"]] == ["completed", "completed"]
    assert received == ["FORWARD 3000", "RIGHT 2000"]


def test_execute_false_only_parses():
    async def scenario(client, link):
        response = await client.post(
            "/command/text", json={"text": "forward 3 seconds", "execute": False}
        )
        return response.json(), list(link.received)

    body, received = api(scenario)

    assert [c["action"] for c in body["commands"]] == ["forward"]
    assert body["execution"] is None
    assert received == []


def test_unrelated_speech_moves_nothing_and_warns():
    async def scenario(client, link):
        response = await client.post("/command/text", json={"text": "good morning everyone"})
        return response.json(), list(link.received)

    body, received = api(scenario)

    assert body["commands"] == []
    assert "no robot command recognised" in body["warnings"]
    assert received == []


def test_empty_text_is_rejected():
    async def scenario(client, _):
        return (await client.post("/command/text", json={"text": ""})).status_code

    assert api(scenario) == 422


def test_stop_interrupts_a_running_request():
    async def scenario(client, link):
        running = asyncio.create_task(
            client.post(
                "/command/text",
                json={"text": "forward 10 seconds then turn left 10 seconds"},
            )
        )
        while "FORWARD 10000" not in link.received:
            await asyncio.sleep(0.001)
        stop = await client.post("/stop")
        return stop, await asyncio.wait_for(running, 1.0), list(link.received)

    stop, running, received = api(scenario, link=MockLink(time_scale=1.0))

    assert stop.status_code == 200
    execution = running.json()["execution"]
    assert execution["status"] == "stopped"
    assert [r["status"] for r in execution["results"]] == ["interrupted", "cancelled"]
    assert "LEFT 10000" not in received


def test_spoken_stop_interrupts_a_running_request():
    async def scenario(client, link):
        running = asyncio.create_task(
            client.post("/command/text", json={"text": "forward 10 seconds"})
        )
        while "FORWARD 10000" not in link.received:
            await asyncio.sleep(0.001)
        stop = await client.post("/command/text", json={"text": "stop"})
        return stop.json(), (await asyncio.wait_for(running, 1.0)).json()

    stop, running = api(scenario, link=MockLink(time_scale=1.0))

    assert stop["execution"]["status"] == "completed"
    assert running["execution"]["status"] == "stopped"


def test_stop_returns_503_when_firmware_does_not_confirm():
    class DeafLink(MockLink):
        def _handle(self, line):
            pass

    async def scenario(client, _):
        return (await client.post("/stop")).status_code

    assert api(scenario, link=DeafLink()) == 503


def test_commands_return_503_after_a_link_error():
    async def scenario(client, link):
        link._emit(f"{LINK_ERROR_PREFIX} device disconnected")
        await asyncio.sleep(0.01)
        command = await client.post("/command/text", json={"text": "forward 1 second"})
        parse_only = await client.post(
            "/command/text", json={"text": "forward 1 second", "execute": False}
        )
        health = await client.get("/health")
        return command, parse_only, health.json(), list(link.received)

    command, parse_only, health, received = api(scenario)

    assert command.status_code == 503
    assert "device disconnected" in command.json()["detail"]
    assert parse_only.status_code == 200
    assert health["status"] == "degraded"
    assert health["link"]["connected"] is False
    assert received == []


def test_audio_command_transcribes_and_executes():
    asr = StubASRClient("turn left for 2 seconds")

    async def scenario(client, link):
        response = await client.post(
            "/command/audio", files={"file": ("speech.wav", b"RIFF...", "audio/wav")}
        )
        return response, list(link.received)

    response, received = api(scenario, asr=asr)

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "turn left for 2 seconds"
    assert body["execution"]["status"] == "completed"
    assert received == ["LEFT 2000"]
    assert asr.calls[0].endswith(".wav")


def test_audio_upload_reaches_the_asr_client_intact():
    payload = b"\x00\x01audio-bytes" * 1000
    seen = {}

    class Recorder(StubASRClient):
        async def transcribe(self, audio_path):
            with open(audio_path, "rb") as audio:
                seen["bytes"] = audio.read()
            return ""

    async def scenario(client, _):
        return await client.post("/command/audio", files={"file": ("speech.webm", payload)})

    assert api(scenario, asr=Recorder()).status_code == 200
    assert seen["bytes"] == payload


def test_audio_execute_false_only_parses():
    async def scenario(client, link):
        response = await client.post(
            "/command/audio",
            files={"file": ("speech.wav", b"RIFF...")},
            data={"execute": "false"},
        )
        return response.json(), list(link.received)

    body, received = api(scenario, asr=StubASRClient("go up 1 second"))

    assert body["execution"] is None
    assert received == []


def test_audio_returns_503_when_disabled():
    async def scenario(client, _):
        return await client.post("/command/audio", files={"file": ("a.wav", b"x")})

    response = api(scenario)
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


def test_audio_returns_503_when_asr_fails_and_moves_nothing():
    class BrokenASR:
        async def transcribe(self, audio_path):
            raise ASRError("ASR container is down")

    async def scenario(client, link):
        response = await client.post("/command/audio", files={"file": ("a.wav", b"x")})
        return response, list(link.received)

    response, received = api(scenario, asr=BrokenASR())

    assert response.status_code == 503
    assert "ASR container is down" in response.json()["detail"]
    assert received == []


def test_audio_too_large_is_rejected():
    asr = StubASRClient("forward 1 second")

    async def scenario(client, _):
        return await client.post("/command/audio", files={"file": ("a.wav", b"x" * 11)})

    assert api(scenario, asr=asr, max_audio_bytes=10).status_code == 413
    assert asr.calls == []


@pytest.mark.parametrize("path", ["/command/text", "/stop"])
def test_lifespan_closes_the_link(path):
    link = MockLink(time_scale=0.01)

    async def scenario(client, _):
        await client.post(path, json={"text": "stop"})

    api(scenario, link=link)
    assert link.connected is False
