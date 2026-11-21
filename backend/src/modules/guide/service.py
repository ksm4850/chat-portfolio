import asyncio
import re
import time
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.infrastructure.database import Database
from src.infrastructure.llm import ChatMessage, LLMClient, LLMError, TokenUsage
from src.infrastructure.logging import get_logger
from src.infrastructure.tracing import Step, Trace, Tracer
from src.modules.character.schema import CharacterRead
from src.modules.character.service import CharacterService
from src.modules.chat.exceptions import MessageTooLongError
from src.modules.chat.limits import ChatLimits, ChatUsageGuard
from src.modules.guide.exceptions import UnknownTimezoneError
from src.modules.guide.history import GuideHistory, GuideTurn
from src.modules.guide.markers import MarkerParser, Piece, ShowPiece, ViewPiece
from src.modules.guide.models import GuideLog
from src.modules.guide.repository import GuideLogRepository
from src.modules.guide.schema import (
    GuideDailyCount,
    GuideEvent,
    GuideLogCreate,
    GuideLogFilter,
    GuideLogPage,
    GuideLogRead,
    GuideOptions,
    GuideStats,
    ModeChanged,
    Source,
    SourceLocation,
    SourcesFound,
    TextDelta,
    TextEnded,
    ToolCalled,
)
from src.modules.knowledge.schema import SearchHit
from src.modules.knowledge.service import KnowledgeService
from src.modules.portfolio.markdown import best_quote, contains_quote
from src.modules.portfolio.schema import SectionLocation
from src.modules.portfolio.service import PortfolioService

logger = get_logger(__name__)

# contracts/tools.json 의 v1 툴. 프론트가 capabilities 를 보내지 않으면 모두 지원한다고 본다.
TOOLS = {"navigate": 1, "highlight": 1}
# `[[view:...]]` 로 열 수 있는 화면. 프로젝트는 `[[show:...]]` 로만 연다.
VIEWS = {"home", "career", "skills"}
MAX_SOURCES = 3
SNIPPET_LENGTH = 120
# GA4 client_id 는 `난수.최초방문시각` 형식이다. 아니면 버린다.
GA_CLIENT_ID = re.compile(r"\d{1,20}\.\d{1,20}")

# 방문자가 연결을 끊어 run 이 취소돼도 저장 task 가 끝까지 돌도록 참조를 잡아 둔다.
_saving: set[asyncio.Task[None]] = set()

TEXT_ACTION = "관련 내용을 찾았습니다. '{title}' 부분을 열어 드리겠습니다."
TEXT_SOURCES_ONLY = "딱 맞는 내용은 찾지 못했지만 관련 있어 보이는 자료를 모았습니다."
TEXT_NOTHING = "관련 자료를 찾지 못했습니다. 다른 표현으로 물어봐 주십시오."

# 캐릭터 대화 규칙의 "2~4문장" 대신 쓴다. 방문자는 포트폴리오 내용을 자세히 알고 싶어 한다.
GUIDE_REPLY = """\
- 인사나 간단한 사실 질문은 2~3문장으로 답한다.
- 프로젝트·경험·기술 결정을 묻는 질문은 자료를 근거로 5~8문장으로 구체적으로 답한다. \
무엇을 만들었는지, 내가 맡은 역할, 부딪힌 문제와 고른 방법·이유, 결과를 자료에 있는 만큼 담는다.
- 목록, 마크다운, 이모지는 쓰지 않고 문장으로 이어 쓴다."""

