import os
import json
from difflib import get_close_matches
from functools import lru_cache
from tenacity import retry, wait_random_exponential, stop_after_attempt
import inflect
from openai import OpenAI

p = inflect.engine()

# -----------------------------
# DATABASE
# -----------------------------
SAFE_FLOWERS = {
    "astilbe": "✅ Astilbe is safe for cats and dogs.",
    "erica": "✅ Erica is pet-friendly.",
    "freesia": "✅ Freesias are safe.",
    "greenbell": "✅ Greenbell is safe.",
    "lisianthus": "✅ Lisianthus is safe.",
    "limonium": "✅ Limonium is safe.",
    "olive": "✅ Olive is safe.",
    "pitto": "✅ Pitto is non-toxic.",
    "pussy willow": "✅ Pussy willow is safe.",
    "roses": "✅ Roses are safe (watch for thorns).",
    "snapdragons": "✅ Snapdragons are safe.",
    "statice": "✅ Statice is safe.",
    "stock": "✅ Stock is safe.",
    "veronica": "✅ Veronica is safe.",
    "sunflowers": "✅ Sunflowers are safe.",
    "waxflower": "✅ Waxflower is safe."
}

TOXIC_FLOWERS = {
    "alstroemeria": "⚠️ Toxic to cats/dogs.",
    "astrantia": "⚠️ Toxic to pets.",
    "asparagus fern": "⚠️ Toxic to pets.",
    "delphinium": "⚠️ Toxic to pets.",
    "eucalyptus": "⚠️ Toxic to pets.",
    "lavender": "⚠️ Toxic to pets in some cases.",
    "lilies": "☠️ Extremely toxic to cats.",
    "peonies": "⚠️ Toxic.",
    "ranunculus": "⚠️ Toxic.",
    "tulip": "⚠️ Toxic to pets."
}

FLOWERS = {**SAFE_FLOWERS, **TOXIC_FLOWERS}

# -----------------------------
# OPENAI CLIENT
# -----------------------------
def get_client():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=key)

@retry(wait=wait_random_exponential(min=1, max=4), stop=stop_after_attempt(3))
def ask_openai(messages):
    client = get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()

# -----------------------------
# RAG LOGIC
# -----------------------------
@lru_cache(maxsize=200)
def rag_flower_safety(flower):
    flower_key = (flower or "").strip().lower()

    if not flower_key:
        return {
            "verified": False,
            "source": "error",
            "message": "Invalid flower name"
        }

    # Direct DB match
    if flower_key in FLOWERS:
        return {
            "verified": True,
            "source": "database",
            "message": FLOWERS[flower_key]
        }

    # Fuzzy match
    match = get_close_matches(flower_key, FLOWERS.keys(), n=1, cutoff=0.75)
    if match:
        return {
            "verified": True,
            "source": "database",
            "message": FLOWERS[match[0]]
        }

    # LLM fallback
    examples = []
    for name, desc in list(FLOWERS.items())[:10]:
        examples.append(f"- {name}: {desc}")

    db_context = "\n".join(examples)

    system_msg = (
        "You are a flower safety assistant. "
        "If the flower appears in the database context, use that. "
        "If not, answer using general knowledge and begin the message with: "
        "'(UNVERIFIED - not found in DB)'"
    )

    user_msg = f"Database:\n{db_context}\n\nIs '{flower}' safe for pets?"

    try:
        reply = ask_openai([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ])

        unverified = reply.lower().startswith("(unverified")

        return {
            "verified": not unverified,
            "source": "llm",
            "message": reply
        }

    except Exception as e:
        return {
            "verified": False,
            "source": "error",
            "message": str(e)
        }

# -----------------------------
# VERCEL HANDLER  (NOT FLASK)
# -----------------------------
def handler(request):
    try:
        method = request.get("method", "GET")

        # CORS preflight
        if method == "OPTIONS":
            return {
                "statusCode": 204,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type"
                },
                "body": ""
            }

        # GET = health check
        if method == "GET":
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"status": "ok", "message": "POST to /api/flower-check"})
            }

        # POST request body (Vercel format)
        raw_body = request.get("body") or "{}"
        data = json.loads(raw_body)

        flower = data.get("flower")
        result = rag_flower_safety(flower)

        # Unverified LLM fallback gets disclaimer
        if result.get("source") == "llm" and not result.get("verified"):
            result["note"] = "AI-generated (unverified). Consult a vet."

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(result)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
