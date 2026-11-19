import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type AuthState = {
  email: string | null
  accessToken: string | null
  refreshToken: string | null
  setTokens: (accessToken: string, refreshToken: string, email?: string) => void
  clear: () => void
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      email: null,
      accessToken: null,
      refreshToken: null,
      setTokens: (accessToken, refreshToken, email) =>
        set((state) => ({ accessToken, refreshToken, email: email ?? state.email })),
      clear: () => set({ email: null, accessToken: null, refreshToken: null }),
    }),
    { name: 'portfolio-admin-auth' },
  ),
)