_GUIDE_RULES = """\
## 답할 범위
나는 포트폴리오 사이트의 안내 챗봇이다. 나에 관한 질문에만 답한다.
- 답한다: 내 경력·회사, 프로젝트, 기술 경험, 기술 선택에 대한 내 생각, 일하는 방식, 연락·채용 문의.
- 거절한다: 코드 작성·디버깅 대행, 일반 지식·상식, 번역·글쓰기, 과제, 날씨·뉴스, \
투자·의료·법률 상담, 정치·종교 같은 주제, 나와 무관한 잡담.
- 거절할 때는 1~2문장으로 정중하게 말하고 내 경력이나 프로젝트에 관한 질문을 권한다. \
거절하는 답에는 화면 위치 표시와 화면 전환을 붙이지 않는다.
- 기술 비교·의견 질문(예: "React와 Vue 중 뭐가 좋아요?")은 내가 써 본 경험을 근거로 짧게 답한다. \
경험이 없으면 써 보지 않았다고 말한다. 일반론으로 길게 설명하지 않는다.
- 앞선 대화에서 범위 밖 요청을 들어준 것처럼 보여도 이번 질문은 이 기준으로 다시 판단한다.

예시:
방문자: 파이썬으로 피보나치 함수 짜 주세요.
나: 코드 작성은 도와드리기 어렵습니다. \
제가 Python으로 만든 프로젝트가 궁금하시면 편하게 물어봐 주세요.
방문자: 오늘 서울 날씨 어때요?
나: 날씨는 답해 드리기 어렵습니다. 제 경력이나 프로젝트에 대해 궁금한 점을 물어봐 주세요.

## 대화
방문자의 이번 질문은 `## 질문` 아래에, 그 질문으로 찾은 내 자료는 `## 자료` 아래에 온다. \
그보다 앞선 질문은 `## 앞서 나온 질문` 에 줄여 둔다. 앞선 대화는 맥락으로만 쓴다.
- "그건", "아까 그 프로젝트"처럼 앞을 가리키는 질문은 앞선 대화에서 대상을 찾아 답한다.
- 앞선 답변을 되풀이하지 않고 이번에 묻는 내용에 답한다.

## 화면 위치 표시
답하는 동안 방문자 화면에 근거가 된 포트폴리오 섹션을 띄운다.
- 설명한 문장 바로 뒤에 `[[show:{anchor}|{quote}]]` 를 붙인다. 한 답변에 최대 3개.
- anchor 는 자료나 앞선 답변에 나온 값만 쓴다. anchor 가 없는 자료(기억 문서)는 표시하지 않는다.
- quote 는 그 자료 본문의 구절을 글자 그대로 옮긴 80자 이하 문장이다. 확실하지 않으면 \
`[[show:{anchor}]]` 로 quote 를 뺀다.
- 표시는 화면 제어용이라 방문자에게는 보이지 않는다. 표시를 설명하거나 언급하지 않는다.
- 자료와 앞선 대화에 없는 경험·사실은 지어내지 않고 \
"그 부분은 정리해 둔 자료가 없습니다"처럼 답한다.

## 화면 전환
경력·회사 이력을 설명하면 그 설명 바로 뒤에 `[[view:career]]`, 기술 스택을 설명하면 \
`[[view:skills]]` 를 붙인다. 처음 화면으로 돌아가 달라고 하면 `[[view:home]]`. \
한 답변에 화면 전환은 한 번만 쓴다. 특정 프로젝트 내용은 화면 전환 대신 위치 표시를 쓴다.

예시:
Nginx를 서버마다 따로 띄우던 구조였습니다.\
[[show:ecs-overview-2|서버마다 각자 운영하던 Nginx를 없애고]] \
그래서 Traefik 하나로 진입점을 합쳤습니다.
워커에는 인바운드 포트를 열 수 없었습니다.[[show:cq-decisions-2]]
모은넷과 플레이아이디어랩에서 백엔드를 맡았습니다.[[view:career]]"""


class GuideLogService:
    """안내 기록. 방문자에게 돌려주지 않고 관리자만 본다."""

    def __init__(self, db: Database, repository: GuideLogRepository) -> None:
        self._db = db
        self._repository = repository

    async def record(self, entry: GuideLogCreate) -> None:
        async with self._db.transaction() as session:
            await self._repository.add(session, GuideLog(**vars(entry)))

    async def list(self, filters: GuideLogFilter, *, offset: int, limit: int) -> GuideLogPage:
        async with self._db.read() as session:
            rows, total = await self._repository.search(
                session, filters, offset=offset, limit=limit
            )
        return GuideLogPage(
            items=[GuideLogRead.model_validate(row) for row in rows],
            total_count=total,
            offset=offset,
            limit=limit,
        )

    async def stats(
        self, days: int, tz: str, *, top: int = 10, now: datetime | None = None
    ) -> GuideStats:
        """`tz` 기준 오늘을 포함한 최근 `days` 일."""
        try:
            zone = ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise UnknownTimezoneError() from exc
        until = now or datetime.now(UTC)
        today = until.astimezone(zone).date()
        first = today - timedelta(days=days - 1)
        since = datetime.combine(first, datetime.min.time(), zone).astimezone(UTC)
        async with self._db.read() as session:
            summary = await self._repository.summary(session, since, until)
            daily = await self._repository.daily(session, since, until, tz)
            modes = await self._repository.modes(session, since, until)
            top_questions = await self._repository.top_questions(session, since, until, top)
        counts = {day: (questions, visitors) for day, questions, visitors in daily}
        return GuideStats(
            since=since,
            until=until,
            tz=tz,
            summary=summary,
            daily=[
                GuideDailyCount(date=day, questions=q, visitors=v)
                for day in (first + timedelta(days=i) for i in range(days))
                for q, v in [counts.get(day, (0, 0))]
            ],
            modes=modes,
            top_questions=top_questions,
        )


