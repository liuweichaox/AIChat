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

Open `http://localhost:8000/` in the browser and allow microphone access.
Click the **Video** button to establish a WebRTC connection and stream your webcam to the server. You can switch the video on or off without affecting the voice conversation.
