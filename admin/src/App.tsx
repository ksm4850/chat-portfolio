import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Layout } from '@/components/Layout'
import { CharacterPage } from '@/pages/CharacterPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { LoginPage } from '@/pages/LoginPage'
import { LogsPage } from '@/pages/LogsPage'
import { PortfolioPage } from '@/pages/PortfolioPage'
import { useAuth } from '@/store/auth'

function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuth((state) => state.accessToken)
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <TooltipProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="characters/new" element={<CharacterPage />} />
            <Route path="characters/:id/:tab?" element={<CharacterPage />} />
            <Route path="portfolio/:file?" element={<PortfolioPage />} />
            <Route path="logs" element={<LogsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" richColors />
    </TooltipProvider>
  )
}