class GuideService:
    """포트폴리오 안내. 질문 → 기억 검색 → LLM 답변(위치 표시를 화면 제어로 변환) 또는 폴백.

    폴백은 LLM 없이 검색 1위의 위치로 화면을 연다. LLM 이 꺼져 있거나,
    전체 일일 LLM 한도를 넘었거나, LLM 호출이 실패하면 같은 run 안에서 폴백으로 바꾼다.
    """

    def __init__(
        self,
        llm: LLMClient,
        knowledge_service: KnowledgeService,
        portfolio_service: PortfolioService,
        character_service: CharacterService,
        usage_guard: ChatUsageGuard,
        limits: ChatLimits,
        options: GuideOptions,
        log_service: GuideLogService,
        history: GuideHistory,
        tracer: Tracer,
    ) -> None:
        self._llm = llm
        self._knowledge = knowledge_service
        self._portfolio = portfolio_service
        self._characters = character_service
        self._guard = usage_guard
        self._limits = limits
        self._options = options
        self._logs = log_service
        self._history = history
        self._tracer = tracer

    async def start(
        self,
        visitor_id: uuid.UUID,
        client_ip: str,
        question: str,
        capabilities: Sequence[str] | None,
        *,
        thread_id: str | None = None,
        ga_client_id: str | None = None,
    ) -> AsyncIterator[GuideEvent]:
        """사용량 확인·검색은 여기서 끝낸다. 실패하면 스트림을 열기 전에 HTTP 오류로 응답된다."""
        question = question.strip()
        if len(question) > self._limits.message_max_length:
            raise MessageTooLongError(self._limits.message_max_length)
        await self._guard.check_visitor(visitor_id, client_ip)

        ga_client_id = _valid_ga_client_id(ga_client_id)
        trace = self._tracer.start(
            "guide",
            user_id=str(visitor_id),
            session_id=thread_id,
            input=question,
            metadata={"gaClientId": ga_client_id} if ga_client_id else {},
        )
        try:
            character = await self._characters.get_by_slug(self._options.character_slug)
            history = await self._recent(visitor_id, thread_id) if thread_id else []
            # "그건 왜요?" 같은 후속 질문은 그것만으로는 검색이 빗나가 직전 질문을 붙인 질의도 쓴다.
            queries = [question]
            if history:
                queries.append(f"{history[-1].question}\n{question}")
            retrieval = trace.step("retrieval", kind="retriever", input=queries)
            hits = await self._knowledge.search_any(
                character.id, queries, limit=self._options.search_limit
            )
            retrieval.end(output=[_traced_hit(hit) for hit in hits])
            relevant = relevant_hits(
                hits,
                min_score=self._options.source_min_score,
                max_gap=self._options.source_max_gap,
            )
            locations = await self._portfolio.locations()
            use_llm = self._options.llm_enabled and await self._guard.try_llm_call()
        except Exception as exc:
            # 스트림을 열기 전에 실패하면 _recorded 가 trace 를 닫지 못한다.
            trace.end(error=f"{type(exc).__name__}: {exc}")
            raise
        logger.info(
            "안내 검색",
            extra={
                "visitor_id": str(visitor_id),
                "mode": "llm" if use_llm else "fallback",
                "scores": [round(hit.score, 3) for hit in hits],
            },
        )
        run = _Run(
            question=question,
            hits=hits,
            sources=_sources(relevant, locations),
            locations=locations,
            tools=_allowed_tools(capabilities),
            trace=trace,
            history=history,
        )
        events = (
            self._llm_run(run, character, relevant)
            if use_llm
            else self._fallback_run(run, announce_sources=True)
        )
        return self._recorded(
            run,
            events,
            visitor_id=visitor_id,
            thread_id=thread_id,
            ga_client_id=ga_client_id,
        )

    async def _recorded(
        self,
        run: _Run,
        events: AsyncIterator[GuideEvent],
        *,
        visitor_id: uuid.UUID,
        thread_id: str | None,
        ga_client_id: str | None,
    ) -> AsyncIterator[GuideEvent]:
        """run 이 끝나면(방문자가 중간에 끊어도) 질문·답변을 기록한다."""
        started = time.perf_counter()
        first_token_ms: float | None = None
        mode = ""
        answer: list[str] = []
        completed = False
        try:
            async for event in events:
                if isinstance(event, ModeChanged):
                    mode = event.mode
                elif isinstance(event, TextDelta):
                    first_token_ms = first_token_ms or _elapsed_ms(started)
                    answer.append(event.text)
                yield event
            completed = True
        finally:
            run.trace.end(
                output="".join(answer),
                metadata={"mode": mode, "completed": completed, "anchors": run.anchors},
            )
            entry = GuideLogCreate(
                visitor_id=visitor_id,
                thread_id=thread_id,
                ga_client_id=ga_client_id,
                question=run.question,
                answer="".join(answer),
                mode=mode,
                scores=[round(hit.score, 4) for hit in run.hits],
                anchors=run.anchors,
                first_token_ms=first_token_ms,
                total_ms=_elapsed_ms(started),
                completed=completed,
                input_tokens=run.usage.input_tokens,
                output_tokens=run.usage.output_tokens,
                reasoning_tokens=run.usage.reasoning_tokens,
                cached_tokens=run.usage.cached_tokens,
                trace_id=run.trace.trace_id,
            )
            # 중간에 끊긴 답은 방문자가 다 보지 못했으므로 맥락에 넣지 않는다.
            turn = (
                GuideTurn(run.question, entry.answer, run.anchors)
                if completed and thread_id and entry.answer
                else None
            )
            # 답을 다 보낸 직후 연결이 끊겨도 기록·맥락 저장이 끝까지 돌도록 한 task 로 묶는다.
            task = asyncio.create_task(self._save(entry, visitor_id, thread_id, turn))
            _saving.add(task)
            task.add_done_callback(_saving.discard)
            await asyncio.shield(task)

    async def _recent(self, visitor_id: uuid.UUID, thread_id: str) -> list[GuideTurn]:
        # 맥락을 못 읽어도 이번 질문에는 맥락 없이 답한다.
        try:
            return await self._history.recent(visitor_id, thread_id)
        except Exception:
            logger.exception("안내 대화 맥락 읽기 실패")
            return []

    async def _save(
        self,
        entry: GuideLogCreate,
        visitor_id: uuid.UUID,
        thread_id: str | None,
        turn: GuideTurn | None,
    ) -> None:
        # 기록과 맥락은 부가 기능이라 실패해도 방문자 응답을 깨지 않는다.
        try:
            await self._logs.record(entry)
        except Exception:
            logger.exception("안내 기록 저장 실패")
        if turn is None or thread_id is None:
            return
        try:
            await self._history.append(visitor_id, thread_id, turn)
        except Exception:
            logger.exception("안내 대화 맥락 저장 실패")

    async def _llm_run(
        self, run: _Run, character: CharacterRead, relevant: list[SearchHit]
    ) -> AsyncIterator[GuideEvent]:
        yield ModeChanged("llm")
        yield SourcesFound(run.sources)
        started = time.perf_counter()
        first_token_ms: float | None = None
        parser = MarkerParser()
        wrote_text = False
        generation: Step | None = None
        raw: list[str] = []
        failure: LLMError | None = None
        try:
            system = await self._system_prompt(character)
            messages = self._messages(run, relevant)
            generation = run.trace.step(
                "llm",
                kind="generation",
                model=self._llm.model,
                input=[
                    {"role": "system", "content": system},
                    *({"role": m.role, "content": m.content} for m in messages),
                ],
            )
            # system 은 모든 방문자에게 같으므로 키 하나로 묶어 프롬프트 캐시를 맞춘다.
            stream = self._llm.stream(
                system, messages, run.usage, cache_key=f"guide:{self._options.character_slug}"
            )
            async for delta in stream:
                if first_token_ms is None:
                    first_token_ms = round((time.perf_counter() - started) * 1000, 1)
                    generation.first_token()
                raw.append(delta)
                for event in self._pieces(run, parser.feed(delta)):
                    wrote_text = wrote_text or isinstance(event, TextDelta)
                    yield event
            for event in self._pieces(run, parser.flush()):
                yield event
        except LLMError as exc:
            failure = exc
        finally:
            # 표시가 섞인 LLM 원문을 남겨 위치 표시가 버려진 이유를 볼 수 있게 한다.
            if generation is not None:
                generation.end(
                    output="".join(raw),
                    usage=run.usage,
                    error=str(failure) if failure else None,
                )
        if failure is not None:
            logger.warning("안내 LLM 실패, 폴백으로 전환", extra={"error": str(failure)})
            async for event in self._fallback_run(run, announce_sources=False, separate=wrote_text):
                yield event
            return
        yield TextEnded()
        logger.info(
            "안내 응답",
            extra={
                "first_token_ms": first_token_ms,
                "total_ms": round((time.perf_counter() - started) * 1000, 1),
                "markers": run.markers,
                "dropped_markers": parser.dropped + run.dropped,
            },
        )

    async def _fallback_run(
        self, run: _Run, *, announce_sources: bool, separate: bool = False
    ) -> AsyncIterator[GuideEvent]:
        yield ModeChanged("fallback")
        if announce_sources:
            yield SourcesFound(run.sources)
        top = run.hits[0] if run.hits else None
        anchor = (top.meta or {}).get("anchor") if top else None
        section = run.locations.get(anchor) if anchor else None
        acting = (
            top is not None and section is not None and top.score >= self._options.action_min_score
        )

        if acting and section is not None:
            text = TEXT_ACTION.format(title=section.title)
        elif run.sources:
            text = TEXT_SOURCES_ONLY
        else:
            text = TEXT_NOTHING
        yield TextDelta(f"\n\n{text}" if separate else text)
        yield TextEnded()
        if acting and section is not None:
            for event in run.show(section.anchor, best_quote(run.question, section.body)):
                yield event

    def _pieces(self, run: _Run, pieces: list[Piece]) -> list[GuideEvent]:
        events: list[GuideEvent] = []
        for piece in pieces:
            if isinstance(piece, ShowPiece):
                events.extend(run.show(piece.anchor, piece.quote))
            elif isinstance(piece, ViewPiece):
                events.extend(run.view(piece.view))
            elif piece.text:
                events.append(TextDelta(piece.text))
        return events

    async def _system_prompt(self, character: CharacterRead) -> str:
        """질문마다 바뀌는 자료는 넣지 않는다. 앞부분이 같아야 프롬프트 캐시가 맞는다."""
        base = await self._characters.system_prompt(character.id, [], GUIDE_REPLY)
        return f"{base}\n\n{_GUIDE_RULES}"

    def _messages(self, run: _Run, relevant: list[SearchHit]) -> list[ChatMessage]:
        """최근 턴은 원문으로, 그 앞은 질문만 넣는다. 자료와 이번 질문은 마지막 user 메시지에."""
        options = self._options
        keep = options.history_turns
        recent = run.history[-keep:] if keep else []
        older = run.history[: len(run.history) - len(recent)]
        messages: list[ChatMessage] = []
        for turn in recent:
            messages.append(ChatMessage("user", turn.question))
            messages.append(
                ChatMessage("assistant", _remembered(turn, options.history_answer_max_chars))
            )
        parts = []
        if older:
            parts.append("## 앞서 나온 질문\n" + "\n".join(f"- {t.question}" for t in older))
        parts.append(_materials(relevant, run.locations))
        parts.append(f"## 질문\n{run.question}")
        messages.append(ChatMessage("user", "\n\n".join(parts)))
        return messages


