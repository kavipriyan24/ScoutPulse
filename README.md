# 🚀 ScoutPulse: Multi-Agent Autonomous Price-Drop Scout

A production-ready, ₹0-cost autonomous multi-agent price drop scout built with **LangGraph**, **Google Gemini (`gemini-2.5-flash`)**, **Tavily AI**, and **Streamlit**.

---

## 📁 Project Structure
- `.env.example` / `.env` — API keys configuration
- `requirements.txt` — Python dependencies
- `database.py` — SQLite database layer (`watchlist.db`)
- `agents.py` — LangGraph multi-agent pipeline (Researcher ➔ Auditor ➔ Notifier)
- `app.py` — Streamlit dashboard + background 12-hour APScheduler + live execution trace viewer

---

## 🔑 Where to Paste Your 4 Free Keys in `.env`

Open the `.env` file in the workspace root and paste your free API keys:

1. **`GEMINI_API_KEY`**: Get your free Google AI Studio API key from [https://aistudio.google.com/](https://aistudio.google.com/)
2. **`TAVILY_API_KEY`**: Get your free 1,000 searches/month key from [https://tavily.com/](https://tavily.com/)
3. **`TELEGRAM_BOT_TOKEN`**: Create a free bot via [@BotFather](https://t.me/BotFather) on Telegram and get your HTTP API token.
4. **`TELEGRAM_CHAT_ID`**: Send a message to your bot or use [@userinfobot](https://t.me/userinfobot) to find your Telegram Chat ID.

---

## 🚀 Quick Start Instructions

1. **Activate Virtual Environment & Install Dependencies:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Verify Imports:**
   ```powershell
   python -c "import database, agents; print('Verification successful!')"
   ```

3. **Run the Streamlit Dashboard:**
   ```powershell
   streamlit run app.py
   ```
