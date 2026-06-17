# FitFindr

FitFindr is a planning agent that helps users find secondhand clothing and style it. Given a natural language query, it searches a mock listings dataset, generates outfit suggestions using the user's wardrobe, and produces a shareable social media caption — all in a single multi-step interaction orchestrated by a planning loop.

---

## Tool Inventory

### `search_listings`

**Purpose:** Find mock secondhand listings that match the user's keywords, size, and budget.

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Clothing keywords (e.g. `"vintage graphic tee"`). Matched against each listing's `title`, `description`, and `style_tags` fields. |
| `size` | `str \| None` | Size to filter by (e.g. `"M"`, `"S/M"`). Case-insensitive substring match. `None` skips size filtering. |
| `max_price` | `float \| None` | Price ceiling in dollars, inclusive. `None` skips price filtering. |

**Returns:** A `list[dict]` of up to 3 matching listings sorted by relevance score (highest first). Returns `[]` if nothing matches — never raises.

Each listing dict has: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str|None), `platform` (str).

---

### `suggest_outfit`

**Purpose:** Use an LLM to suggest 1–2 complete outfit ideas pairing the thrifted item with the user's wardrobe.

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A listing dict (output of `search_listings`). Key fields used: `title`, `category`, `colors`, `style_tags`. |
| `wardrobe` | `dict` | Wardrobe dict with an `"items"` key containing a list of wardrobe item dicts. May be empty. Each wardrobe item has `name`, `category`, `colors`. |

**Returns:** A non-empty `str` with outfit suggestions. If the wardrobe is empty, returns general styling advice (what clothing types and vibes pair well). If the wardrobe has items, the response names specific wardrobe pieces by their `name` field. Never returns an empty string or `None`.

---

### `create_fit_card`

**Purpose:** Generate a short, shareable Instagram/TikTok OOTD caption for the thrifted find.

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit()`. |
| `new_item` | `dict` | The listing dict for the thrifted item. Key fields used: `title`, `price`, `platform`, `style_tags`. |

**Returns:** A 2–4 sentence `str` usable as a social media caption. Mentions item name, price, and platform once each in a casual, authentic voice. If `outfit` is empty or whitespace, returns `"Could not generate a fit card: no outfit suggestion was provided."` without calling the LLM. If the LLM call fails, returns `"Could not generate fit card due to a service error."`.

---

## How the Planning Loop Works

The loop in `run_agent()` ([agent.py](agent.py)) follows a **linear 7-step sequence with one early-exit branch**.

```
Step 1  → Initialize session dict with _new_session()
Step 2  → LLM parses raw query → session["parsed"] = {description, size, max_price}
Step 3  → search_listings(description, size, max_price) → session["search_results"]
           └─ if results == []: set session["error"], return early (steps 4–6 skipped)