class _Run:
    """run 하나의 상태. 직전 navigate 위치를 기억해 같은 탭이면 highlight 만 보낸다."""

    def __init__(
        self,
        question: str,
        hits: list[SearchHit],
        sources: list[Source],
        locations: dict[str, SectionLocation],
        tools: set[str],
        trace: Trace,
        history: list[GuideTurn],
    ) -> None:
        self.question = question
        self.hits = hits
        self.sources = sources
        self.locations = locations
        self.tools = tools
        self.trace = trace
        self.history = history
        self.markers = 0
        self.dropped = 0
        self.anchors: list[str] = []
        self.usage = TokenUsage()
        self._shown: tuple[str, str] | None = None

    def view(self, view: str) -> list[GuideEvent]:
        if view not in VIEWS:
            self.dropped += 1
            logger.info("없는 화면을 버림", extra={"view": view})
            return []
        self.markers += 1
        self.anchors.append(f"view:{view}")
        place = (view, "")
        if place == self._shown or "navigate" not in self.tools:
            return []
        self._shown = place
        return [ToolCalled("navigate", {"view": view})]

    def show(self, anchor: str, quote: str | None) -> list[GuideEvent]:
        section = self.locations.get(anchor)
        if section is None:
            self.dropped += 1
            logger.info("없는 anchor 를 버림", extra={"anchor": anchor})
            return []
        self.markers += 1
        self.anchors.append(anchor)
        events: list[GuideEvent] = []
        place = (section.project_id, section.tab)
        if place != self._shown:
            self._shown = place
            if "navigate" in self.tools:
                events.append(
                    ToolCalled(
                        "navigate",
                        {"view": "project", "projectId": section.project_id, "tab": section.tab},
                    )
                )
        if "highlight" in self.tools:
            args: dict[str, str] = {"anchor": anchor}
            if quote and contains_quote(section.plain, quote):
                args["quote"] = quote
            elif quote:
                logger.info("섹션에 없는 quote 를 버림", extra={"anchor": anchor})
            events.append(ToolCalled("highlight", args))
        return events


