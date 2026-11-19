import { create } from 'zustand'
import { api } from '@/lib/api'
import type { Character } from '@/lib/types'

type CharactersState = {
  items: Character[]
  loaded: boolean
  load: () => Promise<void>
  upsert: (character: Character) => void
  remove: (id: string) => void
}

export const useCharacters = create<CharactersState>((set) => ({
  items: [],
  loaded: false,
  load: async () => set({ items: await api.listCharacters(), loaded: true }),
  upsert: (character) =>
    set((state) => ({
      items: state.items.some((c) => c.id === character.id)
        ? state.items.map((c) => (c.id === character.id ? character : c))
        : [...state.items, character],
    })),
  remove: (id) => set((state) => ({ items: state.items.filter((c) => c.id !== id) })),
}))
