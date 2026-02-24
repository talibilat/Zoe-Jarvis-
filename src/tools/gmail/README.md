# Gmail Tools

This folder contains small helpers that integrate with the Gmail API via OAuth.
All modules assume `credentials.json` and `token.json` live in the project root.

## Files

### `gmail_count.py`
Counts the total number of emails (and threads) in the authenticated mailbox and,
when run with `--enumerate`, walks every message ID to verify the count.

#### Functions
- `enumerate_messages(service, batch_size=500, include_spam_trash=True)`  
  Returns the number of messages by paging through `users().messages().list`.  
  Parameters: a Gmail service, max results per call, and whether to include spam/trash.
- `count_total_emails()`  
  CLI entry point. Prints `emailAddress`, `messagesTotal`, `threadsTotal`, and optionally calls `enumerate_messages` if `--enumerate` is provided.

#### Example
```bash
python src/tools/gmail/gmail_count.py
python src/tools/gmail/gmail_count.py --enumerate --page-size 250
```

### `gmail_unread.py`
Utility functions (no CLI) to retrieve unread email metadata.

#### Functions
- `get_unread_count(query='is:unread', batch_size=500)`  
  Uses the shared Gmail client to count unread messages matching the Gmail search query. Returns an integer.
- `get_unread_email_summary(limit=None, query='is:unread')`  
  Returns a list of dictionaries describing unread messages (id, threadId, subject, sender, date, snippet). `limit` accepts an integer, `"all"`, or `None`.  
- Helper internals (`count_unread_messages`, `fetch_unread_emails`, `_normalize_limit`, `_extract_header`) are exposed for reuse but mainly support the two public helpers above.

#### Example
```python
from src.tools.gmail.gmail_unread import get_unread_count, get_unread_email_summary

total_unread = get_unread_count()
print(f"Unread emails: {total_unread}")

top_three = get_unread_email_summary(limit=3)
for email in top_three:
    print(email["subject"], email["from"])
```

## Environment / Setup
- Enable the Gmail API and download OAuth credentials (`credentials.json`).
- On first run a browser window opens to authorize access; a `token.json` cache is saved for future calls.