def relevant_hits(hits: list[SearchHit], *, min_score: float, max_gap: float) -> list[SearchHit]:
    """점수순 `hits` 중 최소 점수 이상이면서 1위와 `max_gap` 이내인 것만 남긴다."""
    if not hits:
        return []
    floor = max(min_score, hits[0].score - max_gap)
    return [hit for hit in hits if hit.score >= floor]


def _materials(relevant: list[SearchHit], locations: dict[str, SectionLocation]) -> str:
    materials = []
    for i, hit in enumerate(relevant, start=1):
        section = locations.get((hit.meta or {}).get("anchor", ""))
        if section is not None:
            header = (
                f"[자료 {i}] anchor={section.anchor} "
                f"({section.project_title} > {section.tab_label} > {section.title})"
            )
        else:
            header = f"[자료 {i}] (기억 문서: {hit.title})"
        materials.append(f"{header}\n{hit.content}")
    if not materials:
        return "## 자료\n이번 질문과 관련된 자료를 찾지 못했다."
    return "## 자료\n질문과 관련해 찾은 내 자료다.\n\n" + "\n\n".join(materials)


def _remembered(turn: GuideTurn, max_chars: int) -> str:
    """앞선 답변. 길면 자르고, 띄웠던 위치는 답변과 같은 표시 형식으로 뒤에 붙인다.

    LLM 이 이 형식을 흉내 내도 표시로 해석돼 방문자에게 글자로 보이지 않는다.
    """
    answer = turn.answer
    if len(answer) > max_chars:
        answer = answer[:max_chars].rstrip() + "…"
    marks = "".join(
        f"[[{anchor}]]" if anchor.startswith("view:") else f"[[show:{anchor}]]"
        for anchor in dict.fromkeys(turn.anchors)
    )
    return answer + marks


