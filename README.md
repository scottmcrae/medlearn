---
title: Medical Case Tutor
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# Medical Case Tutor

AI-powered medical case generator and Socratic tutor built with Chainlit and Claude.

## Local setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
chainlit run app.py
```

## Deploy to Railway

1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub repo
3. Select your repo
4. Add environment variable: `ANTHROPIC_API_KEY` = your key
5. Railway auto-deploys on every push

## Usage

### Commands
| Command | Description |
|---|---|
| `generate` | Generate a case with current settings |
| `specialty 3` | Set specialty by number |
| `format ed` | Set format: `short`, `full`, `hospital`, `soap`, `ed` |
| `complexity 2` | Set complexity by number (1-4) |
| `topic chest pain` | Set a specific topic or chief complaint |
| `socratic` | Switch to Socratic mode (AI asks you questions) |
| `answer` | Switch to answer-on-demand mode |
| `new` | Clear current case, generate another |
| `menu` | Show the full help menu |

### Tutor modes
- **Answer mode** — ask questions, get direct educational answers
- **Socratic mode** — AI guides you with questions, doesn't give answers away
