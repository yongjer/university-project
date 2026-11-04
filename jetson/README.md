# voice-robot (Jetson controller)

Turns speech or text into motion commands and runs them on the Arduino firmware
over serial.

```text
audio -> ASR (ai_server) -> intent parser -> RobotController -> RobotLink -> Arduino
```

## Quick start (no hardware needed)

The default configuration uses `MockLink`, an in-process emulation of the firmware.

```bash
uv sync
uv run voice-robot run "move forward 2 seconds then turn right for half a second"
uv run voice-robot serve
```

```bash
curl -X POST localhost:8000/command/text -H 'Content-Type: application/json' \
  -d '{"text": "forward 3 seconds then turn right 2 seconds"}'
curl -X POST localhost:8000/stop
```

Interactive API docs are at <http://localhost:8000/docs>.

## HTTP API

| Endpoint | Purpose |
| :--- | :--- |
| `GET /health` | Link state, firmware version, active backends |
| `POST /command/text` | `{"text": "...", "execute": true}`; `execute: false` only parses |
| `POST /command/audio` | Multipart `file` plus optional `execute`; needs the `asr` extra and a running ASR container |
| `POST /stop` | Emergency stop; returns 503 if the firmware did not confirm it |

The command endpoints respond when the plan has finished. A new plan replaces the
one that is running, and `/stop` interrupts it from another request.

The API has no authentication and binds to `0.0.0.0` by default: anyone who can
reach the port can move the robot. Use it on a trusted network, or set
`ROBOT_HOST=127.0.0.1`.

## Configuration

Set `ROBOT_*` environment variables or a `.env` file. See
[`config.py`](src/voice_robot/config.py) for all options.

| Variable | Default | Meaning |
| :--- | :--- | :--- |
| `ROBOT_LINK` | `mock` | `serial` talks to the real board |
| `ROBOT_SERIAL_PORT` | `/dev/ttyUSB0` | Arduino serial port |
| `ROBOT_INTENT_BACKEND` | `rule` | `llm` uses an OpenAI-compatible server, falling back to `rule` on any error |
| `ROBOT_LLM_BASE_URL` | `http://localhost:11434/v1` | Ollama, vLLM, llama.cpp, OpenAI |
| `ROBOT_LLM_MODEL` | `qwen2.5:3b-instruct` | Model name on that server |
| `ROBOT_ASR_URL` | `http://localhost:7860` | ASR container; an empty value disables audio input |

Audio input needs `gradio_client`:

```bash
uv sync --extra asr
```

## Development

```bash
uv run pytest
uv run ruff check .
```
