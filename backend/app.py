from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
from difflib import get_close_matches
from functools import lru_cache
from tenacity import retry, wait_random_exponential, stop_after_attempt
import inflect
import json

p = inflect.engine()

# ---------------------------------------------------
# OpenAI Client (Correct, New API)
# ---------------------------------------------------
def get_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------
# Flower safety data
# ---------------------------------------------------

SAFE_FLOWERS = {
    "astilbe": "✅ Astilbe is totally safe for both cats and dogs.",
    "erica": "✅ Erica is pet friendly.",
    "freesia": "✅ Freesias are safe for pets.",
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
    "waxflower": "✅ Waxflower is safe.",
}

TOXIC_FLOWERS = {
    "alstroemeria": "⚠️ Toxic to cats.",
    "astrantia": "⚠️ Toxic to cats and dogs.",
    "asparagus fern": "⚠️ Toxic to pets.",
    "bupleurum": "⚠️ Toxic to pets.",
    "campanula bells": "⚠️ Toxic.",
    "clematis": "⚠️ Toxic.",
    "craspedia": "⚠️ Toxic.",
    "delphinium": "⚠️ Toxic.",
    "eucalyptus": "⚠️ Toxic.",
    "lavender": "⚠️ Toxic.",
    "lilies": "☠️ EXTREMELY toxic to cats.",
    "peonies": "⚠️ Toxic.",
    "ranunculus": "⚠️ Toxic.",
    "ruscus": "⚠️ Toxic.",
    "senecio": "⚠️ Toxic.",
    "solidago": "⚠️ Toxic.",
    "sweet william": "⚠️ Toxic.",
    "tulip": "⚠️ Toxic.",
}

FLOWERS = {**SAFE_FLOWERS, **TOXIC_FLOWERS}

# ---------------------------------------------------
# Fixed OpenAI call (Correct way)
# ---------------------------------------------------
@retry(wait=wait_random_exponential(min=1, max=4), stop=stop_after_attempt(3))
def ask_openai(messages):
    try:
        client = get_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        raise  # Let tenacity retry properly


# ---------------------------------------------------
# RAG Safety Logic
# ---------------------------------------------------
@lru_cache(maxsize=200)
def rag_flower_safety(flower):
    flower_key = flower.lower().strip()

    # Direct DB hit
    if flower_key in FLOWERS:
        return {
            "verified": True,
            "source": "database",
            "flower": flower,
            "message": FLOWERS[flower_key],
        }

    # Fuzzy match
    match = get_close_matches(flower_key, FLOWERS.keys(), n=1, cutoff=0.76)
    if match:
        return {
            "verified": True,
            "source": "database",
            "flower": match[0],
            "message": FLOWERS[match[0]],
        }

    # Not in database → fallback to LLM
    try:
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are a flower toxicity expert. If the flower is not found "
                    "in the provided DB, answer using general knowledge but begin the reply with: "
                    "'(UNVERIFIED – not in database)'. Keep answers short."
                ),
            },
            {
                "role": "user",
                "content": f"Is the flower '{flower}' safe for cats and dogs?",
            },
        ]

        llm_answer = ask_openai(prompt)
        unverified = llm_answer.lower().startswith("(unverified")

        return {
            "verified": not unverified and False,
            "source": "llm",
            "flower": flower,
            "message": llm_answer,
        }

    except Exception as e:
        print("LLM error:", e)
        return {
            "verified": False,
            "source": "error",
            "flower": flower,
            "message": f"⚠️ Error checking safety: {e}",
        }


# ---------------------------------------------------
# Flask Server
# ---------------------------------------------------

app = Flask(__name__)
CORS(app)

@app.route("/flower-check", methods=["POST"])
def flower_check():
    data = request.get_json(silent=True)
    flower = (data.get("flower") or "").strip()

    if not flower:
        return jsonify({"error": "Flower name missing"}), 400

    result = rag_flower_safety(flower)

    # Add a note for unverified results
    if result["source"] == "llm":
        result["note"] = (
            "This result was generated by AI and not found in the verified database. "
            "Consult a veterinarian for authoritative guidance."
        )

    return jsonify(result)


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "Flower Safety API running"})


if __name__ == "__main__":
    app.run(debug=True)

