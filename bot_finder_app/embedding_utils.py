import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
from tqdm import tqdm

try:
    import openai
except Exception:  # pragma: no cover - optional dependency
    openai = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None

# Directory containing augmented bot definitions relative to repo root
DEFS_DIR = Path(__file__).resolve().parent.parent / "augmented_defs"
# Cached index path
CACHE_PATH = Path(__file__).resolve().parent / "index_cache.json"
# Embedding model for OpenAI
EMBED_MODEL = "text-embedding-3-small"

# increase when index schema changes
CACHE_VERSION = 2

_transformer = None

def load_bots() -> Dict[str, dict]:
    """Load bot definition JSON files."""
    bots = {}
    for path in DEFS_DIR.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                bots[path.stem] = json.load(f)
        except Exception:
            continue
    return bots

def get_embedding(text: str) -> List[float]:
    """Get embedding vector using OpenAI or a local model."""
    if openai and os.getenv("OPENAI_API_KEY"):
        resp = openai.embeddings.create(model=EMBED_MODEL, input=[text])
        return resp.data[0].embedding
    if SentenceTransformer:
        global _transformer
        if _transformer is None:
            _transformer = SentenceTransformer("all-MiniLM-L6-v2")
        return _transformer.encode(text).tolist()
    raise RuntimeError("No embedding backend available")


def extract_app_description(data: dict) -> str:
    """Return the most useful description text for a bot."""
    for key in ("description", "longDescription", "shortDescription"):
        desc = data.get(key)
        if isinstance(desc, str) and desc.strip():
            return desc.strip()
    return ""


def extract_command_descriptions(data: dict) -> List[Tuple[str, Optional[str]]]:
    """Return list of (title, description) command pairs."""
    commands: List[Tuple[str, Optional[str]]] = []
    for bot in data.get("bots", []):
        for cl in bot.get("commandLists", []):
            for cmd in cl.get("commands", []):
                title = cmd.get("title")
                if not title:
                    continue
                desc = cmd.get("description")
                commands.append((title, desc))
    return commands

def build_index(bots: Dict[str, dict]) -> List[dict]:
    """Build embedding index from bot descriptions, commands and prompts."""
    index = []
    for bot_id, data in bots.items():
        bot_name = data.get("name", bot_id)

        # app description
        desc = extract_app_description(data)
        if desc:
            vec = get_embedding(desc)
            index.append({
                "bot_id": bot_id,
                "bot_name": bot_name,
                "prompt": desc,
                "description": desc,
                "command": None,
                "kind": "app_description",
                "embedding": vec,
            })

        # command descriptions
        for title, c_desc in extract_command_descriptions(data):
            text = f"{title}: {c_desc}" if c_desc else title
            vec = get_embedding(text)
            index.append({
                "bot_id": bot_id,
                "bot_name": bot_name,
                "prompt": text,
                "description": c_desc,
                "command": title,
                "kind": "command",
                "embedding": vec,
            })

        # example prompts
        for ex in data.get("examplePrompts") or []:
            prompt = ex.get("prompt")
            if not prompt:
                continue
            vec = get_embedding(prompt)
            entry = {
                "bot_id": bot_id,
                "bot_name": bot_name,
                "prompt": prompt,
                "description": ex.get("description"),
                "command": ex.get("command"),
                "kind": "example",
                "embedding": vec,
            }
            index.append(entry)
    return index

def load_index(use_cache: bool = True) -> Tuple[List[dict], Dict[str, dict]]:
    """Load bots and embedding index, optionally from cache."""
    bots = load_bots()

    if use_cache and CACHE_PATH.exists():
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cached = json.load(f)
        if isinstance(cached, dict) and cached.get("_version") == CACHE_VERSION:
            return cached["index"], bots

    index = build_index(bots)

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({"_version": CACHE_VERSION, "index": index}, f)

    return index, bots

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def search(query: str, index: List[dict], top_n: int = 5) -> List[Tuple[str, List[dict]]]:
    """Return top matching bots with example prompts."""
    q_vec = np.array(get_embedding(query))
    scored = []
    for entry in index:
        v = np.array(entry["embedding"])
        score = cosine_similarity(q_vec, v)
        scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)

    grouped: Dict[str, List[dict]] = {}
    for score, entry in scored:
        bot_id = entry["bot_id"]
        entry = dict(entry)
        entry["score"] = score
        grouped.setdefault(bot_id, []).append(entry)

    # Sort bots by best score and limit matches
    results = []
    for bot_id, items in grouped.items():
        items.sort(key=lambda x: x["score"], reverse=True)
        results.append((bot_id, items[:top_n]))
    results.sort(key=lambda x: x[1][0]["score"], reverse=True)
    return results[:top_n]

