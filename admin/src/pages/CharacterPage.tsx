import { useNavigate, useParams } from 'react-router'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PageHeader } from '@/components/PageHeader'
import { ChatTestPanel } from '@/components/character/ChatTestPanel'
import { CharacterForm } from '@/components/character/CharacterForm'
import { KnowledgePanel } from '@/components/character/KnowledgePanel'
import { SearchPanel } from '@/components/character/SearchPanel'
import { useCharacters } from '@/store/characters'

const TABS = [
  { id: 'settings', label: '설정' },
  { id: 'knowledge', label: '지식' },
  { id: 'search', label: '검색 테스트' },
  { id: 'chat', label: '채팅 테스트' },
] as const

export function CharacterPage() {
  const { id, tab = 'settings' } = useParams()
  const navigate = useNavigate()
  const { items, loaded } = useCharacters()

  if (!id) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <PageHeader title="새 캐릭터" />
        <div className="mt-6">
          <CharacterForm />
        </div>
      </div>
    )
  }

  const character = items.find((c) => c.id === id)
  if (!character) {
    return loaded ? <p className="p-6 text-sm text-muted-foreground">캐릭터를 찾을 수 없다.</p> : null
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            {character.name}
            <Badge variant="outline">{character.slug}</Badge>
            {character.isPublic ? <Badge>공개</Badge> : <Badge variant="secondary">비공개</Badge>}
          </span>
        }
      />
      <Tabs value={tab} onValueChange={(value) => navigate(`/characters/${id}/${value}`)} className="mt-4">
        <TabsList>
          {TABS.map((t) => (
            <TabsTrigger key={t.id} value={t.id}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="settings" className="mt-4">
          <CharacterForm key={character.id} character={character} />
        </TabsContent>
        <TabsContent value="knowledge" className="mt-4">
          <KnowledgePanel characterId={character.id} />
        </TabsContent>
        <TabsContent value="search" className="mt-4">
          <SearchPanel characterId={character.id} />
        </TabsContent>
        <TabsContent value="chat" className="mt-4">
          <ChatTestPanel key={character.id} character={character} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
