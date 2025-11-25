from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import os
from difflib import get_close_matches
from functools import lru_cache
from tenacity import retry, wait_random_exponential, stop_after_attempt
import inflect
import json
p = inflect.engine()

# ------------------
# Configuration
# ------------------
openai.api_key = os.getenv("OPENAI_API_KEY")

# Manual plural map (keeps behaviour from original app)
plural_map = {
    "lily": "lilies",
    "peony": "peonies",
    "daisy": "daisies",
    "cactus": "cacti"
}

# ------------------
# Database of flowers (source-of-truth for RAG)
# ------------------
SAFE_FLOWERS = {
    "Astilbe": "✅ Astilbe is totally safe for both cats and dogs to enjoy around the home.",
    "Erica": "✅ Erica is pet-friendly and safe for both cats and dogs.",
    "Freesia": "✅ Freesias are safe for cats and dogs – their sweet scent is safe for all.",
    "Greenbell": "✅ Greenbell is safe for both cats and dogs, so no worries if they get curious.",
    "Lisianthus": "✅ Lisianthus is safe for cats and dogs – delicate, but pet-friendly.",
    "Limonium": "✅ Limonium is perfectly safe for cats and dogs.",
    "Olive": "✅ Olive is safe for both cats and dogs, a lovely non-toxic choice.",
    "Pitto": "✅ Pitto is non-toxic and safe for both cats and dogs.",
    "Pussy willow": "✅ Pussy willow is safe for cats and dogs – a gentle, pet-friendly option.",
    "Roses": "✅ Roses are safe for cats and dogs (just watch out for thorns!).",
    "Snapdragons": "✅ Snapdragons are safe for both cats and dogs – bright and harmless.",
    "Statice": "✅ Statice is safe for cats and dogs, adding colour without worry.",
    "Stock": "✅ Stock is safe for cats and dogs – safe, sweet, and cheerful.",
    "Veronica": "✅ Veronica is pet-safe for both cats and dogs.",
    "Sunflowers": "✅ Sunflowers are safe for both cats and dogs – sunny and non-toxic.",
    "Waxflower": "✅ Waxflower is safe for cats and dogs.",
    "Trachelium": "🤔 Trachelium is safe for cats, but not recommended for dogs."
}

TOXIC_FLOWERS = {
    "Alstroemeria": "🤔 Alstroemeria is toxic to cats, but not listed as harmful for dogs.",
    "Astrantia": "⚠️ Astrantia is toxic to both cats and dogs.",
    "Asparagus Fern": "⚠️ Asparagus Fern is toxic to cats and dogs.",
    "Bupleurum": "⚠️ Bupleurum is toxic to both cats and dogs.",
    "Campanula bells": "⚠️ Campanula bells are toxic to cats and dogs.",
    "Clematis": "⚠️ Clematis is toxic to cats and dogs.",
    "Craspedia": "⚠️ Craspedia is toxic to cats and dogs.",
    "Delphinium": "⚠️ Delphinium is toxic to cats and dogs.",
    "Eucalyptus": "⚠️ Eucalyptus is toxic to cats and dogs.",
    "Erngium": "⚠️ Erngium is toxic to cats and dogs.",
    "Lavender": "⚠️ Lavender is toxic to cats and dogs.",
    "Lilies": "🤔 Lilies are extremely toxic to cats, but not listed as harmful for dogs.",
    "Ornithogalum": "⚠️ Ornithogalum is toxic to cats and dogs.",
    "Peonies": "⚠️ Peonies are toxic to cats and dogs.",
    "Ranunculus": "⚠️ Ranunculus is toxic to cats and dogs.",
    "Ruscus": "⚠️ Ruscus is toxic to cats and dogs.",
    "Senecio": "⚠️ Senecio is toxic to cats and dogs.",
    "September": "⚠️ September flowers are toxic to cats and dogs.",
    "Solidago": "⚠️ Solidago is toxic to cats and dogs.",
    "Solomio": "⚠️ Solomio is toxic to cats and dogs.",
    "Sweet William": "⚠️ Sweet William is toxic to cats and dogs.",
    "Tulip": "⚠️ Tulips are toxic to cats and dogs."
}

# Lowercase combined mapping used for fast lookup / fuzzy matching
FLOWERS = {**{k.lower(): v for k, v in SAFE_FLOWERS.items()}, **{k.lower(): v for k, v in TOXIC_FLOWERS.items()}}

