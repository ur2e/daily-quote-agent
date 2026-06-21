# EventBridge Scheduler Caller

This Lambda is a small bridge for scheduled daily quote delivery.

Flow:

```text
EventBridge Scheduler
  -> Lambda daily-quote-scheduler
  -> FastAPI /daily-quote/today
  -> DynamoDB users table
  -> Amazon SES email send
```

Example schedule:

```text
Schedule name: daily-quote-agent-daily
Expression: cron(30 7 * * ? *)
Timezone: Asia/Seoul
Target Lambda: daily-quote-scheduler
```

Lambda environment:

```text
QUOTE_API_BASE_URL=https://example.com
QUOTE_USERS_TABLE_NAME=daily-quote-users
QUOTE_USER_EMAILS=user@example.com,friend@example.com
QUOTE_EMAIL_SOURCE=sender@example.com
QUOTE_TODAY_PATH=/daily-quote/today
QUOTE_API_TIMEOUT_SECONDS=20
```

`QUOTE_USERS_TABLE_NAME` is preferred. When it is set, the Lambda loads active users from DynamoDB. `QUOTE_USER_EMAILS` is only a fallback when the table name is not configured.

SES sandbox note:

```text
ProductionAccessEnabled=false
```

If your AWS account is still in the SES sandbox, both sender and recipient email addresses must be verified. The Lambda sends both text and HTML email bodies.

Example configuration update:

```bash
aws lambda update-function-configuration \
  --function-name daily-quote-scheduler \
  --environment 'Variables={QUOTE_API_BASE_URL=https://example.com,QUOTE_TODAY_PATH=/daily-quote/today,QUOTE_USERS_TABLE_NAME=daily-quote-users,QUOTE_USER_EMAILS=user@example.com,QUOTE_EMAIL_SOURCE=sender@example.com,QUOTE_API_TIMEOUT_SECONDS=20}' \
  --region ap-northeast-2
```

Manual test:

```bash
aws lambda invoke \
  --function-name daily-quote-scheduler \
  --payload '{}' \
  /tmp/daily-quote-scheduler-response.json \
  --region ap-northeast-2
```
