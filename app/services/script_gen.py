from typing import Optional
import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You write short-form video scripts (Reels/Shorts) for a single creator.
Default voice: observational, dry, fragment-based, no exclamation marks, no instructional
tone — sounds like a thought caught mid-way, not a tutorial. Adjust only if the user
explicitly asks for a different tone for this script.

Always respond with ONLY valid JSON, no markdown fences, no preamble, in this exact shape:
{"hook": "...", "body": "...", "cta": "...", "caption": "..."}

- hook: 1 line, the first 3 seconds, has to stop a scroll
- body: 3-6 short lines/beats, each a separate sentence or fragment (use \\n between beats)
- cta: 1 short line, soft, not salesy
- caption: the actual post caption to paste under the video on Instagram/TikTok — same
  voice as the script, 1-3 short lines, no hashtags unless asked, reads like a caught
  thought rather than a summary of the video
"""

REVISE_SYSTEM_PROMPT = """You are revising an existing short-form video script for a
single creator, in collaboration with them. Keep the same observational, dry,
fragment-based voice unless they explicitly ask to change it. You'll be given the
current script as JSON and an instruction for how to change it. Apply only the
requested change — don't rewrite parts they didn't ask about unless the change
requires it.

Always respond with ONLY valid JSON, no markdown fences, no preamble, in this exact shape:
{"hook": "...", "body": "...", "cta": "...", "caption": "..."}
"""


def _parse_response(raw: str) -> dict:
    raw = raw.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"hook": raw, "body": "", "cta": "", "caption": ""}


def generate_script(topic: str, tone_override: Optional[str] = None) -> dict:
    user_prompt = f"Topic: {topic}"
    if tone_override:
        user_prompt += f"\nTone for this one: {tone_override}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return _parse_response(response.content[0].text)


DISCOVER_SYSTEM_PROMPT = """You generate short-form video content topic ideas for a single
creator whose voice is observational, dry, fragment-based — no exclamation marks, no
instructional tone. They post about their own work building software products and AI
tools, and about general startup/builder life.

You'll be given a list of topics they've posted about before, and you have web search
available for current trending topics, audio, or formats in the content-creation / tech /
startup space.

Generate exactly 8 topic cards as a JSON array, no markdown fences, no preamble:
[{"category": "...", "topic": "...", "source": "history" | "trend"}, ...]

- Mix roughly half "history": fresh angles/variations on things they've already posted
  about (don't just repeat the old topic verbatim — find a new angle on the same thread)
- And half "trend": ideas tied to something genuinely current (a trending audio, format,
  news item, or discussion happening right now) that would still fit their voice and niche
- category: a short 1-3 word label like "build log", "founder life", "AI tools", "hot take"
- topic: one sentence, phrasable as something they'd actually type into a topic box
- Keep topics specific, not generic platitudes
"""


CATEGORY_MEANINGS = {
    "build log": "the literal process of building the product right now — a feature shipped, a bug fixed, a technical decision, what changed this week",
    "founder life": "the personal, unglamorous experience of running things — stress, doubt, a hard call you had to make, what nobody tells you about doing this, NOT a product feature",
    "hot takes": "a contrarian or sharp opinion about the industry, AI, startups, or content creation itself — something people might push back on",
    "lessons learned": "a specific mistake or realization and what it taught you — retrospective, not a feature announcement",
    "behind the scenes": "what a normal working day or process actually looks like — the unglamorous mechanics, not the polished result",
    "product update": "an actual feature, change, or release in something you're building — the product itself, what it does or now does differently",
    "industry rant": "frustration or critique aimed at a trend, tool, or norm in tech/startups/AI/content creation — pointed, not neutral",
    "personal life": "life outside of work — habits, routines, non-work observations, NOT about the product or the business",
}


def generate_discover_cards(past_topics: list[str], category: str = None, include_history: bool = True) -> list[dict]:
    history_text = "\n".join(f"- {t}" for t in past_topics[:30]) if past_topics else "(no history yet)"

    if not include_history:
        scope_instruction = (
            "CRITICAL: You have NOT been given any of their past topics in this request, and you must "
            "not assume, infer, or invent any. Do not reference any specific product, company, or project "
            "name. Every single card must be \"trend\" sourced — pulled from genuinely current public "
            "discussion. When you search, run queries that explicitly target LinkedIn posts, X/Twitter "
            "discussions, and Google's current trending topics in this space (e.g. \"site:linkedin.com\", "
            "\"site:x.com\", or just the topic plus \"trending\" / \"this week\") — not just generic articles."
        )
    elif category:
        scope_instruction = (
            "Mix roughly half \"history\" (fresh angles on their past topics) and half \"trend\" "
            "(genuinely current ideas)."
        )
    else:
        scope_instruction = "Mix roughly half \"history\" and half \"trend\" cards."

    if category:
        meaning = CATEGORY_MEANINGS.get(category.lower(), "")
        meaning_line = f"\nWhat \"{category}\" specifically means here: {meaning}\n" if meaning else ""
        user_prompt = (
            f"Topics they've posted about before:\n{history_text}\n\n"
            f"Generate the 8 cards now, but ALL 8 must fit the category \"{category}\" specifically — "
            f"not just loosely related, actually centered on what that category means.{meaning_line}"
            f"Set \"category\" to \"{category}\" on every card. {scope_instruction} "
            f"For any \"trend\" cards, actually use web search to find what's currently being discussed "
            f"on Twitter/X, LinkedIn, or in tech/startup news right now — name a real current thread, "
            f"post type, or discussion if you find one, rather than a generic trend description."
        )
    else:
        user_prompt = (
            f"Topics they've posted about before:\n{history_text}\n\n{scope_instruction}\n\n"
            f"For any \"trend\" cards, actually use web search to find what's currently being discussed "
            f"on Twitter/X, LinkedIn, or in tech/startup news right now — name a real current thread, "
            f"post type, or discussion if you find one, rather than a generic trend description.\n\n"
            f"Generate the 8 cards now."
        )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        system=DISCOVER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}],
    )

    # find the final text block (after any tool-use turns) and parse it as JSON
    text_parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    raw = "\n".join(text_parts).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        cards = json.loads(raw)
        if isinstance(cards, list):
            return cards
    except json.JSONDecodeError:
        pass
    return []


def revise_script(current: dict, instruction: str) -> dict:
    current_json = json.dumps({
        "hook": current.get("hook", ""),
        "body": current.get("body", ""),
        "cta": current.get("cta", ""),
        "caption": current.get("caption", ""),
    })
    user_prompt = f"Current script:\n{current_json}\n\nInstruction: {instruction}"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=REVISE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return _parse_response(response.content[0].text)
