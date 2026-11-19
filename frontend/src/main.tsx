import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { installAnalytics } from './lib/analytics'

if (import.meta.env.VITE_MOCK === '1') {
  const { installMockServer } = await import('./mock/server')
  installMockServer()
}

installAnalytics()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
