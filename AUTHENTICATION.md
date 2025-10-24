# Authentication Setup

Frfr needs an Anthropic API key to run fact extraction. There are two ways to provide it:

## Option 1: Claude CLI Authentication (Recommended)

Use the Claude CLI to authenticate, and the API key will be automatically loaded:

```bash
cd ~/Development/frfr
./setup-auth
```

This will:
1. Install the Claude CLI in the Docker container
2. Start the authentication flow
3. You'll authorize in your browser
4. The API key will be stored and automatically loaded

**Then test it:**
```bash
docker compose exec frfr frfr extract-facts \
    /app/output/test_sample_100lines.txt \
    --chunk-size 50 \
    --overlap 10
```

## Option 2: Environment Variable

Set the API key directly in your environment:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-your-actual-key"

# Restart containers to pick it up
cd ~/Development/frfr
docker compose restart frfr
```

## How It Works

The fact extractor automatically searches for the API key in this order:

1. **Environment variable** `ANTHROPIC_API_KEY`
2. **Claude CLI config** at `~/.claude/config`
3. **Alternative locations** `~/.anthropic` or `~/.config/anthropic`

If no API key is found, you'll get a helpful error message.

## Verify Authentication

```bash
# This command will tell you if authentication is working
docker compose exec frfr frfr extract-facts --help
```

If the API key is set up correctly, the help will display. If not, you'll see an error when you try to run extraction.

## Troubleshooting

**Error: "No Anthropic API key found"**

Solution: Run `./setup-auth` or set the environment variable

**Error: "authentication_error: invalid x-api-key"**

Solution: Your API key may be expired or invalid. Re-authenticate with `./setup-auth`

**API key too short (< 50 characters)**

Solution: The placeholder key is still in the config. Run `./setup-auth` to set up properly
