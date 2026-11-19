import { useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { FileText, LayoutDashboard, LogOut, MessagesSquare, Plus, UserRound } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { logout } from '@/lib/api'
import { toastError } from '@/lib/errors'
import { useAuth } from '@/store/auth'
import { useCharacters } from '@/store/characters'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-sidebar-foreground/80 hover:bg-sidebar-accent',
    isActive && 'bg-sidebar-accent font-medium text-sidebar-foreground',
  )

export function Layout() {
  const email = useAuth((state) => state.email)
  const { items, load } = useCharacters()
  const navigate = useNavigate()

  useEffect(() => {
    load().catch(toastError)
  }, [load])

  return (
    <div className="flex h-dvh">
      <aside className="flex w-60 shrink-0 flex-col border-r bg-sidebar">
        <div className="px-4 py-4 text-sm font-semibold">포트폴리오 관리자</div>
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2">
          <NavLink to="/" end className={linkClass}>
            <LayoutDashboard className="size-4" /> 대시보드
          </NavLink>
          <Separator className="my-2" />
          <div className="flex items-center justify-between px-2 pt-1 pb-1 text-xs text-muted-foreground">
            캐릭터
            <Button variant="ghost" size="icon-xs" onClick={() => navigate('/characters/new')} aria-label="새 캐릭터">
              <Plus />
            </Button>
          </div>
          {items.map((character) => (
            <NavLink key={character.id} to={`/characters/${character.id}`} className={linkClass}>
              <UserRound className="size-4" />
              <span className="truncate">{character.name}</span>
              {!character.isPublic && (
                <Badge variant="outline" className="ml-auto">
                  비공개
                </Badge>
              )}
            </NavLink>
          ))}
          <Separator className="my-2" />
          <NavLink to="/portfolio" className={linkClass}>
            <FileText className="size-4" /> 포트폴리오 원본
          </NavLink>
          <NavLink to="/logs" className={linkClass}>
            <MessagesSquare className="size-4" /> 대화 로그
          </NavLink>
        </nav>
        <div className="flex items-center gap-2 border-t px-3 py-3 text-xs text-muted-foreground">
          <span className="truncate">{email}</span>
          <Button
            variant="ghost"
            size="icon-xs"
            className="ml-auto"
            onClick={() => logout().then(() => navigate('/login'))}
            aria-label="로그아웃"
          >
            <LogOut />
          </Button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
