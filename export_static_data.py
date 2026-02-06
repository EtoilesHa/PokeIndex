"""Export the local pokeindex.db contents into a static JSON payload.

This script prepares the dataset for the GitHub Pages frontend by flattening the
SQLite records into a self-contained structure that the browser can fetch.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "pokeindex.db"
DEFAULT_OUTPUT = BASE_DIR / "docs" / "data" / "pokemon.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Pokédex data to JSON")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to the SQLite database (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Destination JSON file (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def get_connection(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def extract_localized_names(species: Dict) -> Dict[str, str]:
    names = {"en": species.get("name"), "ja": None, "zh": None}
    zh_hans = None
    zh_hant = None
    for entry in species.get("names", []):
        lang_raw = entry.get("language", {}).get("name")
        lang = lang_raw.lower() if lang_raw else None
        value = entry.get("name")
        if not value:
            continue
        if lang == "en":
            names["en"] = value
        elif lang in ("ja", "ja-hrkt"):
            names["ja"] = value
        elif lang == "zh-hans":
            zh_hans = value
        elif lang == "zh-hant":
            zh_hant = value
    names["zh"] = zh_hans or zh_hant or names.get("en")
    for key, fallback in (("ja", "en"), ("zh", "en")):
        if not names.get(key):
            names[key] = names.get(fallback)
    return names


def pick_description(species: Dict) -> str:
    preferred = ("zh-hans", "zh-hant", "ja", "ja-hrkt", "en")
    cache: Dict[str, str] = {}
    for entry in species.get("flavor_text_entries", []):
        lang_raw = entry.get("language", {}).get("name")
        lang = lang_raw.lower() if lang_raw else None
        text = entry.get("flavor_text")
        if not lang or not text:
            continue
        cleaned = text.replace("\n", " ").replace("\u000c", " ")
        cache.setdefault(lang, cleaned)
    for language in preferred:
        if cache.get(language):
            return cache[language]
    return next(iter(cache.values()), "")


def extract_sprite(pokemon: Dict) -> str:
    other = pokemon.get("sprites", {}).get("other", {})
    for key in ("official-artwork", "home", "dream_world"):
        candidate = other.get(key, {}).get("front_default")
        if candidate:
            return candidate
    return pokemon.get("sprites", {}).get("front_default") or ""


def collect_types(conn: sqlite3.Connection) -> Dict[int, List[str]]:
    mapping: Dict[int, List[str]] = defaultdict(list)
    rows = conn.execute(
        "SELECT pokemon_id, type_name FROM pokemon_types ORDER BY slot"
    ).fetchall()
    for row in rows:
        mapping[row[0]].append(row[1])
    return mapping


def collect_abilities(conn: sqlite3.Connection) -> Dict[int, List[Dict[str, bool]]]:
    mapping: Dict[int, List[Dict[str, bool]]] = defaultdict(list)
    rows = conn.execute(
        """
        SELECT pokemon_id, ability_name, is_hidden
        FROM pokemon_abilities
        ORDER BY slot
        """
    ).fetchall()
    for row in rows:
        mapping[row[0]].append({"name": row[1], "is_hidden": bool(row[2])})
    return mapping


def stat_order() -> List[str]:
    return [
        "hp",
        "attack",
        "defense",
        "special-attack",
        "special-defense",
        "speed",
    ]


def empty_stats() -> List[Dict[str, int]]:
    return [
        {"label": name.upper().replace("-", " "), "base": 0}
        for name in stat_order()
    ]


def collect_stats(conn: sqlite3.Connection) -> Dict[int, List[Dict[str, int]]]:
    rows = conn.execute(
        """
        SELECT pokemon_id, stat_name, base_stat
        FROM pokemon_stats
        """
    ).fetchall()
    order = stat_order()
    grouped: Dict[int, Dict[str, Dict[str, int]]] = defaultdict(dict)
    for row in rows:
        grouped[row[0]][row[1]] = {"label": row[1], "base": row[2]}
    prepared: Dict[int, List[Dict[str, int]]] = {}
    for pokemon_id, stats_map in grouped.items():
        prepared[pokemon_id] = [
            {
                "label": name.upper().replace("-", " "),
                "base": stats_map.get(name, {"base": 0}).get("base", 0),
            }
            for name in order
        ]
    return prepared


def get_egg_groups(species: Dict) -> List[str]:
    return [group.get("name") for group in species.get("egg_groups", [])]


def build_evolution_index(rows: Sequence[sqlite3.Row]) -> Dict[str, Dict]:
    index: Dict[str, Dict] = {}
    children: Dict[str, List[str]] = defaultdict(list)
    for row in rows:
        species = json.loads(row["species_json"])
        species_name = species.get("name")
        if not species_name:
            continue
        names = extract_localized_names(species)
        parent = (species.get("evolves_from_species") or {}).get("name")
        index[species_name] = {
            "id": row["id"],
            "slug": row["name"],
            "names": names,
            "parent": parent,
        }
        if parent:
            children[parent].append(species_name)
    for siblings in children.values():
        siblings.sort()
    return {"index": index, "children": children}


def build_chain(species_name: str, index: Dict[str, Dict], children: Dict[str, List[str]]):
    if species_name not in index:
        return []
    root = species_name
    while index.get(root, {}).get("parent") and index[root]["parent"] in index:
        root = index[root]["parent"]
    stages: List[List[Dict]] = []
    current = [root]
    visited = set()
    while current:
        stage_entries = []
        next_stage: List[str] = []
        for name in current:
            if name in visited or name not in index:
                continue
            visited.add(name)
            node = index[name]
            stage_entries.append(
                {
                    "id": node["id"],
                    "slug": node["slug"],
                    "names": node["names"],
                    "display_name": node["names"].get("zh") or node["names"].get("en"),
                }
            )
            next_stage.extend(children.get(name, []))
        if stage_entries:
            stage_entries.sort(key=lambda item: item["id"])
            stages.append(stage_entries)
        current = next_stage
    return stages


def build_all_chains(rows: Sequence[sqlite3.Row]) -> Dict[str, List[List[Dict]]]:
    graph = build_evolution_index(rows)
    index = graph["index"]
    children = graph["children"]
    chains: Dict[str, List[List[Dict]]] = {}
    for species_name in index.keys():
        chains[species_name] = build_chain(species_name, index, children)
    return chains


def serialize_dataset(conn: sqlite3.Connection) -> Dict:
    rows = conn.execute(
        "SELECT id, name, pokemon_json, species_json FROM pokemon ORDER BY id"
    ).fetchall()
    types = collect_types(conn)
    abilities = collect_abilities(conn)
    stats = collect_stats(conn)
    chains = build_all_chains(rows)

    dataset = []
    for row in rows:
        pokemon_blob = json.loads(row["pokemon_json"])
        species_blob = json.loads(row["species_json"])
        species_name = species_blob.get("name")
        names = extract_localized_names(species_blob)
        entry = {
            "id": row["id"],
            "slug": row["name"],
            "names": names,
            "sprite": extract_sprite(pokemon_blob),
            "description": pick_description(species_blob),
            "types": types.get(row["id"], []),
            "abilities": abilities.get(row["id"], []),
            "stats": stats.get(row["id"], empty_stats()),
            "egg_groups": get_egg_groups(species_blob),
            "height": pokemon_blob.get("height"),
            "weight": pokemon_blob.get("weight"),
            "base_experience": pokemon_blob.get("base_experience"),
            "evolution_chain": chains.get(species_name, []),
        }
        dataset.append(entry)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(dataset),
        "pokemon": dataset,
    }


def main() -> None:
    args = parse_args()
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(args.db_path) as conn:
        payload = serialize_dataset(conn)

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {payload['total']} Pokémon entries to {output_path}")


if __name__ == "__main__":
    main()
