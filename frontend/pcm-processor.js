// static/pcm-processor.js
class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._floatTo16 = (f32) => {
            const len = f32.length;
            const i16 = new Int16Array(len);
            for (let i = 0; i < len; i++) {
                let s = Math.max(-1, Math.min(1, f32[i]));
                i16[i] = s * 0x7fff;
            }
            return i16;
        };
    }

    process(inputs) {
        const input = inputs[0];
        if (!input || !input[0]) return true;
        const channel = input[0]; // mono
        const i16 = this._floatTo16(channel);
        // 传输所有权，避免拷贝
        this.port.postMessage(i16, [i16.buffer]);
        return true; // 持续运行
    }
}

registerProcessor('pcm-processor', PCMProcessor);
