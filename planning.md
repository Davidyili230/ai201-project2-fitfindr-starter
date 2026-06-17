# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Loads all 40 listings from `listings.json` via `load_listings()`, filters them by `max_price` and `size` (if provided), scores each remaining listing by counting keyword overlaps between `description` and the listing's `title`, `description`, and `style_tags` fields combined, then returns up to the top 3 results sorted by score (highest first), dropping any listings with a score of 0.

**Input parameters:**
- `description` (str): Keywords describing what the user is looking for (e.g., `"vintage graphic tee"`). Matched against listing `title`, `description`, and `style_tags` fields.
- `size` (str | None): Size string to filter by (e.g., `"M"`, `"S/M"`). Matching is case-insensitive substring — `"M"` matches a listing with size `"S/M"`. Pass `None` to skip size filtering.
- `max_price` (float | None): Maximum price in dollars, inclusive (e.g., `30.0`). Listings with `price > max_price` are excluded. Pass `None` to skip price filtering.

**What it returns:**
A list of up to 3 listing dicts sorted by relevance score (highest first). Returns an empty list `[]` if nothing matches — does NOT raise an exception. Each dict in the list has these fields:
- `id` (str): unique listing ID, e.g., `"lst_002"`
- `title` (str): listing title, e.g., `"Y2K Baby Tee — Butterfly Print"`
- `description` (str): full text description of the item
- `category` (str): one of `"tops"`, `"bottoms"`, `"outerwear"`, `"shoes"`, `"accessories"`
- `style_tags` (list[str]): style keywords, e.g., `["y2k", "vintage", "graphic tee"]`
- `size` (str): size label, e.g., `"S/M"`, `"W30 L30"`
- `condition` (str): one of `"excellent"`, `"good"`, `"fair"`
- `price` (float): listed price in dollars, e.g., `18.0`
- `colors` (list[str]): color names, e.g., `["white", "pink", "purple"]`
- `brand` (str | None): brand name or `null` if unbranded
- `platform` (str): one of `"depop"`, `"thredUp"`, `"poshmark"`

**What happens if it fails or returns nothing:**
If the returned list is empty, the planning loop sets `session["error"]` to `"Sorry, I couldn't find any listings matching your search. Try using broader keywords, skipping the size filter, or raising your budget."` and returns the session immediately. `suggest_outfit` and `create_fit_card` are never called.

---

### Tool 2: suggest_outfit

**What it does:**
Takes the selected listing item and the user's wardrobe dict, then calls the Groq LLM to suggest 1–2 complete outfits. If the wardrobe is empty, the LLM is prompted to give general styling advice (what clothing types and vibes pair well with the item). If the wardrobe has items, the LLM is prompted to name specific wardrobe pieces by their `name` field in each outfit combo.

**Input parameters:**
- `new_item` (dict): A listing dict (same structure as returned by `search_listings`). Key fields used in the prompt: `title`, `category`, `style_tags`, `colors`, `condition`, `price`, `platform`.
- `wardrobe` (dict): A wardrobe dict with a single key `"items"` containing a list of wardrobe item dicts. The list may be empty. Each wardrobe item dict has: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str | None).

