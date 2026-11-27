import { useUi } from '@/store/ui'

const GA_ID = import.meta.env.VITE_GA_ID

declare global {
  interface Window {
    dataLayer: unknown[]
    gtag: (...args: unknown[]) => void
  }
}

type Params = Record<string, string | number>

const PAGE_TITLES: Record<string, string> = { home: '홈', career: '경력', skills: '기술 스택' }

/** VITE_GA_ID 가 있으면 GA4(gtag.js)를 붙인다. 첫 화면은 GA 자동 페이지뷰로, 이후 화면 전환은 직접 페이지뷰로 보낸다(URL 이 바뀌지 않는 SPA). */
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
  trackScreens()
}

export function track(name: string, params?: Params) {
  if (!GA_ID) return
  window.gtag('event', name, params)
}

type UiState = ReturnType<typeof useUi.getState>

function screenOf(s: UiState): { path: string; title: string } {
  if (s.screen === 'landing') return { path: '/', title: document.title }
  if (s.project) {
    const { projectId, tab } = s.project
    return { path: `/project/${projectId}${tab ? `/${tab}` : ''}`, title: `프로젝트: ${projectId}` }
  }
  return { path: `/${s.page.name}`, title: PAGE_TITLES[s.page.name] }
}

function trackScreens() {
  let lastPath = screenOf(useUi.getState()).path
  const sendPageView = (s: UiState) => {
    const { path, title } = screenOf(s)
    if (path === lastPath) return
    lastPath = path
    track('page_view', { page_location: `${location.origin}${path}`, page_title: title })
  }
  useUi.subscribe((s, prev) => {
    sendPageView(s)
    if (prev.screen === 'app' && s.screen === 'app' && s.chatOpen !== prev.chatOpen) {
      track('chat_toggle', { chat_open: String(s.chatOpen) })
    }
  })
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
