import html
import json
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import ClientError


def _parse_emails(raw_value: str) -> list[str]:
    return [email.strip() for email in raw_value.split(",") if email.strip()]


def _load_active_user_emails(region: str, today: datetime | None = None) -> list[str]:
    users_table_name = os.environ.get("QUOTE_USERS_TABLE_NAME")
    if not users_table_name:
        return _parse_emails(os.environ["QUOTE_USER_EMAILS"])

    current_day = today or datetime.now(ZoneInfo("Asia/Seoul"))
    is_weekend = current_day.weekday() >= 5
    table = boto3.resource("dynamodb", region_name=region).Table(users_table_name)
    response = table.scan()
    emails = [
        item["email"]
        for item in response.get("Items", [])
        if _should_send_to_user(item, is_weekend)
    ]
    return list(dict.fromkeys(emails))


def _should_send_to_user(item: dict, is_weekend: bool) -> bool:
    if not item.get("email") or not item.get("is_active", True):
        return False
    if not is_weekend:
        return True
    return bool(item.get("send_on_weekends", False))


def _build_email_body(quote_item: dict) -> tuple[str, str, str]:
    today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y년 %m월 %d일")
    subject = f"오늘의 명언 - {today}"

    quote = quote_item["quote"]
    author = quote_item.get("author")
    source = quote_item.get("source")
    commentary = quote_item["commentary"]
    reflection_question = quote_item["reflection_question"]
    attribution = f" - {author}" if author else ""
    source_line = f"\n출처/맥락\n{source}\n" if source else ""

    text_body = (
        f"오늘의 명언 - {today}\n\n"
        f"{quote}{attribution}\n"
        f"{source_line}\n"
        f"해설\n{commentary}\n\n"
        f"생각해볼 질문\n{reflection_question}\n"
    )

    escaped_quote = html.escape(quote)
    escaped_author = html.escape(author) if author else ""
    escaped_source = html.escape(source) if source else ""
    escaped_commentary = html.escape(commentary)
    escaped_question = html.escape(reflection_question)
    escaped_subject = html.escape(subject)
    author_html = (
        f'<p style="margin:14px 0 0; font-size:16px; line-height:1.5; color:#496580;">- {escaped_author}</p>'
        if author
        else ""
    )
    source_html = (
        f'<p style="margin:6px 0 0; font-size:13px; line-height:1.5; color:#64748b;">{escaped_source}</p>'
        if source
        else ""
    )

    html_body = f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escaped_subject}</title>
  </head>
  <body style="margin:0; padding:0; background:#f4f7fb; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,'Apple SD Gothic Neo','Malgun Gothic',sans-serif; color:#172033;">
    <div style="display:none; max-height:0; overflow:hidden; opacity:0; color:transparent;">
      {escaped_quote}
    </div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f7fb; margin:0; padding:32px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px; background:#ffffff; border-radius:18px; overflow:hidden; border:1px solid #e5ebf3; box-shadow:0 10px 30px rgba(28,43,68,0.08);">
            <tr>
              <td style="background:#17324d; padding:28px 30px; color:#ffffff;">
                <div style="font-size:13px; line-height:1.4; color:#b9d7ef; letter-spacing:0.04em; text-transform:uppercase;">Daily Quote</div>
                <h1 style="margin:8px 0 0; font-size:28px; line-height:1.25; font-weight:800; letter-spacing:0;">오늘의 명언</h1>
                <div style="margin-top:10px; font-size:14px; line-height:1.6; color:#d9e7f4;">{today}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:34px 30px 18px;">
                <div style="font-size:14px; font-weight:700; color:#496580; margin-bottom:12px;">QUOTE</div>
                <div style="border-left:5px solid #f2b84b; padding:4px 0 4px 20px;">
                  <p style="margin:0; font-size:25px; line-height:1.55; font-weight:800; color:#111827; word-break:keep-all;">“{escaped_quote}”</p>
                  {author_html}
                  {source_html}
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 30px 0;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc; border:1px solid #e5ebf3; border-radius:14px;">
                  <tr>
                    <td style="padding:22px 22px 20px;">
                      <div style="font-size:14px; font-weight:800; color:#17324d; margin-bottom:10px;">해설</div>
                      <p style="margin:0; font-size:16px; line-height:1.75; color:#334155; word-break:keep-all;">{escaped_commentary}</p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 30px 34px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#fff8eb; border:1px solid #f6dfb5; border-radius:14px;">
                  <tr>
                    <td style="padding:22px 22px 20px;">
                      <div style="font-size:14px; font-weight:800; color:#8a5a08; margin-bottom:10px;">오늘의 질문</div>
                      <p style="margin:0; font-size:17px; line-height:1.7; color:#3f2f12; word-break:keep-all;">{escaped_question}</p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:18px 30px 26px; background:#f8fafc; border-top:1px solid #e5ebf3;">
                <p style="margin:0; font-size:12px; line-height:1.6; color:#64748b;">Daily Quote Agent가 Amazon Bedrock으로 생성하고 SES로 발송한 메시지입니다.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""

    return subject, text_body, html_body


def lambda_handler(event, context):
    base_url = os.environ["QUOTE_API_BASE_URL"].rstrip("/")
    today_path = os.environ.get("QUOTE_TODAY_PATH", "/daily-quote/today")
    timeout = int(os.environ.get("QUOTE_API_TIMEOUT_SECONDS", "20"))
    source_email = os.environ["QUOTE_EMAIL_SOURCE"]
    region = os.environ.get("AWS_REGION", "ap-northeast-2")
    user_emails = _load_active_user_emails(region)
    ses = boto3.client("sesv2", region_name=region)

    url = f"{base_url}/{today_path.lstrip('/')}"
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        quote_item = json.loads(response.read().decode("utf-8"))
        quote_status_code = response.status

    subject, text_body, html_body = _build_email_body(quote_item)

    results = []
    for user_email in user_emails:
        result = {
            "user_email": user_email,
            "quote_status_code": quote_status_code,
            "quote_url": url,
            "quote_theme": quote_item.get("theme"),
        }
        try:
            email_response = ses.send_email(
                FromEmailAddress=source_email,
                Destination={"ToAddresses": [user_email]},
                Content={
                    "Simple": {
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {
                            "Text": {"Data": text_body, "Charset": "UTF-8"},
                            "Html": {"Data": html_body, "Charset": "UTF-8"},
                        },
                    }
                },
            )
            result.update(
                {
                    "status": "sent",
                    "ses_message_id": email_response["MessageId"],
                }
            )
        except ClientError as error:
            error_info = error.response.get("Error", {})
            result.update(
                {
                    "status": "failed",
                    "error_code": error_info.get("Code", "Unknown"),
                    "error_message": error_info.get("Message", str(error)),
                }
            )
        results.append(result)

    result = {
        "sent_count": sum(1 for item in results if item["status"] == "sent"),
        "failed_count": sum(1 for item in results if item["status"] == "failed"),
        "results": results,
    }
    print(json.dumps(result, ensure_ascii=False))
    return result
