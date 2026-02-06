"""Minimal Pokédex web UI backed by the local pokeindex.db SQLite file."""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from flask import Flask, abort, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pokeindex.db"

if not DB_PATH.exists():
	raise SystemExit("pokeindex.db 不存在，请先运行 get_poke_index.py 同步数据。")

app = Flask(__name__)


def get_connection() -> sqlite3.Connection:
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn


def extract_localized_names(species: Dict) -> Dict[str, str]:
	names = {
		"en": species.get("name"),
		"ja": None,
		"zh": None,
	}
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
		if not names[key]:
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


def fetch_types(conn: sqlite3.Connection, pokemon_id: int) -> List[str]:
	rows = conn.execute(
		"SELECT type_name FROM pokemon_types WHERE pokemon_id = ? ORDER BY slot ASC",
		(pokemon_id,),
	).fetchall()
	return [row[0] for row in rows]


def fetch_abilities(conn: sqlite3.Connection, pokemon_id: int) -> List[Dict[str, str]]:
	rows = conn.execute(
		"""
		SELECT ability_name, is_hidden
		FROM pokemon_abilities
		WHERE pokemon_id = ?
		ORDER BY slot ASC
		""",
		(pokemon_id,),
	).fetchall()
	return [
		{"name": row[0], "is_hidden": bool(row[1])}
		for row in rows
	]


def fetch_stats(conn: sqlite3.Connection, pokemon_id: int) -> List[Dict[str, int]]:
	rows = conn.execute(
		"""
		SELECT stat_name, base_stat, effort
		FROM pokemon_stats
		WHERE pokemon_id = ?
		""",
		(pokemon_id,),
	).fetchall()
	order = ["hp", "attack", "defense", "special-attack", "special-defense", "speed"]
	stats_map = {row[0]: {"base": row[1], "effort": row[2]} for row in rows}
	return [
		{"label": name.upper().replace("-", " "), "base": stats_map.get(name, {}).get("base", 0)}
		for name in order
	]


def get_egg_groups(species: Dict) -> List[str]:
	return [group.get("name") for group in species.get("egg_groups", [])]


def db_signature() -> float:
	return DB_PATH.stat().st_mtime


@lru_cache(maxsize=2)
def load_evolution_graph(signature: float) -> Dict[str, Dict]:
	with get_connection() as conn:
		rows = conn.execute(
			"SELECT id, name, species_json FROM pokemon"
		).fetchall()
	index: Dict[str, Dict] = {}
	children: Dict[str, List[str]] = {}
	for row in rows:
		species = json.loads(row["species_json"])
		species_name = species.get("name")
		names = extract_localized_names(species)
		parent = (species.get("evolves_from_species") or {}).get("name")
		index[species_name] = {
			"id": row["id"],
			"slug": row["name"],
			"names": names,
			"parent": parent,
		}
		if parent:
			children.setdefault(parent, []).append(species_name)
	return {"index": index, "children": children}


def build_evolution_chain(species_name: str) -> List[List[Dict]]:
	signature = db_signature()
	graph = load_evolution_graph(signature)
	index = graph["index"]
	children = graph["children"]
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
			node["display_name"] = node["names"].get("zh") or node["names"].get("en")
			stage_entries.append(node)
			next_stage.extend(children.get(name, []))
		if stage_entries:
			stages.append(stage_entries)
		current = next_stage
	return stages


def search_matches(term: str, names: Dict[str, str], pokemon_id: int, slug: str) -> bool:
	if not term:
		return True
	needle = term.lower()
	for candidate in (
		str(pokemon_id),
		slug,
		names.get("en", ""),
		names.get("zh", ""),
		names.get("ja", ""),
	):
		if candidate and needle in candidate.lower():
			return True
	return False


def collect_pokemon_cards(term: str) -> List[Dict]:
	with get_connection() as conn:
		rows = conn.execute(
			"SELECT id, name, pokemon_json, species_json FROM pokemon ORDER BY id"
		).fetchall()
	cards: List[Dict] = []
	for row in rows:
		pokemon = json.loads(row["pokemon_json"])
		species = json.loads(row["species_json"])
		names = extract_localized_names(species)
		if not search_matches(term, names, row["id"], row["name"]):
			continue
		cards.append(
			{
				"id": row["id"],
				"slug": row["name"],
				"names": names,
				"types": [item["type"]["name"] for item in pokemon.get("types", [])],
				"sprite": extract_sprite(pokemon),
				"description": pick_description(species),
			}
		)
	return cards


@app.route("/")
def index() -> str:
	term = request.args.get("q", "").strip()
	cards = collect_pokemon_cards(term)
	return render_template("index.html", search_term=term, cards=cards)


@app.route("/pokemon/<int:pokemon_id>")
def pokemon_detail(pokemon_id: int) -> str:
	with get_connection() as conn:
		row = conn.execute(
			"SELECT * FROM pokemon WHERE id = ?",
			(pokemon_id,),
		).fetchone()
		if not row:
			abort(404)
		pokemon = json.loads(row["pokemon_json"])
		species = json.loads(row["species_json"])
		names = extract_localized_names(species)
		context = {
			"id": row["id"],
			"slug": row["name"],
			"names": names,
			"sprite": extract_sprite(pokemon),
			"description": pick_description(species),
			"types": fetch_types(conn, pokemon_id),
			"abilities": fetch_abilities(conn, pokemon_id),
			"stats": fetch_stats(conn, pokemon_id),
			"egg_groups": get_egg_groups(species),
			"height": pokemon.get("height"),
			"weight": pokemon.get("weight"),
			"base_experience": pokemon.get("base_experience"),
		}
		chain = build_evolution_chain(species.get("name"))
	return render_template(
		"detail.html",
		pokemon=context,
		evolution_chain=chain,
	)


if __name__ == "__main__":
	app.run(debug=True)
