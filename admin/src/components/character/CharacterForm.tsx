import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmButton } from '@/components/ConfirmButton'
import { api } from '@/lib/api'
import { toastError } from '@/lib/errors'
import type { Character, CharacterInput } from '@/lib/types'
import { useCharacters } from '@/store/characters'

const EMPTY: CharacterInput = {
  slug: '',
  name: '',
  greeting: '',
  profile: '',
  speakingStyle: '',
  exampleDialogues: [],
  isPublic: false,
}

const MAX_DIALOGUES = 20

const toInput = ({ slug, name, greeting, profile, speakingStyle, exampleDialogues, isPublic }: Character) => ({
  slug,
  name,
  greeting,
  profile,
  speakingStyle,
  exampleDialogues,
  isPublic,
})

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <Label>
        {label}
        {hint && <span className="font-normal text-muted-foreground">{hint}</span>}
      </Label>
      {children}
    </div>
  )
}

export function CharacterForm({ character }: { character?: Character }) {
  const [form, setForm] = useState<CharacterInput>(character ? toInput(character) : EMPTY)
  const [pending, setPending] = useState(false)
  const { upsert, remove } = useCharacters()
  const navigate = useNavigate()

  const set = <K extends keyof CharacterInput>(key: K, value: CharacterInput[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const setDialogue = (index: number, key: 'user' | 'assistant', value: string) =>
    set(
      'exampleDialogues',
      form.exampleDialogues.map((d, i) => (i === index ? { ...d, [key]: value } : d)),
    )

  async function save() {
    setPending(true)
    try {
      const payload: CharacterInput = {
        ...form,
        exampleDialogues: form.exampleDialogues.filter((d) => d.user.trim() && d.assistant.trim()),
      }
      const saved = character
        ? await api.updateCharacter(character.id, payload)
        : await api.createCharacter(payload)
      upsert(saved)
      setForm(toInput(saved))
      toast.success('저장했다.')
      if (!character) navigate(`/characters/${saved.id}`)
    } catch (e) {
      toastError(e)
    } finally {
      setPending(false)
    }
  }

  async function destroy() {
    if (!character) return
    try {
      await api.deleteCharacter(character.id)
      remove(character.id)
      navigate('/')
    } catch (e) {
      toastError(e)
    }
  }

  return (
    <form
      className="grid gap-5"
      onSubmit={(e) => {
        e.preventDefault()
        save()
      }}
    >
      <Card>
        <CardContent className="grid gap-5">
          <div className="grid grid-cols-2 gap-4">
            <Field label="이름">
              <Input value={form.name} maxLength={50} required onChange={(e) => set('name', e.target.value)} />
            </Field>
            <Field label="slug" hint="소문자·숫자·하이픈">
              <Input
                value={form.slug}
                pattern="[a-z0-9][a-z0-9\-]{0,49}"
                required
                onChange={(e) => set('slug', e.target.value)}
              />
            </Field>
          </div>
          <Field label="인사말" hint="대화를 열면 처음 보이는 말">
            <Input value={form.greeting} maxLength={500} onChange={(e) => set('greeting', e.target.value)} />
          </Field>
          <Field label="프로필" hint="나는 누구인가. 자세한 사실은 지식 문서로 넣는다">
            <Textarea
              value={form.profile}
              rows={6}
              maxLength={4000}
              required
              onChange={(e) => set('profile', e.target.value)}
            />
          </Field>
          <Field label="말투" hint="존댓말/반말, 문장 길이, 말버릇">
            <Textarea
              value={form.speakingStyle}
              rows={4}
              maxLength={2000}
              onChange={(e) => set('speakingStyle', e.target.value)}
            />
          </Field>
          <div className="flex items-center gap-3">
            <Switch id="isPublic" checked={form.isPublic} onCheckedChange={(v) => set('isPublic', v)} />
            <Label htmlFor="isPublic">방문자에게 공개</Label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="grid gap-3">
          <div className="flex items-center">
            <Label>
              예시 대화
              <span className="font-normal text-muted-foreground">
                말투를 보여 주는 주고받기 ({form.exampleDialogues.length}/{MAX_DIALOGUES})
              </span>
            </Label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="ml-auto"
              disabled={form.exampleDialogues.length >= MAX_DIALOGUES}
              onClick={() => set('exampleDialogues', [...form.exampleDialogues, { user: '', assistant: '' }])}
            >
              <Plus /> 추가
            </Button>
          </div>
          {form.exampleDialogues.length === 0 && (
            <p className="text-sm text-muted-foreground">아직 예시가 없다.</p>
          )}
          {form.exampleDialogues.map((dialogue, index) => (
            <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-2 rounded-lg border p-2">
              <Textarea
                placeholder="방문자"
                rows={2}
                maxLength={500}
                value={dialogue.user}
                onChange={(e) => setDialogue(index, 'user', e.target.value)}
              />
              <Textarea
                placeholder="캐릭터"
                rows={2}
                maxLength={500}
                value={dialogue.assistant}
                onChange={(e) => setDialogue(index, 'assistant', e.target.value)}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="예시 삭제"
                onClick={() => set('exampleDialogues', form.exampleDialogues.filter((_, i) => i !== index))}
              >
                <Trash2 />
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          {pending ? '저장 중…' : character ? '저장' : '만들기'}
        </Button>
        {character && (
          <ConfirmButton
            type="button"
            variant="destructive"
            className="ml-auto"
            title={`${character.name} 캐릭터를 삭제할까?`}
            description="캐릭터의 지식 문서도 함께 지워진다."
            onConfirm={destroy}
          >
            캐릭터 삭제
          </ConfirmButton>
        )}
      </div>
    </form>
  )
}