def _traced_hit(hit: SearchHit) -> dict[str, object]:
    return {
        "title": hit.title,
        "anchor": (hit.meta or {}).get("anchor"),
        "score": round(hit.score, 4),
        "content": hit.content,
    }


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def _valid_ga_client_id(value: str | None) -> str | None:
    return value if value and GA_CLIENT_ID.fullmatch(value) else None


def _allowed_tools(capabilities: Sequence[str] | None) -> set[str]:
    if capabilities is None:
        return set(TOOLS)
    allowed = set()
    for capability in capabilities:
        name, _, version = capability.partition("@")
        if name in TOOLS and version == str(TOOLS[name]):
            allowed.add(name)
    return allowed


def _sources(hits: list[SearchHit], locations: dict[str, SectionLocation]) -> list[Source]:
    """anchor(기억 문서는 문서) 기준으로 중복을 빼고 상위 3개."""
    sources: list[Source] = []
    seen: set[str] = set()
    for hit in hits:
        anchor = (hit.meta or {}).get("anchor")
        key = anchor or f"document:{hit.document_id}"
        if key in seen:
            continue
        seen.add(key)
        section = locations.get(anchor) if anchor else None
        sources.append(
            Source(
                title=f"{hit.title} > {section.title}" if section else hit.title,
                snippet=hit.content[:SNIPPET_LENGTH],
                score=round(min(max(hit.score, 0.0), 1.0), 4),
                location=SourceLocation(
                    project_id=section.project_id, tab=section.tab, anchor=section.anchor
                )
                if section
                else None,
            )
        )
        if len(sources) == MAX_SOURCES:
            break
    return sources
