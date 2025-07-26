"""Shared audio and video buffers used by WebSocket and WebRTC handlers."""

# Raw PCM data collected from the browser. This is cleared after each speech
# segment finishes processing.
audio_buffer = bytearray()

# List of received video frames from the WebRTC track. Frames are stored until a
# speech pause is detected, then the list is cleared.
video_frames = []
