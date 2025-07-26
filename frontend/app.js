import { createApp, ref, nextTick, onMounted } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.js'

createApp({
  setup() {
    const lang = ref('zh')
    const userInput = ref('')
    const history = ref([])
    const recording = ref(false)
    const listening = ref(false)
    const typing = ref(false)
    const error = ref(null)
    const showSubtitles = ref(true)
    const ttsMuted = ref(false)
    const videoEnabled = ref(false)

    const historyEl = ref(null)
    const localVideo = ref(null)
    const remoteVideo = ref(null)

    // 音频
    let ws, audioCtx, localStream, workletNode
    let mediaSource, sourceBuffer, audioEl, mediaQueue = []
    // 视频
    let pc, videoStream

    const DOWNSTREAM_MIME = 'audio/mpeg'

    function scrollToBottom() {
      nextTick(() => {
        if (historyEl.value) {
          historyEl.value.scrollTop = historyEl.value.scrollHeight
        }
      })
    }

    function tokensToText(tokens) {
      if (!tokens) return ''
      return tokens.map(t => t.text).join('')
    }
    function renderMarkdown(text) {
      return window.marked.parse(text || '')
    }

    // 下行播放
    function resetMediaSourceForNewUtterance() {
      mediaSource = new MediaSource()
      audioEl = new Audio()
      audioEl.autoplay = true
      audioEl.muted = ttsMuted.value
      audioEl.src = URL.createObjectURL(mediaSource)
      audioEl.onended = () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resume' }))
        }
        listening.value = true
      }
      mediaQueue = []
      mediaSource.addEventListener('sourceopen', () => {
        sourceBuffer = mediaSource.addSourceBuffer(DOWNSTREAM_MIME)
        sourceBuffer.mode = 'sequence'
        sourceBuffer.addEventListener('updateend', appendNextChunk)
        appendNextChunk()
      })
    }
    function finalizeMediaSource() {
      if (mediaSource && mediaSource.readyState === 'open') {
        try { mediaSource.endOfStream() } catch (e) { }
      }
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
      appendNextChunk()
    }

    // 打字机效果
    function typeReply(text) {
      typing.value = true
      const msg = { role: 'bot', tokens: [], typing: true }
      history.value.push(msg)
      scrollToBottom()
      let i = 0
      const timer = setInterval(() => {
        msg.tokens.push({ id: msg.tokens.length, text: text[i] })
        scrollToBottom()
        i++
        if (i >= text.length) {
          clearInterval(timer)
          typing.value = false
          msg.typing = false
        }
      }, 30) // 速度略快
    }

    // 发送文本
    function onSendText() {
      if (!userInput.value.trim()) return
      history.value.push({ role: 'user', text: userInput.value })
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'text', data: userInput.value }))
      }
      userInput.value = ''
      scrollToBottom()
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

      ws.onclose = () => { stopCall() }
      ws.onerror = (e) => { error.value = (lang.value === 'zh' ? 'WebSocket错误' : 'WebSocket error'); console.error(e) }

      ws.onmessage = (e) => {
        if (typeof e.data === 'string') {
          const msg = JSON.parse(e.data)
          if (msg.type === 'asr_text') {
            history.value.push({ role: 'user', text: msg.data })
            listening.value = false
            scrollToBottom()
          } else if (msg.type === 'llm_reply') {
            listening.value = false
            typeReply(msg.data)
          } else if (msg.type === 'tts_begin') {
            listening.value = false
            resetMediaSourceForNewUtterance()
          } else if (msg.type === 'tts_end') {
            finalizeMediaSource()
          }
        } else {
          playTTSChunk(e.data)
        }
      }

      audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 })
      await audioCtx.audioWorklet.addModule('/static/pcm-processor.js')
      localStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const source = audioCtx.createMediaStreamSource(localStream)

      workletNode = new AudioWorkletNode(audioCtx, 'pcm-processor', { numberOfInputs: 1, numberOfOutputs: 0 })
      workletNode.port.onmessage = (ev) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(ev.data.buffer || ev.data)
        }
      }
      source.connect(workletNode)
      if (audioCtx.state === 'suspended') await audioCtx.resume()
    }

    async function stopCall() {
      try { ws && ws.readyState === WebSocket.OPEN && ws.close() } catch { }
      ws = null
      try { workletNode && workletNode.disconnect() } catch { }
      workletNode = null
      try { localStream?.getTracks().forEach(t => t.stop()) } catch { }
      localStream = null

      if (audioCtx && audioCtx.state !== 'closed') {
        try { await audioCtx.close() } catch { }
      }
      audioCtx = null

      try { if (mediaSource && mediaSource.readyState === 'open') mediaSource.endOfStream() } catch { }
      mediaSource = null
      sourceBuffer = null
      audioEl = null
      mediaQueue = []

      recording.value = false
      listening.value = false
    }


    function toggleSubtitles() { showSubtitles.value = !showSubtitles.value }
    function toggleTTS() {
      ttsMuted.value = !ttsMuted.value
      if (audioEl) audioEl.muted = ttsMuted.value
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
      try { videoStream?.getTracks().forEach(t => t.stop()) } catch { }
      try { pc && pc.close() } catch { }
      localVideo.value.srcObject = null
      //remoteVideo.value.srcObject = null
      videoEnabled.value = false
    }
    async function toggleVideo() { if (videoEnabled.value) stopVideo(); else await startVideo() }

    onMounted(() => { startCall() })

    return {
      lang, userInput, history, recording, listening, typing, error,
      toggleMic, toggleSubtitles, toggleTTS, onSendText,
      historyEl, showSubtitles, ttsMuted, localVideo, remoteVideo, videoEnabled, toggleVideo,
      tokensToText, renderMarkdown
    }
  }
}).mount('#app')
