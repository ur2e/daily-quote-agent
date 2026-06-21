from datetime import date

from fastapi.testclient import TestClient

from app.main import app, get_daily_quote_store, get_quote_agent, get_quote_validator
from app.models import DailyQuoteItem, QuoteResponse, QuoteValidationResult
from app.quote_validator import QuoteValidator


client = TestClient(app)


class FakeQuoteAgent:
    def __init__(self) -> None:
        self.calls = 0

    def generate_daily_quote(self, today=None, recent_quotes=None) -> QuoteResponse:
        self.calls += 1
        if self.calls == 1:
            return QuoteResponse(
                quote="이미 보낸 명언",
                author="테스트 저자",
                source="테스트 출처",
                theme="용기",
                commentary="중복 테스트용 명언입니다.",
                reflection_question="중복이면 어떻게 될까요?",
            )
        return QuoteResponse(
            quote="오늘의 작은 선택이 내일의 방향을 만든다.",
            author="테스트 인물",
            source="테스트 연설",
            theme="선택",
            commentary="테스트용 명언입니다.",
            reflection_question="오늘 선택하고 싶은 작은 행동은 무엇인가요?",
        )


class FakeSimilarContextAgent:
    def __init__(self) -> None:
        self.calls = 0

    def generate_daily_quote(self, today=None, recent_quotes=None) -> QuoteResponse:
        self.calls += 1
        if self.calls == 1:
            return QuoteResponse(
                quote="세상을 바꾸는 것은 어렵지만, 자신을 변화시키는 것은 가능하다.",
                original_quote="It is difficult to change the world, but possible to change ourselves.",
                author="테스트 저자",
                source="테스트 출처",
                theme="성장",
                commentary="세상 변화보다 자기 변화에 집중하라는 의미입니다.",
                reflection_question="오늘 바꾸고 싶은 내 태도는 무엇인가요?",
            )
        return QuoteResponse(
            quote="배움은 마음을 새로운 곳으로 데려간다.",
            original_quote="Learning carries the mind to new places.",
            author="테스트 인물",
            source="테스트 강연",
            theme="배움",
            commentary="오늘의 배움에 집중하게 하는 문장입니다.",
            reflection_question="오늘 새롭게 배우고 싶은 것은 무엇인가요?",
        )


class FakeEnglishFirstAgent:
    def __init__(self) -> None:
        self.calls = 0

    def generate_daily_quote(self, today=None, recent_quotes=None) -> QuoteResponse:
        self.calls += 1
        if self.calls == 1:
            return QuoteResponse(
                quote="Stay hungry, stay foolish.",
                original_quote="Stay hungry, stay foolish.",
                author="Steve Jobs",
                source="Stanford commencement address",
                theme="growth",
                commentary="Keep learning and trying.",
                reflection_question="What will you try today?",
            )
        return QuoteResponse(
            quote="계속 갈망하고, 계속 우직하게 나아가라.",
            original_quote="Stay hungry, stay foolish.",
            author="스티브 잡스",
            source="스탠퍼드 졸업식 연설",
            theme="도전",
            commentary="익숙함에 머무르지 말고 계속 배우라는 뜻입니다.",
            reflection_question="오늘 새롭게 시도할 일은 무엇인가요?",
        )


class FakeHistoryStore:
    def __init__(self) -> None:
        self.saved_items: list[DailyQuoteItem] = []
        self.today_quote: DailyQuoteItem | None = None

    def get_today_quote(self, today) -> DailyQuoteItem | None:
        return self.today_quote

    def get_recent_daily_quotes(self, limit: int) -> list[DailyQuoteItem]:
        return [
            DailyQuoteItem(
                quote_date="2026-05-23",
                created_at="2026-05-23T00:00:00+00:00",
                model="test-model",
                quote="이미 보낸 명언",
                author="테스트 저자",
                source="테스트 출처",
                theme="용기",
                commentary="이전 해설",
                reflection_question="이전 질문",
            )
        ]

    def save_daily_quote(
        self,
        today,
        quote: QuoteResponse,
        model: str,
        validation: QuoteValidationResult | None = None,
    ) -> DailyQuoteItem | None:
        item = DailyQuoteItem(
            quote_date=today.isoformat(),
            created_at="2026-05-24T00:00:00+00:00",
            model=model,
            quote=quote.quote,
            original_quote=quote.original_quote,
            author=quote.author,
            source=quote.source,
            theme=quote.theme,
            commentary=quote.commentary,
            reflection_question=quote.reflection_question,
            validation_status="valid" if validation and validation.is_valid else None,
            validation_confidence=validation.confidence if validation else None,
            validation_reason=validation.reason if validation else None,
            source_url=validation.source_url if validation else None,
        )
        self.saved_items.append(item)
        self.today_quote = item
        return item


