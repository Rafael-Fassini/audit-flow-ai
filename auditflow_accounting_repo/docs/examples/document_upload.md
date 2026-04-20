# Document Upload Example

Upload a supported accounting-process document:

```bash
curl -X POST "http://localhost:${APP_PORT:-8000}/documents/" \
  -H "X-Request-ID: local-upload-1" \
  -F "file=@samples/accounting_walkthrough.txt;type=text/plain"
```

Supported formats are `.pdf`, `.docx`, and `.txt`.

For local sample data, use short narratives that describe:
- the business event being posted
- account codes or account names used
- approval or review controls
- supporting evidence mentioned by the process owner
- known gaps or unresolved posting logic

Do not include production secrets, personal data, or confidential client records
in local samples.