**What it returns:**
A non-empty string (1–3 paragraphs) with outfit suggestions. If wardrobe `items` is empty, the string contains general styling advice (e.g., what bottom types and shoe styles pair well with the new item's vibe). If wardrobe is not empty, the string names at least one specific wardrobe piece by its `name` field in each outfit. Never returns an empty string or `None`.

**What happens if it fails or returns nothing:**
- If `wardrobe["items"]` is empty, the tool still calls the LLM with a no-wardrobe prompt rather than skipping or erroring.
- If the LLM API call raises an exception, the tool catches it and returns the fallback string: `"Unable to generate outfit suggestions right now. The [item title] would pair well with neutral basics like straight-leg jeans and clean sneakers."`

---

### Tool 3: create_fit_card

**What it does:**
Generates a 2–4 sentence Instagram/TikTok-style OOTD caption by calling the Groq LLM at a higher temperature (0.9) for variety. The caption feels casual and authentic — it mentions the item name, price, and platform once each in a natural way, captures the outfit vibe in specific terms, and sounds different each time it is called with different inputs.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit()`. Used as context for the caption's styling angle.
- `new_item` (dict): The listing dict for the thrifted item. Key fields used in the prompt: `title`, `price`, `platform`, `style_tags`, `colors`.

**What it returns:**
A 2–4 sentence string usable as a social media caption. If `outfit` is empty or whitespace-only, returns the error string `"Could not generate a fit card: no outfit suggestion was provided."` without calling the LLM. If the LLM call fails, returns `"Could not generate fit card due to a service error."`.

**What happens if it fails or returns nothing:**
- If `outfit` is empty or all whitespace: return the error string immediately, no LLM call.
- If LLM raises an exception: catch it and return the service-error fallback string.
- In both error cases, the planning loop still returns the session — the session's `fit_card` field will hold the error string rather than `None`, and `error` stays `None` (the interaction is not considered a full failure).

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` follows a fixed linear sequence with one early-exit branch. There is no retry or backtracking.

**Step 1 — Initialize session**
Call `_new_session(query, wardrobe)` to create the session dict with all fields set to their starting values (`search_results = []`, `selected_item = None`, `error = None`, etc.).

**Step 2 — Parse the query**
Call the Groq LLM with a structured prompt that instructs it to extract three pieces of information from the user's natural language query:
- `description` (str): clothing keywords only (e.g., `"vintage graphic tee"`)
- `size` (str | None): size mentioned, or `null` if absent
- `max_price` (float | None): price ceiling in dollars, or `null` if absent

Ask the LLM to respond in JSON format. Parse the JSON and store as `session["parsed"] = {"description": ..., "size": ..., "max_price": ...}`.

**Step 3 — Call search_listings and check results**
Call `search_listings(session["parsed"]["description"], session["parsed"]["size"], session["parsed"]["max_price"])`.
Store the returned list in `session["search_results"]`.

**Branch — empty results:**
If `len(session["search_results"]) == 0`:
- Set `session["error"] = "Sorry, I couldn't find any listings matching your search. Try using broader keywords, skipping the size filter, or raising your budget."`
- `return session` immediately. Steps 4–6 are skipped entirely.

**Step 4 — Select the top item**
Set `session["selected_item"] = session["search_results"][0]` (the highest-scored listing returned by `search_listings`).

**Step 5 — Call suggest_outfit**
Call `suggest_outfit(session["selected_item"], session["wardrobe"])`.
Store the returned string in `session["outfit_suggestion"]`.
(This call always produces a string — no branch needed here.)

**Step 6 — Call create_fit_card**
Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`.
Store the returned string in `session["fit_card"]`.
(An empty `outfit_suggestion` is handled inside the tool itself — it returns an error string rather than crashing.)

**Step 7 — Return session**
Return the completed session dict. The caller checks `session["error"]` first; if `None`, it reads `session["selected_item"]`, `session["outfit_suggestion"]`, and `session["fit_card"]`.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single `session` dict (created by `_new_session()`) that is passed by reference through the planning loop. No global variables are used.

| Field | Type | Set by | Read by |
|-------|------|--------|---------|
| `session["query"]` | str | `_new_session()` | query-parse LLM prompt |
| `session["parsed"]` | dict with keys `description`, `size`, `max_price` | Step 2 (LLM parse) | Step 3 (`search_listings` args) |
| `session["search_results"]` | list[dict] | Step 3 (`search_listings` return) | Step 4 (pick top item) |
| `session["selected_item"]` | dict or None | Step 4 | Step 5 (`suggest_outfit` arg), Step 6 (`create_fit_card` arg) |
| `session["wardrobe"]` | dict | `_new_session()` (from caller) | Step 5 (`suggest_outfit` arg) |
| `session["outfit_suggestion"]` | str or None | Step 5 (`suggest_outfit` return) | Step 6 (`create_fit_card` arg) |
| `session["fit_card"]` | str or None | Step 6 (`create_fit_card` return) | Returned to UI |
| `session["error"]` | str or None | Step 3 (on empty results) | UI display / early-return gate |

Tools do not share state directly — they are pure functions. The planning loop writes each tool's output into the session dict and reads the previous tool's output back out as arguments to the next tool.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the description, size, and/or price filter (returns `[]`) | Sets `session["error"]` to `"Sorry, I couldn't find any listings matching your search. Try using broader keywords, skipping the size filter, or raising your budget."` and returns session immediately. `suggest_outfit` and `create_fit_card` are never called. |
| `suggest_outfit` | `wardrobe["items"]` is empty (new user with no wardrobe entered) | Tool still calls the LLM with a prompt asking for general styling advice for the item on its own (what bottom types, shoe styles, and vibes pair well). Returns a non-empty suggestion string — the planning loop proceeds normally. |
| `create_fit_card` | `outfit` argument is empty or whitespace (e.g., `suggest_outfit` returned `""`) | Tool returns the string `"Could not generate a fit card: no outfit suggestion was provided."` without calling the LLM. The planning loop stores this in `session["fit_card"]` and returns the session; `session["error"]` stays `None`. |

---

## Architecture

```
User query (natural language string)
         │
         ▼
┌────────────────────────────────────────────────────────────────┐
│                   Planning Loop  (run_agent)                   │
│                                                                │
│  ① _new_session(query, wardrobe)                              │
│       → session = {query, parsed:{}, search_results:[],        │
│                    selected_item:None, wardrobe,               │
│                    outfit_suggestion:None, fit_card:None,      │
│                    error:None}                                 │
│                         │                                      │
│  ② LLM parse query      │                                      │
│       → session["parsed"] = {description, size, max_price}    │
│                         │                                      │
│                         ▼                                      │
│  ③ search_listings(description, size, max_price)              │
│          │                                                     │
│     results == []                                             │
│          ├──► session["error"] = "No listings found…"         │
│          │              │                                      │
│          │              └──────────────────► RETURN session ◄─┐
│          │                                  (early exit)      │
│     results = [item₁, item₂, …]                              │
│          │                                                     │
│     session["search_results"] = results                       │
│     session["selected_item"]  = results[0]                    │
│          │                                                     │
│          ▼                                                     │
│  ④ suggest_outfit(selected_item, wardrobe)                    │
│          │                                                     │
│     wardrobe["items"] == []                                   │
│          ├──► LLM prompt: general styling advice              │
│     wardrobe["items"] != []                                   │
│          ├──► LLM prompt: specific combos naming              │
│          │    wardrobe pieces by name                         │
│     session["outfit_suggestion"] = returned string            │
│          │                                                     │
│          ▼                                                     │
│  ⑤ create_fit_card(outfit_suggestion, selected_item)         │
│          │                                                     │
│     outfit == "" / whitespace                                 │
│          ├──► return error string (no LLM call)               │
│     outfit != ""                                              │
│          ├──► LLM prompt: OOTD caption at temperature 0.9     │
│     session["fit_card"] = caption string                      │
│          │                                                     │
│          ▼                                                     │
│     RETURN session  ◄───────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
         │
         ▼
  Gradio UI reads:
    session["selected_item"]     → item title, price, platform
    session["outfit_suggestion"] → displayed as outfit advice
    session["fit_card"]          → displayed as shareable caption
    session["error"]             → displayed if not None (replaces other fields)
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

**Tool 1 — `search_listings`:**
I'll give Claude the Tool 1 section of this planning.md (inputs with types and meanings, exact return-dict field list, empty-results failure behavior) along with the `load_listings()` docstring from `utils/data_loader.py`. I'll ask it to implement the function — filter by `max_price` and `size` (case-insensitive substring), score by counting word overlaps between the lowercased `description` argument and the combined `title + description + " ".join(style_tags)` of each listing, drop score-0 listings, and return the top 3 sorted by score. Before using the output I'll verify: (1) call with `"vintage graphic tee", None, 30.0` and confirm the result list is non-empty and all prices ≤ 30; (2) call with `"denim jacket", "M", None` and confirm size field contains "M" (case-insensitive); (3) call with `"designer ballgown", None, 5.0` and confirm it returns `[]`.

**Tool 2 — `suggest_outfit`:**
I'll give Claude the Tool 2 section of this planning.md plus the `_get_groq_client()` helper from `tools.py`, one example listing dict (the Y2K Baby Tee), and the first two wardrobe item dicts from `wardrobe_schema.json`. I'll ask it to implement the empty-wardrobe branch (call LLM asking for general pairing advice) and the non-empty branch (format all wardrobe `name` fields into a bulleted list in the prompt, ask LLM to name specific pieces in suggestions). I'll verify by: (1) calling with `get_example_wardrobe()` and checking the returned string mentions at least one wardrobe item by name; (2) calling with `get_empty_wardrobe()` and confirming it returns a non-empty string and does not crash; (3) reading the output to confirm it is coherent and relevant to the item.

**Tool 3 — `create_fit_card`:**
I'll give Claude the Tool 3 section of this planning.md (style guidelines, temperature note, two error-case behaviors) and the actual output of `suggest_outfit` from a test run. I'll ask it to implement: guard against empty/whitespace `outfit`, build a prompt that gives the LLM `title`, `price`, and `platform` from `new_item` plus the `outfit` string, and request a 2–4 sentence OOTD caption at temperature 0.9. I'll verify by: (1) calling it twice with the same input and confirming the outputs differ; (2) calling with `outfit=""` and confirming it returns the specific error string without crashing; (3) reading the caption to confirm it mentions item name, price, and platform exactly once each.

**Milestone 4 — Planning loop and state management:**
I'll give Claude the Planning Loop section of this planning.md (all 7 steps with exact branch conditions), the Architecture diagram above, the `_new_session()` function body from `agent.py`, and the signatures of all three tools. I'll ask it to implement `run_agent()` following the 7-step flow exactly — LLM-based query parsing returning JSON, early return on empty search results, sequential tool calls writing into the session dict. I'll verify by running `python agent.py` and checking: (1) the happy path prints a non-empty `outfit_suggestion` and `fit_card` with `error = None`; (2) the no-results path (`"designer ballgown size XXS under $5"`) prints a non-None `error` and `fit_card = None`; (3) the session dict keys match `_new_session()`'s structure exactly.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Parse the query (LLM call):**
The planning loop calls the Groq LLM with the raw query and asks it to extract structured fields. The LLM returns JSON:
```json
{"description": "vintage graphic tee", "size": null, "max_price": 30.0}
```
`session["parsed"]` is set to `{"description": "vintage graphic tee", "size": None, "max_price": 30.0}`.

**Step 2 — Call `search_listings("vintage graphic tee", None, 30.0)`:**
The tool loads all 40 listings, drops any with `price > 30.0`, then scores each remaining listing. The word tokens from `"vintage graphic tee"` are matched against each listing's `title + description + style_tags`. The Y2K Baby Tee (lst_002, $18, style_tags: `["y2k", "vintage", "graphic tee"]`) scores 3 hits; a Vintage Band Tee (lst_008, $22, style_tags: `["vintage", "graphic tee", "band tee"]`) scores 3 hits; a Vintage Oversized Crewneck (lst_015, $27, style_tags: `["vintage", "streetwear"]`) scores 2 hits.
`search_listings` returns these three dicts sorted by score. `session["search_results"]` is set to the list (length 3, not empty — no early exit). `session["selected_item"]` is set to `lst_002` (Y2K Baby Tee).

**Step 3 — Call `suggest_outfit(selected_item, wardrobe)`:**
`wardrobe["items"]` has 10 items (the example wardrobe), so the non-empty branch runs. The LLM prompt includes the item's title, category (`tops`), style_tags, colors, and a bulleted list of all 10 wardrobe item names. The LLM returns:
> "The Y2K Baby Tee pairs perfectly with your Baggy straight-leg jeans, dark wash (w_001) for a nostalgic streetwear look — add your Chunky white platform sneakers (w_005) to nail the 2000s silhouette. For a second combo, try it tucked into your Wide-leg khaki trousers (w_002) with a boxy jacket on top for a more editorial vibe."
`session["outfit_suggestion"]` is set to this string.

**Step 4 — Call `create_fit_card(outfit_suggestion, selected_item)`:**
`outfit_suggestion` is not empty, so the LLM is called at temperature 0.9. The prompt includes item title ("Y2K Baby Tee"), price ($18.00), platform (depop), and the outfit suggestion string. The LLM returns:
> "found this Y2K baby tee on depop for $18 and it immediately became the center of every outfit this week. paired it with my baggy dark wash jeans and chunky platform sneakers and honestly it's giving everything. thrift season is not over, go check depop."
`session["fit_card"]` is set to this caption. `session["error"]` remains `None`.

**Final output to user:**
The Gradio UI displays:
- **Found:** Y2K Baby Tee — Butterfly Print · $18.00 · depop · Condition: excellent
- **How to style it:** "The Y2K Baby Tee pairs perfectly with your Baggy straight-leg jeans, dark wash…" (full outfit suggestion)
- **Your fit card:** "found this Y2K baby tee on depop for $18 and it immediately became the center of every outfit this week…" (shareable caption)
