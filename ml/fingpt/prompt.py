

def build_fingpt_prompt(row):
    return f"""
You are a financial news analysis model.

Analyze the following NSE corporate announcement.

Company: {row['company_name']}
Symbol: {row['symbol']}
Event Type: {row['event_type']}
Date: {row['published_at']}

Announcement:
{row['content']}

Return:
1. Sentiment: POSITIVE / NEGATIVE / NEUTRAL
2. Event: What happened?
3. Financial Impact: HIGH / MEDIUM / LOW
4. Business Impact: HIGH / MEDIUM / LOW
5. Short-term Market Impact: POSITIVE / NEGATIVE / NEUTRAL
6. Reason: Brief explanation
""".strip()