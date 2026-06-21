from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from tavily import TavilyClient

from app.models import QuoteResponse, QuoteSearchResult, QuoteValidationResult

VALIDATION_SYSTEM_PROMPT = (
    "You verify whether a quote is plausibly a real quote from the stated real person. "
    "Use only the provided web search results as evidence. "
    "Return a conservative judgment. If the evidence is weak, mark it invalid. "
    "Mark it invalid when the Korean quote and original quote do not express the same meaning. "
    "Mark it invalid when search results support only the author or topic but not the quote text. "
    "When valid, include the most relevant source URL from the search results."
)


class QuoteValidator:
    def __init__(
        self,
        *,
        tavily_api_key: str | None,
        region_name: str,
        model_id: str,
        endpoint_url: str | None = None,
        temperature: float = 0.0,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled and bool(tavily_api_key)
        self.search_client = TavilyClient(api_key=tavily_api_key) if self.enabled else None
        self.model = ChatBedrockConverse(
            model=model_id,
            region_name=region_name,
            base_url=endpoint_url,
            temperature=temperature,
            max_tokens=400,
        ).with_structured_output(QuoteValidationResult)

    def search_quote_source(self, quote: QuoteResponse) -> list[QuoteSearchResult]:
        if not self.enabled or self.search_client is None:
            return []
        if _is_missing_source(quote.source) or _is_vague_source(quote.source):
            return []

        response = self.search_client.search(
            query=_build_search_query(quote),
            search_depth="basic",
            max_results=5,
            include_answer=False,
            include_raw_content=False,
        )
        return [
            QuoteSearchResult(
                title=result.get("title", ""),
                url=result.get("url", ""),
                content=result.get("content", ""),
            )
            for result in response.get("results", [])
        ]

    def validate_quote(
        self, quote: QuoteResponse, search_results: list[QuoteSearchResult]
    ) -> QuoteValidationResult:
        if not self.enabled:
            return QuoteValidationResult(
                is_valid=True,
                confidence=0.0,
                reason="Validation skipped because Tavily is not configured.",
            )
        if _is_missing_source(quote.source) or _is_vague_source(quote.source):
            return QuoteValidationResult(
                is_valid=False,
                confidence=0.0,
                reason="The quote candidate does not include a concrete source.",
            )
        if not search_results:
            return QuoteValidationResult(
                is_valid=False,
                confidence=0.0,
                reason="No web search evidence was found for the quote and author.",
            )

        prompt = (
            "Quote candidate:\n"
            f"- Korean quote: {quote.quote}\n"
            f"- Original quote: {quote.original_quote or 'unknown'}\n"
            f"- Author: {quote.author or 'unknown'}\n"
            f"- Source/context: {quote.source or 'unknown'}\n\n"
            "Search results:\n"
            f"{_format_search_results(search_results)}\n\n"
            "Decide whether the exact quote, or a faithful Korean translation of the exact quote, "
            "is supported by these search results."
        )
        response = self.model.invoke(
            [SystemMessage(content=VALIDATION_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        validation = QuoteValidationResult.model_validate(response)
        return _enforce_validation_quality(validation)


def _build_search_query(quote: QuoteResponse) -> str:
    searchable_quote = quote.original_quote or quote.quote
    parts = [part for part in [quote.author, searchable_quote, quote.source] if part]
    return " ".join(parts)


def _is_missing_source(source: str | None) -> bool:
    if source is None:
        return True
    normalized = source.strip().lower()
    if not normalized:
        return True
    return normalized in {
        "unknown",
        "unknown source",
        "n/a",
        "none",
        "알 수 없음",
        "출처 없음",
        "미상",
        "불명",
    }


def _is_vague_source(source: str | None) -> bool:
    if source is None:
        return True
    normalized = source.strip().lower()
    vague_fragments = [
        "various",
        "attributed",
        "attributed to",
        "quote collection",
        "quote anthology",
    ]
    return any(fragment in normalized for fragment in vague_fragments)


def _enforce_validation_quality(validation: QuoteValidationResult) -> QuoteValidationResult:
    if not validation.is_valid:
        return validation
    if validation.confidence < 0.7:
        return QuoteValidationResult(
            is_valid=False,
            confidence=validation.confidence,
            reason=f"Validation confidence is too low. {validation.reason}",
            source_url=validation.source_url,
        )
    if not validation.source_url:
        return QuoteValidationResult(
            is_valid=False,
            confidence=validation.confidence,
            reason=f"Validation did not identify a concrete source URL. {validation.reason}",
        )
    return validation


def _format_search_results(search_results: list[QuoteSearchResult]) -> str:
    return "\n".join(
        f"{index}. {result.title}\nURL: {result.url}\nSnippet: {result.content}"
        for index, result in enumerate(search_results, start=1)
    )
