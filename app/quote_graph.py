from datetime import date
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import Settings
from app.daily_quote_store import DailyQuoteStore
from app.models import DailyQuoteItem, QuoteResponse, QuoteSearchResult, QuoteValidationResult
from app.quote_agent import QuoteAgent
from app.quote_validator import QuoteValidator

CONTEXT_SIMILARITY_THRESHOLD = 0.53


class DailyQuoteGraphState(TypedDict, total=False):
    today: date
    settings: Settings
    agent: QuoteAgent
    validator: QuoteValidator
    daily_quote_store: DailyQuoteStore
    recent_history: list[DailyQuoteItem]
    recent_quotes: list[str]
    recent_themes: set[str]
    candidate: QuoteResponse
    search_results: list[QuoteSearchResult]
    validation: QuoteValidationResult
    saved_quote: DailyQuoteItem
    attempts: int
    max_attempts: int
    error: str
    repetition_reason: str


class DailyQuoteGraph:
    def __init__(self) -> None:
        graph = StateGraph(DailyQuoteGraphState)
        graph.add_node("load_today_quote", self._load_today_quote)
        graph.add_node("load_recent_quotes", self._load_recent_quotes)
        graph.add_node("generate_quote_candidate", self._generate_quote_candidate)
        graph.add_node("check_korean_quote", self._check_korean_quote)
        graph.add_node("search_quote_source", self._search_quote_source)
        graph.add_node("validate_real_quote", self._validate_real_quote)
        graph.add_node("check_theme_repetition", self._check_theme_repetition)
        graph.add_node("save_daily_quote", self._save_daily_quote)

        graph.add_edge(START, "load_today_quote")
        graph.add_conditional_edges(
            "load_today_quote",
            self._route_after_today_lookup,
            {"existing": END, "generate": "load_recent_quotes"},
        )
        graph.add_edge("load_recent_quotes", "generate_quote_candidate")
        graph.add_edge("generate_quote_candidate", "check_korean_quote")
        graph.add_conditional_edges(
            "check_korean_quote",
            self._route_after_korean_check,
            {
                "retry": "generate_quote_candidate",
                "search": "search_quote_source",
                "failed": END,
            },
        )
        graph.add_edge("search_quote_source", "validate_real_quote")
        graph.add_conditional_edges(
            "validate_real_quote",
            self._route_after_validation,
            {
                "retry": "generate_quote_candidate",
                "check_theme": "check_theme_repetition",
                "failed": END,
            },
        )
        graph.add_conditional_edges(
            "check_theme_repetition",
            self._route_after_theme_check,
            {
                "retry": "generate_quote_candidate",
                "save": "save_daily_quote",
                "failed": END,
            },
        )
        graph.add_edge("save_daily_quote", END)
        self._graph = graph.compile()

    def run(
        self,
        *,
        today: date,
        settings: Settings,
        agent: QuoteAgent,
        validator: QuoteValidator,
        daily_quote_store: DailyQuoteStore,
    ) -> DailyQuoteItem:
        state = self._graph.invoke(
            {
                "today": today,
                "settings": settings,
                "agent": agent,
                "validator": validator,
                "daily_quote_store": daily_quote_store,
                "attempts": 0,
                "max_attempts": settings.quote_generation_attempts,
            }
        )
        saved_quote = state.get("saved_quote")
        if saved_quote is None:
            detail = state.get("error") or "Could not generate a daily quote."
            raise DailyQuoteGraphError(detail)
        return saved_quote

    @staticmethod
    def _load_today_quote(state: DailyQuoteGraphState) -> DailyQuoteGraphState:
        today_quote = state["daily_quote_store"].get_today_quote(state["today"])
        if today_quote is None:
            return {}
        return {"saved_quote": today_quote}

    @staticmethod
    def _route_after_today_lookup(state: DailyQuoteGraphState) -> Literal["existing", "generate"]:
        if state.get("saved_quote") is not None:
            return "existing"
        return "generate"

    @staticmethod
    def _load_recent_quotes(state: DailyQuoteGraphState) -> DailyQuoteGraphState:
        recent_history = state["daily_quote_store"].get_recent_daily_quotes(
            limit=state["settings"].duplicate_check_limit
        )
        recent_themes = {
            item.theme.strip().lower()
            for item in recent_history
            if item.theme is not None and item.theme.strip()
        }
        return {
            "recent_history": recent_history,
            "recent_quotes": [item.quote for item in recent_history],
            "recent_themes": recent_themes,
        }

    @staticmethod
    def _generate_quote_candidate(state: DailyQuoteGraphState) -> DailyQuoteGraphState:
        quote = state["agent"].generate_daily_quote(
            state["today"], recent_quotes=state.get("recent_quotes", [])
        )
        return {"candidate": quote, "attempts": state.get("attempts", 0) + 1}

    @staticmethod
    def _check_korean_quote(state: DailyQuoteGraphState) -> DailyQuoteGraphState:
        candidate = state["candidate"]
        if _is_korean_user_facing_quote(candidate):
            return {}
        if state.get("attempts", 0) >= state["max_attempts"]:
            return {"error": "Could not generate a Korean-only quote. Please try again."}
        return {}

    @staticmethod
    def _route_after_korean_check(
        state: DailyQuoteGraphState,
    ) -> Literal["retry", "search", "failed"]:
        if state.get("error"):
            return "failed"
        if not _is_korean_user_facing_quote(state["candidate"]):
            return "retry"
        return "search"

    @staticmethod
    def _search_quote_source(state: DailyQuoteGraphState) -> DailyQuoteGraphState:
        return {
            "search_results": state["validator"].search_quote_source(state["candidate"])
        }

    @staticmethod
    def _validate_real_quote(state: DailyQuoteGraphState) -> DailyQuoteGraphState:
        validation = state["validator"].validate_quote(
            state["candidate"], state.get("search_results", [])
        )
        if not validation.is_valid and state.get("attempts", 0) >= state["max_attempts"]:
            return {
                "validation": validation,
                "error": "Could not validate a real quote from the provided author/source.",
            }
        return {"validation": validation}

    @staticmethod
    def _route_after_validation(
        state: DailyQuoteGraphState,
    ) -> Literal["retry", "check_theme", "failed"]:
        if state.get("error"):
            return "failed"
        validation = state.get("validation")
        if validation is not None and not validation.is_valid:
            return "retry"
        return "check_theme"

    @staticmethod
    def _check_theme_repetition(state: DailyQuoteGraphState) -> DailyQuoteGraphState:
        candidate = state["candidate"]
        quote_theme = candidate.theme.strip().lower() if candidate.theme else None
        if quote_theme is not None and quote_theme in state.get("recent_themes", set()):
            if state.get("attempts", 0) >= state["max_attempts"]:
                return {
                    "error": "Could not generate a non-repetitive quote theme. Please try again.",
                    "repetition_reason": "theme",
                }
            return {"repetition_reason": "theme"}

        similar_quote = _find_similar_context(candidate, state.get("recent_history", []))
        if similar_quote is None:
            return {}

        if state.get("attempts", 0) >= state["max_attempts"]:
            return {"repetition_reason": "context"}
        return {"repetition_reason": "context"}

    @staticmethod
    def _route_after_theme_check(
        state: DailyQuoteGraphState,
    ) -> Literal["retry", "save", "failed"]:
        if state.get("error"):
            return "failed"
        candidate = state["candidate"]
        quote_theme = candidate.theme.strip().lower() if candidate.theme else None
        if quote_theme is not None and quote_theme in state.get("recent_themes", set()):
            return "retry"
        if (
            _find_similar_context(candidate, state.get("recent_history", [])) is not None
            and state.get("attempts", 0) < state["max_attempts"]
        ):
            return "retry"
        return "save"

    @staticmethod
    def _save_daily_quote(state: DailyQuoteGraphState) -> DailyQuoteGraphState:
        saved_quote = state["daily_quote_store"].save_daily_quote(
            today=state["today"],
            quote=state["candidate"],
            model=state["settings"].bedrock_model_id,
            validation=state.get("validation"),
        )
        if saved_quote is not None:
            return {"saved_quote": saved_quote}

        concurrently_saved_quote = state["daily_quote_store"].get_today_quote(state["today"])
        if concurrently_saved_quote is not None:
            return {"saved_quote": concurrently_saved_quote}

        return {"error": "Could not save today's quote. Please try again."}


