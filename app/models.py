from pydantic import BaseModel, Field


class QuoteResponse(BaseModel):
    quote: str = Field(..., description="The Korean quote text to show to users.")
    original_quote: str | None = Field(None, description="The original quote text, if available.")
    author: str | None = Field(None, description="The real person credited for the quote.")
    source: str | None = Field(None, description="Known work, speech, or context for the quote.")
    theme: str | None = Field(None, description="The main theme of the quote.")
    commentary: str = Field(..., description="A short explanation of the quote.")
    reflection_question: str = Field(..., description="A question for today's reflection.")


class DailyQuoteItem(QuoteResponse):
    quote_date: str
    created_at: str
    model: str
    validation_status: str | None = None
    validation_confidence: float | None = None
    validation_reason: str | None = None
    source_url: str | None = None


class UserItem(BaseModel):
    email: str
    is_active: bool = True
    send_on_weekends: bool = False
    created_at: str | None = None


class QuoteSearchResult(BaseModel):
    title: str
    url: str
    content: str


class QuoteValidationResult(BaseModel):
    is_valid: bool
    confidence: float = Field(..., ge=0, le=1)
    reason: str
    source_url: str | None = None
