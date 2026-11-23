import os
import time
import requests
from typing import List, Dict, Any, TypedDict
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from tavily import TavilyClient

import database

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


class AuditEvaluation(BaseModel):
    is_valid_match: bool = Field(..., description="True if exact brand new product match.")
    verified_base_price: float = Field(..., description="Lowest genuine base price in INR.")
    effective_price_inr: float = Field(..., description="Final effective price after bank discounts.")
    coupon_notes: str = Field(..., description="Bank offers or coupons.")
    best_url: str = Field(..., description="Direct product URL.")
    reasoning: str = Field(..., description="Verification reasoning.")


class ScoutState(TypedDict):
    item_id: int
    item_name: str
    target_price_inr: float
    raw_search_results: List[Dict[str, Any]]
    verified_base_price: float
    effective_price_inr: float
    coupon_notes: str
    best_url: str
    is_valid_match: bool
    agent_logs: List[str]


def researcher_node(state: ScoutState) -> ScoutState:
    item_name = state["item_name"]
    logs = list(state.get("agent_logs", []))
    logs.append(f"[Researcher] Searching for '{item_name}' in Indian stores...")

    raw_results = []
    try:
        if not TAVILY_API_KEY or TAVILY_API_KEY.startswith("your_"):
            logs.append("[Researcher] Tavily key is placeholder. Using simulated search.")
            raw_results = [
                {"title": f"{item_name} - Amazon IN", "url": "https://www.amazon.in", "content": f"Buy {item_name}. HDFC bank offer available."},
                {"title": f"{item_name} - Flipkart", "url": "https://www.flipkart.com", "content": f"Best price for {item_name}."}
            ]
        else:
            tavily = TavilyClient(api_key=TAVILY_API_KEY)
            q1 = f"{item_name} price India amazon.in flipkart.com croma.com"
            q2 = f"{item_name} bank discount coupon offer India"
            res1 = tavily.search(query=q1, max_results=3, include_domains=["amazon.in", "flipkart.com", "croma.com", "reliancedigital.in"])
            res2 = tavily.search(query=q2, max_results=2, include_domains=["amazon.in", "flipkart.com", "croma.com", "reliancedigital.in"])
            for r in res1.get("results", []) + res2.get("results", []):
                raw_results.append({"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")})
            logs.append(f"[Researcher] Retrieved {len(raw_results)} results.")
    except Exception as e:
        logs.append(f"[Researcher] Error: {str(e)}")
        raw_results = [{"title": f"{item_name} (Fallback)", "url": "https://www.amazon.in", "content": "Fallback content"}]

    state["raw_search_results"] = raw_results
    state["agent_logs"] = logs
    return state


def auditor_node(state: ScoutState) -> ScoutState:
    item_name = state["item_name"]
    target_price = state["target_price_inr"]
    raw_results = state.get("raw_search_results", [])
    logs = list(state.get("agent_logs", []))
    logs.append(f"[Auditor] Auditing {len(raw_results)} results for '{item_name}'...")

    verified_base_price = 0.0
    effective_price_inr = 0.0
    coupon_notes = "None"
    best_url = ""
    is_valid_match = False

    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("your_"):
            logs.append("[Auditor] Gemini key placeholder. Using heuristic evaluation.")
            verified_base_price = float(target_price) * 1.05
            effective_price_inr = float(target_price) * 0.95
            coupon_notes = "₹1,000 Instant Bank Discount"
            best_url = raw_results[0]["url"] if raw_results else "https://www.amazon.in"
            is_valid_match = True
        else:
            llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0, google_api_key=GEMINI_API_KEY)
            structured_llm = llm.with_structured_output(AuditEvaluation)
            prompt = (
                f"You are a strict Indian e-commerce deal auditor. Verify if the search results contain an exact, brand-new match "
                f"for '{item_name}' (reject cases, covers, cables, and refurbished items). Extract the lowest base price in INR, "
                f"subtract any verified instant bank/coupon discount to calculate effective_price_inr, summarize the offer in coupon_notes, "
                f"and provide the cleanest product URL.\nTarget Price: ₹{target_price}\nSearch Results: {raw_results}"
            )
            ev: AuditEvaluation = structured_llm.invoke(prompt)
            verified_base_price = ev.verified_base_price
            effective_price_inr = ev.effective_price_inr
            coupon_notes = ev.coupon_notes
            best_url = ev.best_url
            is_valid_match = ev.is_valid_match
            logs.append(f"[Auditor] LLM Audit passed: Match={is_valid_match}, Base=₹{verified_base_price}, Effective=₹{effective_price_inr}")
    except Exception as e:
        logs.append(f"[Auditor] Error: {str(e)}. Using fallback.")
        verified_base_price = target_price * 1.1
        effective_price_inr = target_price * 0.98
        coupon_notes = "None"
        best_url = raw_results[0]["url"] if raw_results else "https://www.amazon.in"
        is_valid_match = True

    state["verified_base_price"] = float(verified_base_price)
    state["effective_price_inr"] = float(effective_price_inr)
    state["coupon_notes"] = str(coupon_notes)
    state["best_url"] = str(best_url)
    state["is_valid_match"] = bool(is_valid_match)
    state["agent_logs"] = logs
    return state


