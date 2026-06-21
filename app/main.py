from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query

from app.config import Settings, get_settings
from app.daily_quote_store import DailyQuoteStore
from app.models import DailyQuoteItem
from app.quote_agent import QuoteAgent
from app.quote_graph import DailyQuoteGraph, DailyQuoteGraphError
from app.quote_validator import QuoteValidator

app = FastAPI(
    title="Daily Quote Agent",
    docs_url="/daily-quote/docs",
    openapi_url="/daily-quote/openapi.json",
    redoc_url="/daily-quote/redoc",
)
daily_quote_graph = DailyQuoteGraph()


@app.get("/health")
@app.get("/daily-quote/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def get_quote_agent(settings: Settings = Depends(get_settings)) -> QuoteAgent:
    return QuoteAgent(
        region_name=settings.aws_region,
        model_id=settings.bedrock_model_id,
        endpoint_url=settings.bedrock_endpoint_url,
        temperature=settings.bedrock_temperature,
    )


def get_daily_quote_store(settings: Settings = Depends(get_settings)) -> DailyQuoteStore:
    return DailyQuoteStore(
        daily_quotes_table_name=settings.dynamodb_daily_quotes_table_name,
        users_table_name=settings.dynamodb_users_table_name,
        region_name=settings.aws_region,
    )


def get_quote_validator(settings: Settings = Depends(get_settings)) -> QuoteValidator:
    return QuoteValidator(
        tavily_api_key=settings.tavily_api_key,
        region_name=settings.aws_region,
        model_id=settings.bedrock_model_id,
        endpoint_url=settings.bedrock_endpoint_url,
        enabled=settings.quote_validation_enabled,
    )


@app.get("/quote/today", response_model=DailyQuoteItem)
@app.get("/daily-quote/today", response_model=DailyQuoteItem)
def get_today_quote(
    user_email: str | None = Query(
        None, description="Deprecated. Daily quotes are now shared by all users."
    ),
    settings: Settings = Depends(get_settings),
    agent: QuoteAgent = Depends(get_quote_agent),
    validator: QuoteValidator = Depends(get_quote_validator),
    daily_quote_store: DailyQuoteStore = Depends(get_daily_quote_store),
) -> DailyQuoteItem:
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    try:
        return daily_quote_graph.run(
            today=today,
            settings=settings,
            agent=agent,
            validator=validator,
            daily_quote_store=daily_quote_store,
        )
    except DailyQuoteGraphError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/quote/recent", response_model=list[DailyQuoteItem])
@app.get("/daily-quote/recent", response_model=list[DailyQuoteItem])
def get_recent_quotes(
    limit: int = Query(10, ge=1, le=50),
    daily_quote_store: DailyQuoteStore = Depends(get_daily_quote_store),
) -> list[DailyQuoteItem]:
    return daily_quote_store.get_recent_daily_quotes(limit=limit)
