# Mumu AI Voice Demo

This example shows a simple ChatGPT-like voice conversation. Audio is streamed
between the browser and server using WebSockets. Each audio segment is saved to the
`recordings/` directory before being transcribed. Speech synthesized by the TTS
service is stored under `tts_recordings/` for later playback.

## Setup

Install the dependencies:

```bash
pip install -r requirements.txt
```

The server communicates with the browser over a WebSocket connection, so no
extra system packages are required.

## Running

Set the `BIGMODEL_API_KEY` environment variable to your Zhipu API key before running.

Run the API server:

```bash
export BIGMODEL_API_KEY=<your-api-key>
python main.py
```

Open `http://localhost:8000/` in the browser and allow microphone access. The
microphone starts automatically and the server listens for speech pauses before
running ASR, LLM and TTS.

Click the **Video** button if you want to stream your webcam. Video is received
only; the server does not echo the stream back to the browser.