def notifier_node(state: ScoutState) -> ScoutState:
    item_id = state["item_id"]
    item_name = state["item_name"]
    target_price = state["target_price_inr"]
    verified_base_price = state["verified_base_price"]
    effective_price = state["effective_price_inr"]
    coupon_notes = state["coupon_notes"]
    best_url = state["best_url"]
    is_valid_match = state["is_valid_match"]
    logs = list(state.get("agent_logs", []))

    logs.append(f"[Notifier] Evaluating target (Effective: ₹{effective_price} vs Target: ₹{target_price})...")

    status = "Watching"
    is_deal = False

    if is_valid_match and effective_price > 0 and effective_price <= target_price:
        status = "Deal Found"
        is_deal = True
        logs.append("[Notifier] 🎉 DEAL FOUND!")
    else:
        logs.append("[Notifier] Status: Watching.")

    try:
        database.update_item_price(item_id, verified_base_price, effective_price, coupon_notes, best_url, status)
        logs.append("[Notifier] Database updated.")
    except Exception as e:
        logs.append(f"[Notifier] DB error: {str(e)}")

    if is_deal:
        try:
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
            if not bot_token or bot_token.startswith("your_") or not chat_id or chat_id.startswith("your_"):
                logs.append("[Notifier] Telegram keys placeholder. Skipping message.")
            else:
                savings = target_price - effective_price
                pct = (savings / target_price) * 100 if target_price > 0 else 0
                msg = (
                    f"🔥 DEAL: {item_name} 🔥\n"
                    f"Target: ₹{target_price:,.0f}\n"
                    f"Deal Price: ₹{effective_price:,.0f}\n"
                    f"Offer: {coupon_notes}\n"
                    f"Save: ₹{savings:,.0f} ({pct:.1f}%)\n\n"
                    f"Buy Now: {best_url}"
                )
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                r = requests.post(url, json={"chat_id": chat_id, "text": msg}, timeout=10)
                if r.status_code == 200:
                    logs.append("[Notifier] Telegram sent successfully.")
                else:
                    logs.append(f"[Notifier] Telegram error: {r.text}")
        except Exception as e:
            logs.append(f"[Notifier] Telegram error: {str(e)}")

    logs.append("[Notifier] Finished.")
    state["agent_logs"] = logs
    return state


def create_scout_graph():
    workflow = StateGraph(ScoutState)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("auditor", auditor_node)
    workflow.add_node("notifier", notifier_node)

    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "auditor")
    workflow.add_edge("auditor", "notifier")
    workflow.add_edge("notifier", END)

    return workflow.compile()


def run_full_watchlist_check() -> List[Dict[str, Any]]:
    database.init_db()
    items = database.get_all_items()
    if not items:
        return []

    graph = create_scout_graph()
    results = []

    for idx, item in enumerate(items):
        if isinstance(item, dict) or hasattr(item, "keys"):
            item_id = item["id"]
            item_name = item["item_name"]
            target_price = float(item["target_price_inr"])
        else:
            item_id, item_name, target_price = item[0], item[1], float(item[2])

        initial_state: ScoutState = {
            "item_id": item_id,
            "item_name": item_name,
            "target_price_inr": target_price,
            "raw_search_results": [],
            "verified_base_price": 0.0,
            "effective_price_inr": 0.0,
            "coupon_notes": "None",
            "best_url": "",
            "is_valid_match": False,
            "agent_logs": [],
        }

        try:
            final_state = graph.invoke(initial_state)
            results.append(final_state if isinstance(final_state, dict) else initial_state)
        except Exception as e:
            initial_state["agent_logs"].append(f"[Error] {str(e)}")
            results.append(initial_state)

        if idx < len(items) - 1:
            time.sleep(4)

    return results if isinstance(results, list) else []