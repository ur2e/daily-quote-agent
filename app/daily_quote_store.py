from datetime import date, datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from app.models import DailyQuoteItem, QuoteResponse, QuoteValidationResult, UserItem


class DailyQuoteStore:
    def __init__(self, daily_quotes_table_name: str, users_table_name: str, region_name: str) -> None:
        resource = boto3.resource("dynamodb", region_name=region_name)
        self.daily_quotes_table = resource.Table(daily_quotes_table_name)
        self.users_table = resource.Table(users_table_name)

    def get_today_quote(self, today: date) -> DailyQuoteItem | None:
        response = self.daily_quotes_table.get_item(Key={"quote_date": today.isoformat()})
        item = response.get("Item")
        if item is None:
            return None
        return DailyQuoteItem.model_validate(item)

    def get_recent_daily_quotes(self, limit: int) -> list[DailyQuoteItem]:
        response = self.daily_quotes_table.scan()
        items = [DailyQuoteItem.model_validate(item) for item in response.get("Items", [])]
        return sorted(items, key=lambda item: item.quote_date, reverse=True)[:limit]

    def save_daily_quote(
        self,
        today: date,
        quote: QuoteResponse,
        model: str,
        validation: QuoteValidationResult | None = None,
    ) -> DailyQuoteItem | None:
        item = DailyQuoteItem(
            quote_date=today.isoformat(),
            created_at=datetime.now(timezone.utc).isoformat(),
            model=model,
            quote=quote.quote,
            original_quote=quote.original_quote,
            author=quote.author,
            source=quote.source,
            theme=quote.theme,
            commentary=quote.commentary,
            reflection_question=quote.reflection_question,
            validation_status=_validation_status(validation),
            validation_confidence=validation.confidence if validation else None,
            validation_reason=validation.reason if validation else None,
            source_url=validation.source_url if validation else None,
        )
        try:
            self.daily_quotes_table.put_item(
                Item=_to_dynamodb_item(item),
                ConditionExpression="attribute_not_exists(quote_date)",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise
        return item

    def list_active_users(self) -> list[UserItem]:
        response = self.users_table.scan()
        users = [UserItem.model_validate(item) for item in response.get("Items", [])]
        return [user for user in users if user.is_active]


def _validation_status(validation: QuoteValidationResult | None) -> str | None:
    if validation is None:
        return None
    return "valid" if validation.is_valid else "invalid"


def _to_dynamodb_item(item: DailyQuoteItem) -> dict:
    dynamodb_item = item.model_dump()
    confidence = dynamodb_item.get("validation_confidence")
    if confidence is not None:
        dynamodb_item["validation_confidence"] = Decimal(str(confidence))
    return dynamodb_item
