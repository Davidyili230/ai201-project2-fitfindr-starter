# FitFindr

FitFindr is a planning agent that helps users find secondhand clothing and style it. Given a natural language query, it searches a mock listings dataset, generates outfit suggestions using the user's wardrobe, and produces a shareable social media caption — all in a single multi-step interaction orchestrated by a planning loop.

## What the Agent Does

A complete interaction looks like this:

1. **User submits a query** — e.g., "vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers."
2. **Planning loop parses the query** — an LLM call extracts `description`, `size`, and `max_price` as structured fields.
3. **`search_listings` runs** — filters 40 mock listings by price and size, scores by keyword overlap, returns up to 3 matches sorted by relevance.
4. **`suggest_outfit` runs** — given the top match and the user's wardrobe, the LLM suggests 1–2 complete outfit combinations naming specific wardrobe pieces.
5. **`create_fit_card` runs** — the LLM generates a 2–4 sentence Instagram/TikTok-style OOTD caption referencing the item name, price, and platform.
6. **Results display** in three panels: found item, outfit advice, and fit card caption.

## How the Planning Loop Works

The loop in `run_agent()` (`agent.py`) follows a **linear 7-step sequence with one early-exit branch**:

```
Step 1  → Initialize session dict
Step 2  → LLM parses query → session["parsed"]
Step 3  → search_listings() → session["search_results"]
           └─ if empty: set session["error"], return early (steps 4–6 skipped)
Step 4  → session["selected_item"] = search_results[0]
Step 5  → suggest_outfit(selected_item, wardrobe) → session["outfit_suggestion"]
Step 6  → create_fit_card(outfit_suggestion, selected_item) → session["fit_card"]
Step 7  → return session
```

The key decision point is after `search_listings`: if no listings match the query, the loop sets `session["error"]` and returns immediately — `suggest_outfit` and `create_fit_card` are never called with empty input.

State passes between tools through the single `session` dict — no global variables, no re-prompting the user between steps. The output of each tool is stored in `session` and read as arguments to the next tool.

## Error Handling Strategy

Each tool handles its own failure mode and never raises an unhandled exception:

| Tool | Failure mode | Behavior |
|------|-------------|----------|
| `search_listings` | No listings match filters | Returns `[]`; planning loop sets `session["error"]` and exits early with a helpful message telling the user to try broader keywords, skip the size filter, or raise their budget. |
| `suggest_outfit` | User has an empty wardrobe | Still calls the LLM with a prompt asking for general pairing advice (bottom types, shoe styles, vibe). Returns a non-empty suggestion string — the loop proceeds normally. If the LLM API call fails, returns a fallback string rather than crashing. |
| `create_fit_card` | `outfit` argument is empty or whitespace | Returns the error string `"Could not generate a fit card: no outfit suggestion was provided."` without calling the LLM. The session is still returned; `session["error"]` stays `None`. |

The guiding principle: **fail informatively, never silently**. Every failure path produces a specific, user-readable string that either explains what went wrong or what to try next.

## Project Structure

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── tests/
│   └── test_tools.py          # Pytest tests for all 3 tools + failure modes
├── tools.py                   # search_listings, suggest_outfit, create_fit_card
├── agent.py                   # run_agent() — the planning loop
├── app.py                     # Gradio UI — handle_query() calls run_agent()
├── planning.md                # Full design spec, agent diagram, AI tool plan
└── requirements.txt           # Python dependencies
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Mac/Linux
pip install -r requirements.txt
```

Create a `.env` file in the repo root (never commit this):
```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com) — no credit card required.

## Running the App

```bash
python app.py
```

Opens a Gradio UI at `http://localhost:7860`.

To test the planning loop directly:
```bash
python agent.py
```

To run the test suite:
```bash
pytest tests/
```
