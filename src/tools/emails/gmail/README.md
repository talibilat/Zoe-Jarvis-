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
python src/tools/emails/gmail/gmail_count.py
python src/tools/emails/gmail/gmail_count.py --enumerate --page-size 250
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
from src.tools.emails.gmail.gmail_unread import get_unread_count, get_unread_email_summary

total_unread = get_unread_count()
print(f"Unread emails: {total_unread}")

top_three = get_unread_email_summary(limit=3)
for email in top_three:
    print(email["subject"], email["from"])
```

### `gmail_upload.py`
Attachment upload helpers for Gmail drafts/messages.

#### Functions
- `gmail_create_draft_with_attachments(email_to, email_from, subject, body, attachment_paths)`  
  Builds a MIME message with one or more file attachments and creates a draft in Gmail.
- `gmail_send_email_with_attachments(email_to, email_from, subject, body, attachment_paths)`  
  Builds the same MIME message and sends it immediately via `users().messages().send`.
- `_validate_attachment_paths(attachment_paths)`  
  Internal path validation helper; raises if the list is empty, missing, or points to non-files.

#### Example
```python
from src.tools.emails.gmail.gmail_upload import gmail_create_draft_with_attachments

draft = gmail_create_draft_with_attachments(
    email_to="recipient@example.com",
    email_from="me",
    subject="Monthly report",
    body="Hi, attaching the report.",
    attachment_paths=["./reports/february.pdf"],
)
print(draft["id"])
```

### `gmail_send_email.py`
Standard send helper for non-attachment emails.

#### Functions
- `gmail_send_email(email_to, email_from, subject, body)`  
  Builds a plain MIME message and sends it using Gmail `users().messages().send`.

### `gmail_threads.py`
Thread inspection helper for longer conversations.

#### Functions
- `show_chatty_threads(min_messages=3, max_threads=100, query=None)`  
  Returns thread metadata (`thread_id`, `subject`, `message_count`) for threads meeting the message-count threshold and containing a subject line.

## Environment / Setup
- Enable the Gmail API and download OAuth credentials (`credentials.json`).
- On first run a browser window opens to authorize access; a `token.json` cache is saved for future calls.
