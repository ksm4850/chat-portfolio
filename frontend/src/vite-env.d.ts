/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MOCK?: string
  /** GA4 측정 ID(G-XXXX). 없으면 GA 를 붙이지 않고 gaClientId 도 보내지 않는다. */
  readonly VITE_GA_ID?: string
}
