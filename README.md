# Mumu AI Voice Demo

This example shows a simple ChatGPT-like voice conversation. Audio is streamed
between the browser and server using WebRTC, and a separate WebSocket channel
handles control messages such as interrupting text-to-speech playback.

## Setup

Install the dependencies:

```bash
pip install -r requirements.txt
```

The `aiortc` package is required for WebRTC support. If installation fails,
ensure the system packages needed by `aiortc` (e.g. FFmpeg libraries and build
tools) are available. Refer to the `aiortc` documentation for details.

## Running

Run the API server:

```bash
python main.py
```

Open `http://localhost:8000/` in the browser and allow microphone access.