class DailyQuoteGraphError(Exception):
    pass


def _find_similar_context(
    candidate: QuoteResponse, recent_history: list[DailyQuoteItem]
) -> DailyQuoteItem | None:
    candidate_text = _context_text(candidate)
    for item in recent_history:
        similarity = max(
            _text_similarity(candidate.quote, item.quote),
            _text_similarity(candidate_text, _context_text(item)),
        )
        if similarity >= CONTEXT_SIMILARITY_THRESHOLD:
            return item
    return None


def _context_text(quote: QuoteResponse) -> str:
    parts = [
        quote.quote,
        quote.original_quote or "",
        quote.theme or "",
        quote.commentary,
    ]
    return " ".join(parts)


def _is_korean_user_facing_quote(quote: QuoteResponse) -> bool:
    required_texts = [
        quote.quote,
        quote.theme or "",
        quote.commentary,
        quote.reflection_question,
    ]
    return all(_contains_hangul(text) for text in required_texts)


def _contains_hangul(text: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in text)


def _text_similarity(left: str, right: str) -> float:
    left_tokens = _char_ngrams(left)
    right_tokens = _char_ngrams(right)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union


def _char_ngrams(text: str, size: int = 3) -> set[str]:
    normalized = "".join(char.lower() for char in text if char.isalnum())
    if len(normalized) <= size:
        return {normalized} if normalized else set()
    return {
        normalized[index : index + size]
        for index in range(0, len(normalized) - size + 1)
    }
