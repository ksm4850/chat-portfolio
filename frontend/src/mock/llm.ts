import type { Source } from '@/lib/types'

export type Piece = { kind: 'text'; text: string } | { kind: 'show'; anchor: string; quote?: string }

const MAX_MARKER_LENGTH = 200
const MARKER = /^show:([\w-]+)(?:\|([\s\S]+))?$/

/** contracts/README.md 5장 "서버 변환 규칙" 참고 구현. 델타 경계에서 잘린 표시도 처리한다. */
export function createMarkerParser() {
  let buffer = ''

  function feed(delta: string): Piece[] {
    buffer += delta
    const out: Piece[] = []
    while (buffer) {
      const open = buffer.indexOf('[[')
      if (open === -1) {
        const keep = buffer.endsWith('[') ? 1 : 0
        const text = buffer.slice(0, buffer.length - keep)
        if (text) out.push({ kind: 'text', text })
        buffer = buffer.slice(buffer.length - keep)
        break
      }
      if (open > 0) {
        out.push({ kind: 'text', text: buffer.slice(0, open) })
        buffer = buffer.slice(open)
        continue
      }
      const close = buffer.indexOf(']]')
      if (close === -1) {
        if (buffer.length <= MAX_MARKER_LENGTH) break
        out.push({ kind: 'text', text: '[[' })
        buffer = buffer.slice(2)
        continue
      }
      const match = MARKER.exec(buffer.slice(2, close).trim())
      buffer = buffer.slice(close + 2)
      if (match) out.push({ kind: 'show', anchor: match[1], quote: match[2]?.trim() || undefined })
      else console.warn('[mock] 무효한 위치 표시를 버림')
    }
    return out
  }

  function flush(): Piece[] {
    const text = buffer
    buffer = ''
    return text ? [{ kind: 'text', text }] : []
  }

  return { feed, flush }
}

const SCRIPTS: { match: RegExp; answer: string }[] = [
  {
    match: /aws|인프라|ecs|swarm|클라우드/i,
    answer:
      'AWS로 옮기기 전에는 NCP의 여러 서버에 Docker Compose로 서비스를 올리고, 어느 서버에 둘지를 사람이 직접 정하고 있었습니다.' +
      '[[show:ecs-overview-1|어느 서비스를 어느 서버에 둘지 사람이 리소스 여유를 보고 직접 정하는 수동 배치]] ' +
      '이 구조를 그대로 옮기면 서버마다 남는 유휴 리소스가 그대로 비용이 되는 게 가장 큰 문제였습니다. ' +
      '그래서 1차로 소수의 EC2로 구성한 Swarm 클러스터에 전 서비스를 통합했고, 서버마다 따로 띄우던 Nginx도 Traefik 하나로 합쳤습니다.' +
      '[[show:ecs-overview-2|서버마다 각자 운영하던 Nginx를 없애고]] ' +
      '요금 문제는 해결됐지만, 이번에는 EC2 패치부터 로깅과 모니터링 스택까지 전부 직접 운영해야 하는 부담이 남았습니다.' +
      '[[show:ecs-overview-3|EC2 인스턴스 프로비저닝·패치, 서비스별 로깅 수집, Swarm 클러스터와 모니터링 스택 자체의 관리까지 전부 자체 운영 부담]] ' +
      '결국 2차로 ECS로 전환해 운영 영역을 관리형 서비스로 넘겼고, 그 뒤에도 비용은 기존 대비 30~40% 줄어든 상태로 유지했습니다.',
  },
  {
    match: /방화벽|워커|nats|토폴로지/i,
    answer:
      '워커는 연구자의 집이나 사무실 PC라서 공인 IP도, 열린 포트도 없었습니다.' +
      '[[show:cq-decisions-2|워커는 집·사무실 PC라 공인 IP도 열린 포트도 없음]] ' +
      '그래서 서버가 워커로 접속하는 대신 방향을 뒤집어, 런타임 통신을 전부 NATS 위에서 처리했습니다. ' +
      '에이전트 요청은 릴레이가 request-reply로 워커에 전달하고, 로그는 JetStream 스트림으로 흘려보냈습니다.' +
      '[[show:cq-decisions-2|방향을 뒤집어 런타임 통신을 전부 NATS 위에서 처리]] ' +
      '덕분에 워커는 아웃바운드만 되면 어디서든 동작하고, 릴레이가 재시작돼도 진행 중인 실험이 끊기지 않습니다.',
  },
  {
    match: /레거시|마이그레이션|asp/i,
    answer:
      '한국미용데이터에서 Classic ASP와 IIS로 돌던 앱 API 서버를 FastAPI와 Ubuntu 환경으로 옮겼습니다.' +
      '[[show:vuka-app-api-overview-3|Classic ASP + IIS 환경의 API 서버를 FastAPI + Ubuntu 환경으로 마이그레이션]] ' +
      '기존 MSSQL은 유지하면서 PostgreSQL을 함께 쓰는 구조로 전환했고, 이 과정에서 인프라도 AWS로 이전했습니다.' +
      '[[show:vuka-app-api-overview-3|DB는 MSSQL을 유지하면서 PostgreSQL을 함께 사용하는 구조로 전환]]',
  },
  {
    match: /아무거나|소개|대표|어떤 일|뭐 했|무슨 일/,
    answer:
      '가장 최근에 집중한 프로젝트는 ML 실험 자동화 플랫폼입니다. ' +
      '연구자가 자기 PC의 GPU를 워커로 등록하면, AI 에이전트가 MCP로 원격 실험을 설계하고 실행하는 플랫폼입니다.' +
      '[[show:cq-overview-1|연구자가 자신의 PC(GPU)를 워커로 등록하면]] ' +
      '두 명이 만들었고, 저는 웹 프론트엔드를 제외한 백엔드와 인프라 전반을 맡았습니다.' +
      '[[show:cq-overview-1|본인은 웹 프론트엔드를 제외한 백엔드·인프라 전반 담당]] ' +
      '방화벽 뒤 워커에 어떻게 접근했는지, 인프라를 어떻게 옮겼는지도 물어봐 주시면 화면과 함께 설명드리겠습니다.',
  },
]

export function mockAnswer(question: string, sources: (Source & { quote?: string })[]): string {
  const script = SCRIPTS.find((s) => s.match.test(question))
  if (script) return script.answer

  const [top, second] = sources
  if (!top?.location) {
    return '해당 내용은 제가 정리해 둔 자료에는 없습니다. 프로젝트나 기술 경험에 대해 물어봐 주시면 관련 화면과 함께 설명드리겠습니다.'
  }
  const marker = (s: typeof top) => `[[show:${s.location!.anchor}${s.quote ? `|${s.quote}` : ''}]]`
  let answer = `관련 내용은 '${top.title.split(' > ')[0]}'에 정리해 두었습니다. ${top.snippet.slice(0, 60)}…${marker(top)} `
  if (second?.location) answer += `함께 보시면 좋은 부분도 열어 드리겠습니다.${marker(second)}`
  return answer
}

/** LLM 스트림처럼 불규칙한 크기의 조각으로 나눈다. 위치 표시가 조각 경계에서 잘리는 경우도 생긴다. */
export function* llmDeltas(answer: string) {
  let i = 0
  while (i < answer.length) {
    const size = 1 + Math.floor(Math.random() * 5)
    yield answer.slice(i, i + size)
    i += size
  }
}