# ------------------
# OpenAI helper with retry
# ------------------
@retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(3))
def ask_openai(messages):
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()

# ------------------
# RAG-aware safety check
# ------------------
@lru_cache(maxsize=200)
def rag_flower_safety(flower):
    """
    RAG workflow:
      1) Always check local database first (FLOWERS).
      2) If found -> return verified=True and the database entry.
      3) If not found -> ask the LLM but provide the LLM with a small extract of the local DB
         so it can reference what *is* known. The LLM should answer using foundation knowledge
         and must prepend a clear disclaimer that the answer is NOT verified by the database.
    """
    flower_key = flower.strip().lower()

    # 1) Exact / fuzzy match against the database
    if flower_key in FLOWERS:
        return {
            "source": "database",
            "verified": True,
            "flower": flower,
            "message": FLOWERS[flower_key]
        }

    # fuzzy match (helpful for typos)
    match = get_close_matches(flower_key, list(FLOWERS.keys()), n=1, cutoff=0.75)
    if match:
        return {
            "source": "database",
            "verified": True,
            "flower": match[0],
            "message": FLOWERS[match[0]]
        }

    # 2) Not found in DB -> ask LLM with database context (RAG)
    # Build a short context: include up to N known examples (keeps prompt size reasonable)
    # We include only name + one-line status for each example.
    examples = []
    for i, (name, desc) in enumerate(list({**SAFE_FLOWERS, **TOXIC_FLOWERS}.items())):
        if i >= 12:
            break
        examples.append(f"- {name}: {desc}")

    db_context = "\n".join(examples)

    system_msg = (
        "You are a flower safety assistant. The user asks about pet-safety (cats and dogs). "
        "First, check the small database context provided below. If the flower appears in that list, "
        "reply with that database entry and mark the answer as VERIFIED. If the flower is NOT in the "
        "database, give your best answer using general botanical / veterinary knowledge, but START "
        "the reply with: '(UNVERIFIED - not found in DB)'. When unverified, explicitly recommend consulting "
        "a veterinarian or the ASPCA animal poison control. Keep the answer short (1-3 sentences)."
    )

    user_msg = (
        f"Database context (examples):\n{db_context}\n\n" 
        f"User question: Is '{flower}' safe for cats and dogs? Answer briefly."
    )

    try:
        ai_reply = ask_openai([
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ])

        # If the model itself indicates it's unverified we mark verified=False
        verified = True
        if ai_reply.strip().lower().startswith("(unverified"):
            verified = False

        return {
            "source": "llm",
            "verified": verified,
            "flower": flower,
            "message": ai_reply
        }

    except Exception as e:
        return {
            "source": "error",
            "verified": False,
            "flower": flower,
            "message": f"⚠️ Error checking flower safety: {str(e)}"
        }

# ------------------
# Flask app
# ------------------
app = Flask(__name__)
CORS(app)

@app.route("/flower-check", methods=["POST"])
def flower_check():
    data = request.get_json(force=True)
    flower = (data.get("flower") or "").strip()

    # Basic validation
    if not flower or len(flower.split()) > 4 or not any(c.isalpha() for c in flower):
        return jsonify({"error": "Please provide a valid flower name (1-4 words)."}), 400

    # Normalize plurals
    key = flower.lower()
    if key in plural_map:
        key = plural_map[key]
    else:
        singular = p.singular_noun(key)
        if singular:
            key = singular

    # Always use RAG: check DB first, else ask LLM with DB context
    result = rag_flower_safety(key)

    # Structured response so frontend can show "verified" badges or warnings
    response = {
        "flower": result.get("flower"),
        "message": result.get("message"),
        "verified": result.get("verified", False),
        "source": result.get("source")
    }

    # Provide a user-friendly short note when the model's answer is unverified
    if response["source"] == "llm" and not response["verified"]:
        response["note"] = (
            "This answer was generated by the AI and was NOT found in our flower database. "
            "Please consult your veterinarian or the ASPCA animal poison control for authoritative guidance."
        )

    return jsonify(response)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "🌸 Flower Safety API (RAG-enabled) is running.",
        "usage": "POST /flower-check with JSON {'flower': 'Roses'}; response includes 'verified' and 'source' fields."
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5001)), debug=False)
