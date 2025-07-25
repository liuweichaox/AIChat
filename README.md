# Mumu AI Voice Demo

This example shows a simple ChatGPT-like voice conversation. Audio is streamed
between the browser and server using WebRTC. Each audio segment is saved to the
`recordings/` directory before being transcribed. Speech synthesized by the TTS
service is stored under `tts_recordings/` for later playback.

## Setup

Install the dependencies:

```bash
pip install -r requirements.txt
```

The `aiortc` package is required for WebRTC support. If installation fails,
ensure the system packages needed by `aiortc` (e.g. FFmpeg libraries and build
tools) are available. Refer to the `aiortc` documentation for details.

## Running

Set the `BIGMODEL_API_KEY` environment variable to your Zhipu API key before running.

Run the API server:

```bash
export BIGMODEL_API_KEY=<your-api-key>
python main.py
```

Open `http://localhost:8000/` in the browser and allow microphone access.
