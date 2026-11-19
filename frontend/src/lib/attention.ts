const IDLE_MS = 1500

let lastActivity = 0

/** 사용자가 모달을 직접 스크롤·클릭한 시각을 기록한다. 프로그램 스크롤과 구분하려고 wheel/touch/pointer 입력에서만 호출한다. */
export const markActivity = () => {
  lastActivity = performance.now()
}

export async function waitForIdle(isCancelled: () => boolean) {
  while (!isCancelled() && performance.now() - lastActivity < IDLE_MS) {
    await new Promise((r) => setTimeout(r, 200))
  }
}