Step 4  → session["selected_item"] = search_results[0]
Step 5  → suggest_outfit(selected_item, wardrobe) → session["outfit_suggestion"]
Step 6  → create_fit_card(outfit_suggestion, selected_item) → session["fit_card"]
Step 7  → return session
```

**Key decisions the agent makes:**

1. **Query parsing (Step 2):** Rather than regex, the agent calls the Groq LLM (`llama-3.3-70b-versatile`, temperature 0) to extract `description`, `size`, and `max_price` as a JSON object from the raw natural language query. This handles phrasing like "something under thirty dollars" or "fits a medium" that regex would miss. If the LLM call or JSON parsing fails, the agent falls back to using the raw query as the description with no filters.

2. **Early exit (Step 3):** After `search_listings`, the agent checks whether the returned list is empty. If it is, the loop terminates immediately and sets a user-readable error message in `session["error"]`. Steps 4–6 are never reached — `suggest_outfit` is never called with no item, and `create_fit_card` is never called with no outfit.

3. **Item selection (Step 4):** The agent always picks the top result (`search_results[0]`). Because `search_listings` already sorts by relevance score, the first item is the best keyword match within the user's filters. No secondary scoring is needed.

4. **Wardrobe-aware styling (Step 5):** `suggest_outfit` inspects whether `wardrobe["items"]` is empty and switches between two LLM prompts — one that names specific wardrobe pieces, one that gives general pairing advice. The planning loop does not need to know which branch ran; it always gets a non-empty string back.

---

## State Management

All state lives in a single `session` dict created by `_new_session()` at the start of each call to `run_agent()`. No global variables are used. Tools are pure functions — they receive arguments and return values; they do not read or write the session directly.

| Field | Type | Written by | Read by |
|-------|------|-----------|---------|
| `session["query"]` | `str` | `_new_session()` | Step 2 LLM prompt |
| `session["parsed"]` | `dict` (`description`, `size`, `max_price`) | Step 2 (LLM parse) | Step 3 (`search_listings` args) |
| `session["search_results"]` | `list[dict]` | Step 3 (`search_listings` return) | Step 4 (pick top item) |
| `session["selected_item"]` | `dict \| None` | Step 4 | Step 5 and Step 6 args |
| `session["wardrobe"]` | `dict` | `_new_session()` (from caller) | Step 5 (`suggest_outfit` arg) |
| `session["outfit_suggestion"]` | `str \| None` | Step 5 (`suggest_outfit` return) | Step 6 (`create_fit_card` arg) |
| `session["fit_card"]` | `str \| None` | Step 6 (`create_fit_card` return) | Returned to Gradio UI |
| `session["error"]` | `str \| None` | Step 3 (on empty results) | UI display and early-return gate |

State passes strictly forward: each step reads from earlier fields and writes to its own output field. No tool looks at a field that comes after it in the sequence. This means you can always tell what state any step saw just by looking at the steps above it.

---

## Error Handling

Each tool handles its own failure mode and never raises an unhandled exception to the planning loop.

| Tool | Failure mode | Behavior |
|------|-------------|----------|
| `search_listings` | No listings match filters (returns `[]`) | Planning loop sets `session["error"]` and exits early. |
| `suggest_outfit` | `wardrobe["items"]` is empty | Calls LLM with a general styling prompt — still returns a useful string. |
| `suggest_outfit` | LLM API exception | Returns fallback: `"Unable to generate outfit suggestions right now. The [title] would pair well with neutral basics…"` |
| `create_fit_card` | `outfit` is empty or whitespace | Returns `"Could not generate a fit card: no outfit suggestion was provided."` without calling the LLM. |
| `create_fit_card` | LLM API exception | Returns `"Could not generate fit card due to a service error."` |

**Concrete examples from testing:**

- **`search_listings` no-results:** Querying `search_listings("designer ballgown", size="XXS", max_price=5)` returns `[]`. No listing in the 40-item dataset is priced under $5 in size XXS that matches "ballgown." The planning loop stores the error message `"Sorry, I couldn't find any listings matching your search. Try using broader keywords, skipping the size filter, or raising your budget."` in `session["error"]` and returns immediately. The Gradio UI displays this message in the top panel; the outfit and fit-card panels remain empty. This is covered by `test_search_empty_results` in [tests/test_tools.py](tests/test_tools.py).

- **`create_fit_card` empty-outfit guard:** Calling `create_fit_card("", EXAMPLE_ITEM)` or `create_fit_card("   ", EXAMPLE_ITEM)` returns the specific error string immediately — no Groq API call is made. The test `test_create_fit_card_empty_outfit_returns_error` and `test_create_fit_card_whitespace_outfit_returns_error` confirm this. In practice this path would only be hit if `suggest_outfit` returned an empty string, which it cannot in normal operation — but the guard prevents a silent crash if the LLM ever returns whitespace.

- **`suggest_outfit` API fallback:** `test_suggest_outfit_fallback_on_api_error` patches `_get_groq_client` to raise `Exception("API down")`. The returned string contains the item title and a neutral styling suggestion, confirming the tool never propagates the exception to the planning loop.

---

## Spec Reflection

**What worked as designed:**

The linear 7-step loop with a single early-exit branch proved to be the right scope. Because each step has one clear responsibility and one clear output field, debugging was straightforward — when a query returned the wrong item, the problem was always isolatable to either the parse step or the search-scoring step, never both.

The decision to use LLM-based query parsing (Step 2) rather than regex paid off. Queries like `"something vintage under thirty"` or `"size medium jacket"` parse correctly because the LLM handles natural language variation. A regex approach would have needed separate patterns for each phrasing variant.

**What was harder than expected:**

The Groq LLM sometimes wraps its JSON response in markdown code fences (` ```json ... ``` `). The parse step needed an explicit fence-stripping step before calling `json.loads()`. This is not mentioned in the planning doc and had to be added after seeing it fail on the first live test.

**What would change in a v2:**

- The agent always selects `search_results[0]`. A v2 could present all three results and let the user pick before calling `suggest_outfit`.
- The scoring in `search_listings` is word-overlap only. Synonyms ("jacket" vs "coat") score 0. An embedding-based similarity score would give much better recall.
- There is no retry on the no-results path. A v2 could automatically re-run `search_listings` with the size and price filters dropped if the first call returns nothing, only falling through to the error message if the relaxed search also fails.

---

## AI Usage

### Instance 1: Implementing `search_listings` (Tool 1)

**What I gave the AI:** The Tool 1 section of [planning.md](planning.md), specifically: the three input parameters with their types and filter semantics (case-insensitive substring for size, inclusive `<=` for price), the exact list of listing dict fields, the scoring rule (count word overlaps in `title + description + style_tags`), the sort-and-top-3 return spec, and the `load_listings()` function signature from [utils/data_loader.py](utils/data_loader.py).

**What it produced:** A complete implementation that filtered by price and size, built a `keywords` set from `.split()`, scored by iterating over that set, and returned the top 3 with a list comprehension.

**What I changed:** The AI initially scored by checking whether each keyword appeared as a substring anywhere in the combined text field. I changed it to use `kw in text` with word-boundary-approximate semantics — this was fine for the dataset but I left a note in planning.md that embedding similarity would be a real improvement.

### Instance 2: Implementing the LLM query-parse step (Step 2 of `run_agent`)

**What I gave the AI:** The Planning Loop section of planning.md (all 7 steps, branch conditions, the `_new_session()` body), and the Groq API usage pattern from Tool 2's implementation. I specifically asked it to handle the case where the LLM wraps its JSON in markdown code fences.

**What it produced:** A working parse block that called the LLM with a zero-temperature structured prompt, stripped ` ```json ``` ` fences with a string split, called `json.loads()`, and had a bare `except Exception` fallback that set `description` to the raw query with `size=None` and `max_price=None`.

**What I changed:** The generated fence-stripping logic split on ` ``` ` and took index `[1]`, then stripped a leading `"json"` prefix. This worked but was fragile if the model omitted the language tag. I added the check `if raw.startswith("json"): raw = raw[4:]` inside the fence-stripped block to make it handle both ```` ```json ```` and ```` ``` ```` variants, then verified it against two live Groq responses where the model used each style.

---

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

---

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

---

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

---

## What a Complete Interaction Looks Like

**Query:** `"vintage graphic tee under $30"`  **Wardrobe:** Example wardrobe

1. **Parse (LLM):** Extracts `{"description": "vintage graphic tee", "size": null, "max_price": 30.0}`.
2. **`search_listings("vintage graphic tee", None, 30.0)`:** Drops listings over $30, scores by keyword overlap. Returns Y2K Baby Tee ($18, depop) as the top result.
3. **`suggest_outfit(Y2K Baby Tee, example_wardrobe)`:** LLM sees the wardrobe and suggests pairing with "Baggy straight-leg jeans" and "Chunky white platform sneakers" by name.
4. **`create_fit_card(outfit, Y2K Baby Tee)`:** LLM generates a casual OOTD caption at temperature 0.9 mentioning the item, $18, and depop.
5. **UI output:** Three panels populate: the listing details, the outfit combo, and the fit card caption ready to copy.

**No-results path:** Query `"designer ballgown size XXS under $5"` — `search_listings` returns `[]`, the loop sets `session["error"]` and returns immediately. The UI shows the error message in panel 1; panels 2 and 3 are empty.
