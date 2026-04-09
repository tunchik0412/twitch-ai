# Gemini Stream Assistant

A Twitch Extension that integrates Google Gemini AI, allowing streamers to add an interactive AI assistant to their channel.

## Features

- **AI-Powered Chat**: Viewers can ask questions and get AI-generated responses
- **Quick Commands**: Built-in commands for jokes, facts, and playful roasts
- **Streamer Configuration**: Full control over bot behavior, enabled commands, and response style
- **Secure API Key Storage**: API keys are stored securely on the backend, never exposed to viewers
- **Customizable**: Multiple response styles, custom prompts, and bot name prefix

## Project Structure

```
twitch-ai/
├── manifest.json       # Twitch extension manifest
├── config.html         # Broadcaster configuration page
├── config.js           # Configuration page JavaScript
├── panel.html          # Viewer panel interface
├── panel.js            # Panel JavaScript
├── app.py              # Flask backend (EBS)
├── requirements.txt    # Python dependencies
├── render.yaml         # Render.com deployment config
└── README.md           # This file
```

## Setup Instructions

### 1. Create a Twitch Extension

1. Go to [Twitch Developer Console](https://dev.twitch.tv/console/extensions)
2. Click "Create Extension"
3. Fill in the basic information:
   - Name: "Gemini Stream Assistant"
   - Type: Panel
4. Note your **Client ID** and **Extension Secret**

### 2. Deploy the Backend to Render.com

1. Push this repository to GitHub
2. Go to [Render.com](https://render.com) and create a new Web Service
3. Connect your GitHub repository
4. Configure the service:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Add environment variables:
   - `TWITCH_EXTENSION_SECRET`: Your extension secret (base64 encoded, from Twitch)
   - `TWITCH_CLIENT_ID`: Your extension client ID
6. Deploy and note your service URL (e.g., `https://your-app.onrender.com`)

### 2b. Deploy on Hetzner (Docker Compose + Caddy)

Use this option if you want to self-host on a Hetzner server.

Prerequisites:
- A Hetzner VPS or Cloud server (Ubuntu/Debian)
- A domain/subdomain pointing to your server (for example, `ebs.example.com`)
- Ports `80` and `443` open

This repo includes:
- `docker-compose.hetzner.yml` (EBS API + bot worker + Caddy)
- `.env.hetzner.example` (environment template)
- `deploy/hetzner/Caddyfile` (TLS reverse proxy)

Server setup:

```bash
# Install Docker and the compose plugin
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker

# Clone repository
git clone <your-repo-url>
cd twitch-ai

# Create env file and edit secrets
cp .env.hetzner.example .env.hetzner
```

Set these required values in `.env.hetzner`:
- `DOMAIN`
- `TWITCH_EXTENSION_SECRET`
- `TWITCH_CLIENT_ID`
- `TWITCH_TOKEN`
- `TWITCH_CHANNEL`
- `GEMINI_API_KEY`
- `EBS_URL` (for example, `https://ebs.example.com`)

Start services:

```bash
docker compose -f docker-compose.hetzner.yml up -d --build
```

Verify deployment:

```bash
docker compose -f docker-compose.hetzner.yml ps
docker compose -f docker-compose.hetzner.yml logs -f ebs
curl https://$DOMAIN/
```

Expected result:
- `https://$DOMAIN/` returns `Gemini Stream Assistant EBS is running`
- `https://$DOMAIN/api/*` is proxied to the Flask EBS service
- The bot runs continuously as a separate worker container

Update after new commits:

```bash
git pull
docker compose -f docker-compose.hetzner.yml up -d --build
```

### 3. Configure the Extension

1. In the Twitch Developer Console, go to your extension settings
2. Under "Asset Hosting", upload the frontend files:
   - `config.html`
   - `config.js`
   - `panel.html`
   - `panel.js`
3. Under "Extension Capabilities":
   - Enable "Panel" view
   - Set panel height to 400px
4. Under "Extension Backend Service":
   - Enter your backend URL (Render or Hetzner), e.g. `https://ebs.example.com`

### 4. Get a Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create a new API key
3. Copy the key (you'll enter it in the extension config)

### 5. Test the Extension

1. In the Twitch Developer Console, go to "Hosted Test"
2. Install the extension on your test channel
3. Open the config page and enter:
   - Your backend URL
   - Your Gemini API key
   - Configure commands and style
4. Save the configuration
5. Open the panel view to test

## Commands

| Command | Description |
|---------|-------------|
| `!ask [question]` | Ask the AI any question |
| `!joke` | Get a random joke |
| `!fact` | Learn an interesting fact |
| `!roast [@user]` | Get a playful roast |
| `!help` | Show available commands |

## Response Styles

- **Friendly & Casual**: Fun, engaging responses with emojis
- **Professional**: Clear, informative responses
- **Funny & Entertaining**: Witty, humorous responses
- **Lore-Friendly (RPG)**: Fantasy-themed responses

## Security

- API keys are stored on the backend only, never sent to viewers
- All requests are authenticated using Twitch Extension JWT tokens
- Configuration is only accessible to the broadcaster
- Rate limiting prevents abuse

## Local Development

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

### Frontend

Use the [Twitch Extension Developer Rig](https://dev.twitch.tv/docs/extensions/rig/) for local testing.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TWITCH_EXTENSION_SECRET` | Base64-encoded extension secret from Twitch |
| `TWITCH_CLIENT_ID` | Twitch extension client ID |
| `PORT` | Server port (default: 5000) |
| `FLASK_DEBUG` | Enable debug mode (default: false) |

## Troubleshooting

### "API key not configured"
- Make sure you've saved the configuration in the config page
- Check that your backend URL is correct

### "Connection failed"
- Verify your Render.com service is running
- Check the backend logs for errors

### Commands not working
- Ensure commands are enabled in the config
- Check the cooldown settings

## License

MIT License - Feel free to modify and use for your streams!
