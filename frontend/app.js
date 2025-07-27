import { createApp, ref, nextTick, onMounted, onUnmounted } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.js'

// marked is loaded globally via a script tag in index.html
const { marked } = window

class AsyncQueue {
  constructor() {
    this.queue = [];
    this.resolvers = [];
  }

  enqueue(item) {
    if (this.resolvers.length > 0) {
      const resolve = this.resolvers.shift();
      resolve(item);
    } else {
      this.queue.push(item);
    }
  }

  dequeue() {
    return new Promise((resolve) => {
      if (this.queue.length > 0) {
        resolve(this.queue.shift());
      } else {
        this.resolvers.push(resolve);
      }
    });
  }
}

createApp({
  setup() {
    const lang = ref('zh')
    const userInput = ref('')
    const history = ref([])
    const speakingIndex = ref(-1)
    const recording = ref(false)
    const listening = ref(false)
    const typing = ref(false)
    const error = ref(null)
    const ttsMuted = ref(false)
    const videoEnabled = ref(false)
    const voices = ref([])
    const voice = ref('zh-CN-XiaoxiaoNeural')

    const historyEl = ref(null)
    const localVideo = ref(null)
    const remoteVideo = ref(null)

    // 音频
    let ws, audioCtx, localStream, workletNode
    let mediaSource, sourceBuffer, audioEl, mediaQueue = []
    let ttsStartTime = 0

    // 视频
    let pc, videoStream

    const DOWNSTREAM_MIME = 'audio/mpeg'

    function base64ToArrayBuffer(base64) {
      const binary = atob(base64)
      const len = binary.length
      const bytes = new Uint8Array(len)
      for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i)
      return bytes.buffer
    }

    function scrollToBottom() {
      nextTick(() => {
        if (historyEl.value) {
          historyEl.value.scrollTop = historyEl.value.scrollHeight
        }
      })
    }

    function resetMediaSourceForNewUtterance() {
      if (mediaSource && mediaSource.readyState === 'open') {
        try { mediaSource.endOfStream() } catch (e) { console.warn(e) }
      }
      mediaSource = new MediaSource()
      audioEl = new Audio()
      audioEl.autoplay = true
      audioEl.muted = ttsMuted.value
      audioEl.src = URL.createObjectURL(mediaSource)

      audioEl.onended = () => {
        speakingIndex.value = -1
        pendingBoundaries.queue = []
        if (ws && ws.readyState === WebSocket.OPEN && !listening.value) {
          ws.send(JSON.stringify({ type: 'resume' }))
          console.log("ws send resume")
          listening.value = true
        }
      }

      mediaQueue = []
      sourceBuffer = null

      mediaSource.addEventListener('sourceopen', () => {
        try {
          sourceBuffer = mediaSource.addSourceBuffer(DOWNSTREAM_MIME)
          sourceBuffer.mode = 'sequence'
          sourceBuffer.addEventListener('updateend', appendNextChunk)
          appendNextChunk() // 立即尝试消耗队列
        } catch (e) {
          console.error('[MediaSource] addSourceBuffer error:', e)
        }
      }, { once: true })
    }

    function finalizeMediaSource() {
      console.log("finalizeMediaSource start")
      if (!mediaSource || mediaSource.readyState !== "open" || listening.value)
        return
      if (sourceBuffer && (sourceBuffer.updating || mediaQueue.length > 0)) {
        sourceBuffer.addEventListener('updateend', finalizeMediaSource, {
          once: true
        })
        return
      }
      mediaSource.endOfStream()
      console.log("mediaSource endOfStream")
    }
    function appendNextChunk() {
      if (!sourceBuffer || sourceBuffer.updating) return
      if (mediaQueue.length > 0) {
        sourceBuffer.appendBuffer(mediaQueue.shift())
      }
    }

    function playTTSChunk(chunk) {
      if (!chunk || chunk.byteLength === 0) return
      if (!mediaSource) resetMediaSourceForNewUtterance()
      mediaQueue.push(new Uint8Array(chunk))
      if (sourceBuffer && !sourceBuffer.updating) {
        appendNextChunk()
      }
    }

    // 发送文本
    function onSendText() {
      if (!userInput.value.trim()) return
      history.value.push({ role: 'user', text: userInput.value })
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'llm_search', data: userInput.value }))
      }
      userInput.value = ''
      scrollToBottom()
    }

    const pendingBoundaries = new AsyncQueue();

    async function waitUntil(timeSec) {
      while ((performance.now() / 1000) - ttsStartTime < timeSec) {
        await new Promise(requestAnimationFrame);
      }
    }

    (async () => {
      while (true) {
        const msg = await pendingBoundaries.dequeue();
        await waitUntil(msg.offset_sec);
        const m = history.value[speakingIndex.value];
        if (m) {
          m.text += msg.text;
          history.value = [...history.value];
          scrollToBottom()
        }
      }
    })();

    function onTTSBegin() {
      ttsStartTime = performance.now() / 1000
      resetMediaSourceForNewUtterance()
    }

    function onWordBoundary(msg) {
      pendingBoundaries.enqueue(msg);
    }

    function onTTSEnd() {
      finalizeMediaSource()
    }

    // 音频主入口
    async function startCall() {
      history.value = []
      recording.value = true
      listening.value = true
      error.value = null
      scrollToBottom()

      ws = new WebSocket(`ws://${location.host}/ws/audio`)
      ws.binaryType = 'arraybuffer'
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'voice', data: voice.value }))
      }

      ws.onclose = () => { stopCall() }
      ws.onerror = (e) => { error.value = (lang.value === 'zh' ? 'WebSocket错误' : 'WebSocket error'); console.error(e) }

      ws.onmessage = (e) => {
        if (typeof e.data !== 'string') return
        const msg = JSON.parse(e.data)
        switch (msg.type) {
          case 'asr_text':
            history.value.push({ role: 'user', text: msg.data })
            listening.value = false
            scrollToBottom()
            break
          case 'llm_begin':
            history.value.push({ role: 'bot', text: '' })
            speakingIndex.value = history.value.length - 1
            listening.value = false
            scrollToBottom()
            break
          case 'llm_delta': {
            const m = history.value[speakingIndex.value]
            if (m) {
              m.text += msg.data
              history.value = [...history.value]
              scrollToBottom()
            }
            break
          }
          case 'llm_end':
            break
          case 'tts_begin':
            onTTSBegin()
            break
          case 'tts_audio':
            playTTSChunk(base64ToArrayBuffer(msg.data))
            break
          case 'tts_boundary':
            onWordBoundary(msg)
            break
          case 'tts_end':
            onTTSEnd()
            break
          case 'error':
            error.value = msg.data
            break
        }
      }

      audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 })
      await audioCtx.audioWorklet.addModule('/static/pcm-processor.js')
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const source = audioCtx.createMediaStreamSource(localStream)

      workletNode = new AudioWorkletNode(audioCtx, 'pcm-processor', { numberOfInputs: 1, numberOfOutputs: 0 })
      workletNode.port.onmessage = (ev) => {
        if (ws && ws.readyState === WebSocket.OPEN && listening.value) {
          ws.send(ev.data.buffer || ev.data)
        }
      }
      source.connect(workletNode)
      if (audioCtx.state === 'suspended') await audioCtx.resume()
    }

    async function stopCall() {
      ws && ws.readyState === WebSocket.OPEN && ws.close()
      ws = null
      workletNode && workletNode.disconnect()
      workletNode = null
      localStream?.getTracks().forEach(t => t.stop())
      localStream = null

      if (audioCtx && audioCtx.state !== 'closed') {
        await audioCtx.close()
      }
      audioCtx = null

      if (mediaSource && mediaSource.readyState === "open") mediaSource.endOfStream()
      mediaSource = null
      sourceBuffer = null
      audioEl = null
      mediaQueue = []

      recording.value = false
      listening.value = false
    }


    function toggleTTS() {
      ttsMuted.value = !ttsMuted.value
      if (audioEl) audioEl.muted = ttsMuted.value
    }
    function onVoiceChange() {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'voice', data: voice.value }))
      }
    }
    async function toggleMic() {
      if (recording.value) stopCall()
      else {
        try { await startCall() }
        catch (err) {
          console.error(err)
          error.value = err?.message || String(err)
          recording.value = false
        }
      }
    }

    // 视频
    async function startVideo() {
      if (videoEnabled.value) return
      videoEnabled.value = true
      await nextTick()
      try {
        videoStream = await navigator.mediaDevices.getUserMedia({ video: true })
        if (videoEnabled.value) {
          localVideo.value.srcObject = videoStream
        }
        pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
        videoStream.getTracks().forEach(t => pc.addTrack(t, videoStream))
        pc.ontrack = ev => {
          if (ev.track.kind === 'video') {
            //remoteVideo.value.srcObject = ev.streams[0]
          }
        }
        const offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        const resp = await fetch('/rtc/offer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sdp: pc.localDescription.sdp, type: pc.localDescription.type })
        })
        const answer = await resp.json()
        await pc.setRemoteDescription(answer)
      } catch (err) {
        console.error(err)
        error.value = err?.message || String(err)
        videoEnabled.value = false
      }
    }

    function stopVideo() {
      videoStream?.getTracks().forEach(t => t.stop())
      pc && pc.close()
      localVideo.value.srcObject = null
      //remoteVideo.value.srcObject = null
      videoEnabled.value = false
    }
    async function toggleVideo() { if (videoEnabled.value) stopVideo(); else await startVideo() }


    onMounted(async () => {
      startCall()
      const resp = await fetch('/api/voices')
      voices.value = await resp.json()
    })

    onUnmounted(() => {
    })

    return {
      lang, userInput, history, recording, listening, typing, error,
      toggleMic, toggleTTS, onSendText, onVoiceChange,
      historyEl, ttsMuted, localVideo, remoteVideo, videoEnabled, toggleVideo,
      voices, voice, speakingIndex,
      marked
    }
  }
}).mount('#app')
