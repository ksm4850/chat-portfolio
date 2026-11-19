// 마이크 입력(보통 48kHz float)을 16kHz mono 16-bit PCM 으로 바꿔 100ms 단위로 메인 스레드에 넘긴다.
const TARGET_RATE = 16000;
const CHUNK_SAMPLES = TARGET_RATE / 10;

class PcmWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.step = sampleRate / TARGET_RATE;
    this.phase = 0;
    this.sum = 0;
    this.count = 0;
    this.peak = 0;
    this.chunk = new Int16Array(CHUNK_SAMPLES);
    this.length = 0;
  }

  process(inputs) {
    const samples = inputs[0][0];
    if (!samples) return true;
    for (const sample of samples) {
      // 출력 한 샘플에 해당하는 입력 구간을 평균 내 앨리어싱을 줄인다.
      this.sum += sample;
      this.count += 1;
      this.phase += 1;
      if (this.phase >= this.step) {
        this.phase -= this.step;
        this.push(this.sum / this.count);
        this.sum = 0;
        this.count = 0;
      }
    }
    return true;
  }

  push(value) {
    const clamped = Math.max(-1, Math.min(1, value));
    this.peak = Math.max(this.peak, Math.abs(clamped));
    this.chunk[this.length++] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    if (this.length === CHUNK_SAMPLES) {
      this.port.postMessage({ pcm: this.chunk.buffer, peak: this.peak }, [this.chunk.buffer]);
      this.chunk = new Int16Array(CHUNK_SAMPLES);
      this.length = 0;
      this.peak = 0;
    }
  }
}

registerProcessor('pcm-worklet', PcmWorklet);
