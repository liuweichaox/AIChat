import { createApp, ref, nextTick, onMounted } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.js'

createApp({
  setup() {
    const reply = ref([])
    const history = ref([])
    const userText = ref('')
    const recording = ref(false)
    const listening = ref(false)
    const typing = ref(false)
    const error = ref(null)
    const showSubtitles = ref(true)
    const videoEnabled = ref(false)

    const historyEl = ref(null)
    const localVideo = ref(null)
    const remoteVideo = ref(null)

    // ---- 音频相关（上行：AudioContext 推流，下行：MediaSource 播放）----
    let ws
    let audioCtx
    let localStream
    let workletNode

    let mediaSource
    let sourceBuffer
    let audioEl
    let mediaQueue = []

    // ---- 视频相关 ----
    let pc
    let videoStream

    // 你后端返回的编码：'audio/mpeg'（MP3）或 'audio/ogg; codecs=opus'
    const DOWNSTREAM_MIME = 'audio/mpeg'  // 如果是 OGG 改成 'audio/ogg; codecs=opus'

    function scrollToBottom() {
      nextTick(() => {
        if (historyEl.value) {
          historyEl.value.scrollTop = historyEl.value.scrollHeight
        }
      })
    }

    // ---------- 下行播放（MediaSource） ----------
    function initMediaSource() {
      if (mediaSource) return
      mediaSource = new MediaSource()
      audioEl = new Audio()
      audioEl.autoplay = true
      audioEl.src = URL.createObjectURL(mediaSource)

      mediaSource.addEventListener('sourceopen', () => {
        sourceBuffer = mediaSource.addSourceBuffer(DOWNSTREAM_MIME)
        sourceBuffer.mode = 'sequence'
        sourceBuffer.addEventListener('updateend', appendNextChunk)
        appendNextChunk()
      })
    }

    function appendNextChunk() {
      if (!sourceBuffer || sourceBuffer.updating) return
      if (mediaQueue.length > 0) {
        sourceBuffer.appendBuffer(mediaQueue.shift())
      }
    }

    function playTTSChunk(chunk) {
      if (!chunk || chunk.byteLength === 0) return
      if (!mediaSource) initMediaSource()
      mediaQueue.push(new Uint8Array(chunk))
      appendNextChunk()
    }

    // ---------- 打字机式文字显示 ----------
    function typeReply(text) {
      reply.value = []
      typing.value = true
      let i = 0
      const timer = setInterval(() => {
        reply.value.push({ id: reply.value.length, text: text[i] })
        scrollToBottom()
        i++
        if (i >= text.length) {
          clearInterval(timer)
          typing.value = false
          history.value.push({ role: 'bot', text })
          scrollToBottom()
        }
      }, 120)
    }

    // ---------- 建立通话（上行麦克风 + 下行 TTS） ----------
    async function startCall() {
      reply.value = []
      userText.value = ''
      recording.value = true
      listening.value = true
      error.value = null
      scrollToBottom()

      // 1) 连接 WebSocket（同一条通道：发 PCM，收 文本/音频）
      ws = new WebSocket(`ws://${location.host}/ws/audio`)
      ws.binaryType = 'arraybuffer'

      ws.onclose = () => { stopCall() }
      ws.onerror = (e) => { error.value = 'WebSocket错误'; console.error(e) }

      ws.onmessage = (e) => {
        if (typeof e.data === 'string') {
          // 文本帧
          const msg = JSON.parse(e.data)
          if (msg.type === 'transcript') {
            userText.value = msg.data
            listening.value = false
            history.value.push({ role: 'user', text: msg.data })
            scrollToBottom()
          } else if (msg.type === 'text') {
            typeReply(msg.data)
          } else if (msg.type === 'end') {
            // 如果后端会显式告诉“这一轮音频结束”，你可以在这里把 listening 置 true
            listening.value = true
            userText.value = ''
          }
        } else {
          // 二进制帧：TTS MP3/OGG chunk
          playTTSChunk(e.data)
        }
      }

      // 2) 上行：采集麦克风，用 AudioWorklet 把 PCM 推给后端
      audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 })
      await audioCtx.audioWorklet.addModule('/static/pcm-processor.js')

      localStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const source = audioCtx.createMediaStreamSource(localStream)

      workletNode = new AudioWorkletNode(audioCtx, 'pcm-processor', { numberOfInputs: 1, numberOfOutputs: 0 })
      workletNode.port.onmessage = (ev) => {
        // 这里的 ev.data 是你在 processor 里 postMessage 上来的 PCM Int16/Float32 等
        if (ws && ws.readyState === WebSocket.OPEN) {
          // 注意：如果你传来的是 Float32Array，需要转换成 ArrayBuffer/Int16 再发
          ws.send(ev.data.buffer || ev.data)
        }
      }

      source.connect(workletNode)

      if (audioCtx.state === 'suspended') {
        await audioCtx.resume()
      }
    }

    function stopCall() {
      // WebSocket
      try { ws && ws.readyState === WebSocket.OPEN && ws.close() } catch { }
      ws = null

      // 关闭录音
      try { workletNode && workletNode.disconnect() } catch { }
      try { localStream?.getTracks().forEach(t => t.stop()) } catch { }
      try { audioCtx && audioCtx.close() } catch { }

      // MediaSource
      try {
        if (mediaSource && mediaSource.readyState === 'open') {
          mediaSource.endOfStream()
        }
      } catch { }
      mediaSource = null
      sourceBuffer = null
      audioEl = null
      mediaQueue = []

      recording.value = false
      listening.value = false
    }

    function toggleSubtitles() {
      showSubtitles.value = !showSubtitles.value
    }

    async function toggleMic() {
      if (recording.value) {
        stopCall()
      } else {
        try {
          await startCall()
        } catch (err) {
          console.error(err)
          error.value = err?.message || String(err)
          recording.value = false
        }
      }
    }

    // ---------- 视频（保留你原来的） ----------
    async function startVideo() {
      if (videoEnabled.value) return
      try {
        videoStream = await navigator.mediaDevices.getUserMedia({ video: true })
        localVideo.value.srcObject = videoStream
        pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
        videoStream.getTracks().forEach(t => pc.addTrack(t, videoStream))
        pc.ontrack = ev => {
          if (ev.track.kind === 'video') {
            remoteVideo.value.srcObject = ev.streams[0]
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
        videoEnabled.value = true
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
      remoteVideo.value.srcObject = null
      videoEnabled.value = false
    }

    async function toggleVideo() {
      if (videoEnabled.value) {
        stopVideo()
      } else {
        await startVideo()
      }
    }

    onMounted(() => {
      startCall()
    })

    return {
      reply, history, userText, recording, listening, typing, error,
      toggleMic, historyEl, showSubtitles, toggleSubtitles,
      localVideo, remoteVideo, videoEnabled, toggleVideo
    }
  }
}).mount('#app')