class FakeQuoteValidator:
    def __init__(self) -> None:
        self.search_calls = 0
        self.validation_calls = 0

    def search_quote_source(self, quote: QuoteResponse) -> list:
        self.search_calls += 1
        return []

    def validate_quote(self, quote: QuoteResponse, search_results: list) -> QuoteValidationResult:
        self.validation_calls += 1
        return QuoteValidationResult(
            is_valid=True,
            confidence=0.9,
            reason="테스트에서는 외부 검색 검증을 생략합니다.",
            source_url="https://example.com/test-source",
        )


def test_health() -> None:
    response = client.get("/health")
    prefixed_response = client.get("/daily-quote/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert prefixed_response.status_code == 200
    assert prefixed_response.json() == {"status": "ok"}


def test_get_today_quote_saves_shared_non_duplicate_quote() -> None:
    fake_agent = FakeQuoteAgent()
    fake_store = FakeHistoryStore()
    fake_validator = FakeQuoteValidator()
    app.dependency_overrides[get_quote_agent] = lambda: fake_agent
    app.dependency_overrides[get_daily_quote_store] = lambda: fake_store
    app.dependency_overrides[get_quote_validator] = lambda: fake_validator

    response = client.get("/daily-quote/today", params={"user_email": "friend@example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["quote_date"] == date.today().isoformat()
    assert body["quote"] == "오늘의 작은 선택이 내일의 방향을 만든다."
    assert body["author"] == "테스트 인물"
    assert body["theme"] == "선택"
    assert body["validation_status"] == "valid"
    assert len(fake_store.saved_items) == 1
    assert fake_agent.calls == 2
    assert fake_validator.search_calls == 2

    app.dependency_overrides.clear()


def test_get_today_quote_retries_similar_recent_context() -> None:
    fake_agent = FakeSimilarContextAgent()
    fake_store = FakeHistoryStore()
    fake_validator = FakeQuoteValidator()
    fake_store.get_recent_daily_quotes = lambda limit: [
        DailyQuoteItem(
            quote_date="2026-06-10",
            created_at="2026-06-10T00:00:00+00:00",
            model="test-model",
            quote="세상을 바꾸는 것은 쉽지 않지만, 우리 자신을 변화시키는 것은 가능하다.",
            original_quote=(
                "Human beings, by changing the inner attitudes of their minds, "
                "can change the outer aspects of their lives."
            ),
            author="William James",
            source="테스트 출처",
            theme="변화",
            commentary="자기 변화가 세상에 대한 태도를 바꾼다는 의미입니다.",
            reflection_question="오늘 어떤 태도를 바꾸고 싶나요?",
        )
    ]
    app.dependency_overrides[get_quote_agent] = lambda: fake_agent
    app.dependency_overrides[get_daily_quote_store] = lambda: fake_store
    app.dependency_overrides[get_quote_validator] = lambda: fake_validator

    response = client.get("/daily-quote/today")

    assert response.status_code == 200
    assert response.json()["quote"] == "배움은 마음을 새로운 곳으로 데려간다."
    assert fake_agent.calls == 2
    assert len(fake_store.saved_items) == 1

    app.dependency_overrides.clear()


def test_get_today_quote_retries_non_korean_quote() -> None:
    fake_agent = FakeEnglishFirstAgent()
    fake_store = FakeHistoryStore()
    fake_validator = FakeQuoteValidator()
    app.dependency_overrides[get_quote_agent] = lambda: fake_agent
    app.dependency_overrides[get_daily_quote_store] = lambda: fake_store
    app.dependency_overrides[get_quote_validator] = lambda: fake_validator

    response = client.get("/daily-quote/today")

    assert response.status_code == 200
    body = response.json()
    assert body["quote"] == "계속 갈망하고, 계속 우직하게 나아가라."
    assert body["theme"] == "도전"
    assert fake_agent.calls == 2
    assert fake_validator.search_calls == 1
    assert len(fake_store.saved_items) == 1

    app.dependency_overrides.clear()


def test_get_today_quote_reuses_existing_shared_quote() -> None:
    fake_agent = FakeQuoteAgent()
    fake_store = FakeHistoryStore()
    fake_validator = FakeQuoteValidator()
    fake_store.today_quote = DailyQuoteItem(
        quote_date="2026-05-30",
        created_at="2026-05-30T00:00:00+00:00",
        model="test-model",
        quote="기존 오늘 명언",
        author="기존 인물",
        source="기존 출처",
        theme="성찰",
        commentary="기존 해설",
        reflection_question="기존 질문",
    )
    app.dependency_overrides[get_quote_agent] = lambda: fake_agent
    app.dependency_overrides[get_daily_quote_store] = lambda: fake_store
    app.dependency_overrides[get_quote_validator] = lambda: fake_validator

    first_response = client.get("/daily-quote/today", params={"user_email": "first@example.com"})
    second_response = client.get("/daily-quote/today", params={"user_email": "second@example.com"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["quote"] == second_response.json()["quote"]
    assert fake_agent.calls == 0
    assert fake_validator.search_calls == 0

    app.dependency_overrides.clear()


def test_get_recent_quotes() -> None:
    fake_store = FakeHistoryStore()
    app.dependency_overrides[get_daily_quote_store] = lambda: fake_store

    response = client.get("/daily-quote/recent")

    assert response.status_code == 200
    assert response.json()[0]["quote"] == "이미 보낸 명언"

    app.dependency_overrides.clear()


def test_legacy_quote_paths_still_work() -> None:
    fake_store = FakeHistoryStore()
    app.dependency_overrides[get_daily_quote_store] = lambda: fake_store

    response = client.get("/quote/recent")

    assert response.status_code == 200
    assert response.json()[0]["quote"] == "이미 보낸 명언"

    app.dependency_overrides.clear()


def test_quote_validator_rejects_missing_source() -> None:
    validator = QuoteValidator(
        tavily_api_key="test-key",
        region_name="ap-northeast-2",
        model_id="test-model",
    )
    quote = QuoteResponse(
        quote="세상을 바꾸는 것은 작은 행동부터 시작된다.",
        original_quote="Never doubt that a small group of thoughtful citizens can change the world.",
        author="Margaret Mead",
        source="알 수 없음",
        theme="변화",
        commentary="작은 행동의 힘을 말합니다.",
        reflection_question="오늘 어떤 작은 행동을 할 수 있나요?",
    )

    search_results = validator.search_quote_source(quote)
    validation = validator.validate_quote(quote, search_results)

    assert search_results == []
    assert validation.is_valid is False
    assert validation.reason == "The quote candidate does not include a concrete source."


def test_quote_validator_searches_speech_source_context() -> None:
    validator = QuoteValidator(
        tavily_api_key="test-key",
        region_name="ap-northeast-2",
        model_id="test-model",
    )
    calls = []
    validator.search_client.search = lambda **kwargs: (
        calls.append(kwargs)
        or {
            "results": [
                {
                    "title": "Mother Teresa speech transcript",
                    "url": "https://example.com/speech",
                    "content": "Speech transcript containing the quote.",
                }
            ]
        }
    )
    quote = QuoteResponse(
        quote="삶은 결코 완벽할 수 없지만, 그 속에서 작은 행복을 발견할 수 있다.",
        original_quote="Life is not perfect, but you can find small happiness within it.",
        author="마더 테레사",
        source="마더 테레사의 연설문 중에서",
        theme="행복",
        commentary="작은 행복을 발견하라는 의미입니다.",
        reflection_question="오늘 발견한 작은 행복은 무엇인가요?",
    )

    search_results = validator.search_quote_source(quote)

    assert len(search_results) == 1
    assert search_results[0].url == "https://example.com/speech"
    assert calls[0]["query"].endswith("마더 테레사의 연설문 중에서")
