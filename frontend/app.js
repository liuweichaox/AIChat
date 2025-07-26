import { createApp, ref, nextTick } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.js'

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

    let ws
    let audioCtx
    let localStream
    let workletNode
    let pc
    let videoStream

    function scrollToBottom() {
      nextTick(() => {
        if (historyEl.value) {
          historyEl.value.scrollTop = historyEl.value.scrollHeight
        }
      })
    }

    function playAudio(data) {
      if (!audioCtx) {
        audioCtx = new AudioContext({ sampleRate: 48000 })
      }
      if (data.byteLength === 0) return
      const pcm = new Int16Array(data)
      const float = new Float32Array(pcm.length)
      for (let i = 0; i < pcm.length; i++) float[i] = pcm[i] / 32768
      const buffer = audioCtx.createBuffer(1, float.length, 48000)
      buffer.copyToChannel(float, 0)
      const source = audioCtx.createBufferSource()
      source.buffer = buffer
      source.connect(audioCtx.destination)
      source.onended = () => {
        setTimeout(() => {
          listening.value = true
          userText.value = ''
        }, 300)
      }
      source.start()
    }

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

    async function startCall() {
      reply.value = []
      userText.value = ''
      recording.value = true
      listening.value = true
      error.value = null
      scrollToBottom()

      ws = new WebSocket(`ws://${location.host}/ws/audio`)
      ws.binaryType = 'arraybuffer'
      ws.onclose = () => { stopCall() }
      ws.onerror = (e) => { error.value = 'WebSocket错误'; console.error(e) }

      ws.onmessage = (e) => {
        if (typeof e.data === 'string') {
          const msg = JSON.parse(e.data)
          if (msg.type === 'transcript') {
            userText.value = msg.data
            listening.value = false
            history.value.push({ role: 'user', text: msg.data })
            scrollToBottom()
          } else if (msg.type === 'text') {
            typeReply(msg.data)
          }
        } else {
          playAudio(e.data)
        }
      }

      audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 })
      await audioCtx.audioWorklet.addModule('/static/pcm-processor.js')

      localStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const source = audioCtx.createMediaStreamSource(localStream)

      workletNode = new AudioWorkletNode(audioCtx, 'pcm-processor', { numberOfInputs: 1, numberOfOutputs: 0 })
      workletNode.port.onmessage = (ev) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(ev.data.buffer)
        }
      }

      source.connect(workletNode)

      if (audioCtx.state === 'suspended') {
        await audioCtx.resume()
      }
    }

    function stopCall() {
      try { ws && ws.readyState === WebSocket.OPEN && ws.close() } catch {}
      try { workletNode && workletNode.disconnect() } catch {}
      try { localStream?.getTracks().forEach(t => t.stop()) } catch {}
      try { audioCtx && audioCtx.close() } catch {}
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
      try { videoStream?.getTracks().forEach(t => t.stop()) } catch {}
      try { pc && pc.close() } catch {}
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

    return {
      reply, history, userText, recording, listening, typing, error,
      toggleMic, historyEl, showSubtitles, toggleSubtitles,
      localVideo, remoteVideo, videoEnabled, toggleVideo
    }
  }
}).mount('#app')
