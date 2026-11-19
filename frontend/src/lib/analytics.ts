const GA_ID = import.meta.env.VITE_GA_ID

declare global {
  interface Window {
    dataLayer: unknown[]
    gtag: (...args: unknown[]) => void
  }
}

/** VITE_GA_ID 가 있으면 GA4(gtag.js)를 붙인다. */
export function installAnalytics() {
  if (!GA_ID) return
  window.dataLayer = window.dataLayer || []
  window.gtag = function gtag() {
    // gtag.js 는 배열이 아니라 arguments 객체를 받아야 처리한다.
    window.dataLayer.push(arguments)
  }
  window.gtag('js', new Date())
  window.gtag('config', GA_ID)
  const script = document.createElement('script')
  script.async = true
  script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`
  document.head.appendChild(script)
}

const fromCookie = () => document.cookie.match(/(?:^|; )_ga=GA\d+\.\d+\.(\d+\.\d+)/)?.[1]

/** 백엔드 대화 기록을 GA 방문자 데이터와 잇는 client_id. 광고 차단 등으로 못 얻으면 undefined. */
export function gaClientId(): Promise<string | undefined> {
  if (!GA_ID || !window.gtag) return Promise.resolve(undefined)
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(fromCookie()), 500)
    window.gtag('get', GA_ID, 'client_id', (id: unknown) => {
      clearTimeout(timer)
      resolve(typeof id === 'string' ? id : fromCookie())
    })
  })
}
