from datetime import date

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage

from app.models import QuoteResponse

SYSTEM_PROMPT = (
    "You generate one thoughtful daily quote for Korean readers. "
    "The quote, theme, commentary, and reflection question must be written in Korean only. "
    "Use a real quote, motto, or leadership principle from a real person, translated faithfully "
    "into Korean when needed. "
    "Include the original quote text and a concrete source, such as a book, speech, interview, "
    "letter, essay, company memo, shareholder letter, or publication. "
    "Do not use unknown, unavailable, or vague source values. "
    "Never put English or any non-Korean-language text in the user-facing quote field. "
    "Do not invent the quote, author, or source. Avoid religious or political persuasion. "
    "Keep the tone calm and warm."
)


class QuoteAgent:
    def __init__(
        self, region_name: str, model_id: str, endpoint_url: str | None = None, temperature: float = 1.0
    ) -> None:
        self.model = ChatBedrockConverse(
            model=model_id,
            region_name=region_name,
            base_url=endpoint_url,
            temperature=temperature,
            max_tokens=500,
        ).with_structured_output(QuoteResponse)

    def generate_daily_quote(
        self, today: date | None = None, recent_quotes: list[str] | None = None
    ) -> QuoteResponse:
        current_date = today or date.today()
        recent_quote_text = _format_recent_quotes(recent_quotes or [])
        user_prompt = (
            f"오늘 날짜는 {current_date.isoformat()}입니다. "
            "실제 인물이 남긴 널리 알려진 명언, 좌우명, 리더십 원칙 중 1개를 한국어로 소개하고, "
            "원문, 저자, 검증 가능한 구체적인 출처나 맥락, 한 단어 수준의 주제, "
            "짧은 해설, 오늘의 질문을 만들어주세요. 아래 최근 명언들과 "
            "표현, 의미, 주제가 겹치지 않게 해주세요. 특히 최근 30일 안에 "
            "자기 변화, 세상 변화, 삶의 짧음, 작은 행복처럼 비슷한 맥락이 있으면 "
            "다른 맥락의 명언을 선택하세요. CEO, 창업자, 경영자, 감독, 개발자, 연구자 등 "
            "현대 리더의 인터뷰, 연설, 저서, 사내 메모, 주주서한에 나온 좌우명을 사용해도 됩니다. "
            "출처를 알 수 없는 명언은 선택하지 마세요. "
            "quote, theme, commentary, reflection_question 필드는 반드시 한국어로만 작성하세요. "
            "영어 원문은 original_quote 필드에만 넣고 quote 필드에는 절대 넣지 마세요.\n"
            f"{recent_quote_text}"
        )

        response = self.model.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
        )
        return QuoteResponse.model_validate(response)


def _format_recent_quotes(recent_quotes: list[str]) -> str:
    if not recent_quotes:
        return "최근 명언 없음"
    return "\n".join(f"- {quote}" for quote in recent_quotes)
