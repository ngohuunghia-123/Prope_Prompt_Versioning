# Prompt conversion CLI

This playground calls `POST /api/v1/prompt-conversions` and prints the XML
preview. It never saves a prompt or revision.

```powershell
pip install -r requirements.txt
$env:ADMIN_SESSION_TOKEN = '<development bootstrap token from .env>'
python main.py convert --file .\prompt.md
python main.py convert --format yaml --text 'task: Summarize {{topic}}'
```

Use `--prompt-id` when testing conversion for an existing prompt. The API then
checks `revision.create`; without it, the API checks `prompt.create`.

For the Docker development stack, the CLI defaults to `ADMIN_SESSION_TOKEN`.
Use `--base-url http://localhost:8080`; the application port is internal to
Docker. The bootstrap token is rejected by the application unless
`APP_ENV=development`. The CLI reads this value from the repository `.env`, so
setting it in the terminal is optional.
