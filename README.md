# Nook Antigravity Plugin

A real-time status and context token monitor for [Google Antigravity](https://antigravity.google) inside the [Nook](https://nooknotch.xyz) floating notch for Windows 10 and 11.

---

## ✨ Features

- **Dynamic Active Conversation Tracking**: Automatically detects whichever conversation you are currently active in inside Antigravity and displays its actual title.
- **Context Window Token Usage**: Visual progress ring and token counter displaying current context memory vs. model limit (e.g. `200k / 1,000k` for Gemini 3.8 Flash).
- **Color-coded Health Indicators**:
  - 🟢 **Accent**: Normal usage (< 60% of context window)
  - 🟡 **Yellow**: Elevated context (60% - 80%)
  - 🔴 **Red**: High context (> 80% — recommend running `/compact`) or Rate Limit warning
- **Detailed Session Breakdown**: Click the notch tile to view:
  - Active conversation title and step count
  - Prompt / Input tokens
  - Cache Read tokens (Google Cloud context caching)
  - Output tokens generated in the latest turn
  - Quick action buttons (Refresh, Copy Summary, Open Brain Folder)
- **Automatic Live Watcher**: Updates reactively every 3 seconds whenever your conversation progresses.

---

## 📋 Requirements

- **Windows 10 / 11**
- [Nook](https://nooknotch.xyz) (v0.3.0 or later)
- **Python 3.8+** (with Python available in PATH)
- [Google Antigravity](https://antigravity.google)

---

## 🚀 Installation

### Option 1: Via Git (Manual)

Open PowerShell and clone this repository into your Nook plugins directory:

```powershell
git clone https://github.com/paulorafsilva/nook-antigravity.git "$env:APPDATA\Nook\plugins\antigravity"
```

Then enable plugin developer mode in `%APPDATA%\Nook\config.toml` (or inside Nook Settings):

```toml
plugin_dev = true
```

Nook will detect and load the plugin immediately without needing a restart!

### Option 2: Nook Marketplace

Once published to the [Nook Plugins Marketplace](https://nooknotch.xyz/plugins), click **Install in Nook** to install with one click.

---

## 🛠️ How It Works

This plugin uses **Nook Plugin Protocol v1**. It runs as an independent, isolated process communicating over `stdin`/`stdout`:
1. Reads `conversation_summaries.db` from `%USERPROFILE%\.gemini\antigravity\` to resolve the most recently modified active conversation title and ID.
2. Parses the active conversation's `transcript.jsonl` to calculate exact token consumption (`input_tokens`, `cache_read_tokens`, `output_tokens`).
3. Streams declarative UI updates (`tile` and `page`) formatted in Nook's native glass design system.

---

## 🔒 Privacy & Safety

- **100% Local**: This plugin runs strictly offline on your local machine.
- No network requests are made; it reads local session statistics from your local `.gemini\antigravity\` directory.
- Runs with read-only access to Antigravity's local session logs.

---

## 📄 License

[MIT License](LICENSE)
