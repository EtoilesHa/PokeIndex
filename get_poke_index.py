"""Synchronize Pokédex data from PokeAPI into a local SQLite database."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from sqlite3 import Cursor as SQLiteCursor
from sqlite3 import Error as SQLiteError
from typing import Dict, Generator, Iterable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_BASE = "https://pokeapi.co/api/v2"
DEFAULT_PAGE_SIZE = 200
DEFAULT_RATE_DELAY = 0.2
MAX_PAGE_SIZE = 500
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "pokeindex.db"



def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Download Pokédex data from PokeAPI and persist it locally."
	)
	parser.add_argument(
		"--db-path",
		default=os.getenv("POKE_DB_PATH") or str(DEFAULT_DB_PATH),
		help="Path to the SQLite database file (env: POKE_DB_PATH)",
	)
	parser.add_argument(
		"--names",
		nargs="+",
		help="Explicit Pokémon names or numeric IDs to refresh.",
	)
	parser.add_argument(
		"--limit",
		type=int,
		help="Restrict how many Pokémon are pulled (useful for quick tests).",
	)
	parser.add_argument(
		"--offset",
		type=int,
		default=0,
		help="Pagination offset when crawling the entire Pokédex.",
	)
	parser.add_argument(
		"--page-size",
		type=int,
		default=DEFAULT_PAGE_SIZE,
		help="Number of entries requested per API page (max %d)." % MAX_PAGE_SIZE,
	)
	parser.add_argument(
		"--sleep",
		type=float,
		default=DEFAULT_RATE_DELAY,
		help="Seconds to wait between API requests to stay within rate limits.",
	)
	parser.add_argument(
		"--batch-size",
		type=int,
		default=25,
		help="Commit to the database after processing this many Pokémon.",
	)
	parser.add_argument(
		"--max-retries",
		type=int,
		default=5,
		help="Amount of automatic retries for transient HTTP errors.",
	)
	parser.add_argument(
		"--backoff",
		type=float,
		default=0.3,
		help="Exponential backoff factor for HTTP retries.",
	)
	parser.add_argument(
		"--log-level",
		default=os.getenv("POKE_LOG_LEVEL", "INFO"),
		help="Python logging level (DEBUG, INFO, ...).",
	)
	return parser.parse_args()


def configure_logging(level: str) -> None:
	numeric = getattr(logging, level.upper(), logging.INFO)
	logging.basicConfig(
		level=numeric,
		format="%(asctime)s | %(levelname)s | %(message)s",
		datefmt="%H:%M:%S",
	)


def build_session(max_retries: int, backoff: float) -> requests.Session:
	retry = Retry(
		total=max_retries,
		read=max_retries,
		connect=max_retries,
		backoff_factor=backoff,
		status=max_retries,
		status_forcelist=(429, 500, 502, 503, 504),
		allowed_methods=frozenset(["GET"]),
		raise_on_status=False,
	)
	adapter = HTTPAdapter(max_retries=retry)
	session = requests.Session()
	session.mount("https://", adapter)
	session.mount("http://", adapter)
	session.headers.update({"User-Agent": "pokeindex-sync/1.0"})
	return session


def connect_database(args: argparse.Namespace) -> SQLiteConnection:
	db_path = Path(args.db_path).expanduser()
	if not db_path.parent.exists():
		db_path.parent.mkdir(parents=True, exist_ok=True)
	connection = sqlite3.connect(str(db_path))
	connection.execute("PRAGMA foreign_keys = ON;")
	return connection


def ensure_schema(cursor: SQLiteCursor) -> None:
	schema_statements = [
		"""
		CREATE TABLE IF NOT EXISTS pokemon (
			id INTEGER PRIMARY KEY,
			name TEXT NOT NULL UNIQUE,
			base_experience INTEGER,
			height INTEGER,
			weight INTEGER,
			pokemon_order INTEGER,
			is_default INTEGER,
			location_area_encounters TEXT,
			species_name TEXT,
			species_color TEXT,
			species_capture_rate INTEGER,
			species_base_happiness INTEGER,
			species_growth_rate TEXT,
			habitat TEXT,
			shape TEXT,
			is_baby INTEGER,
			is_legendary INTEGER,
			is_mythical INTEGER,
			hatch_counter INTEGER,
			gender_rate INTEGER,
			generation TEXT,
			pokemon_json TEXT,
			species_json TEXT,
			updated_at TEXT DEFAULT CURRENT_TIMESTAMP
		);
		""",
		"""
		CREATE TABLE IF NOT EXISTS pokemon_abilities (
			pokemon_id INTEGER NOT NULL,
			ability_name TEXT NOT NULL,
			slot INTEGER NOT NULL,
			is_hidden INTEGER NOT NULL,
			PRIMARY KEY (pokemon_id, ability_name),
			FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE
		);
		""",
		"""
		CREATE TABLE IF NOT EXISTS pokemon_types (
			pokemon_id INTEGER NOT NULL,
			slot INTEGER NOT NULL,
			type_name TEXT NOT NULL,
			PRIMARY KEY (pokemon_id, slot),
			FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE
		);
		""",
		"""
		CREATE TABLE IF NOT EXISTS pokemon_stats (
			pokemon_id INTEGER NOT NULL,
			stat_name TEXT NOT NULL,
			base_stat INTEGER NOT NULL,
			effort INTEGER NOT NULL,
			PRIMARY KEY (pokemon_id, stat_name),
			FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE
		);
		""",
		"""
		CREATE TABLE IF NOT EXISTS pokemon_moves (
			pokemon_id INTEGER NOT NULL,
			move_name TEXT NOT NULL,
			version_group TEXT NOT NULL,
			learn_method TEXT NOT NULL,
			level_learned_at INTEGER NOT NULL,
			PRIMARY KEY (pokemon_id, move_name, version_group, learn_method, level_learned_at),
			FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE
		);
		""",
		"""
		CREATE TABLE IF NOT EXISTS pokemon_held_items (
			pokemon_id INTEGER NOT NULL,
			item_name TEXT NOT NULL,
			version_name TEXT NOT NULL,
			rarity INTEGER NOT NULL,
			PRIMARY KEY (pokemon_id, item_name, version_name),
			FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE
		);
		""",
		"""
		CREATE TABLE IF NOT EXISTS pokemon_game_indices (
			pokemon_id INTEGER NOT NULL,
			version_name TEXT NOT NULL,
			game_index INTEGER NOT NULL,
			PRIMARY KEY (pokemon_id, version_name),
			FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE
		);
		""",
		"""
		CREATE TABLE IF NOT EXISTS pokemon_forms (
			pokemon_id INTEGER NOT NULL,
			form_name TEXT NOT NULL,
			PRIMARY KEY (pokemon_id, form_name),
			FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE
		);
		""",
		"""
		CREATE TABLE IF NOT EXISTS pokemon_past_types (
			pokemon_id INTEGER NOT NULL,
			generation_name TEXT NOT NULL,
			slot INTEGER NOT NULL,
			type_name TEXT NOT NULL,
			PRIMARY KEY (pokemon_id, generation_name, slot),
			FOREIGN KEY (pokemon_id) REFERENCES pokemon(id) ON DELETE CASCADE
		);
		""",
	]

	for statement in schema_statements:
		cursor.execute(statement)


def iter_pokemon_targets(
	session: requests.Session,
	*,
	names: Optional[Iterable[str]],
	limit: Optional[int],
	offset: int,
	page_size: int,
) -> Generator[Dict[str, str], None, None]:
	if names:
		seen = set()
		for name in names:
			identifier = str(name).strip().lower()
			if not identifier or identifier in seen:
				continue
			seen.add(identifier)
			yield {
				"name": identifier,
				"url": f"{API_BASE}/pokemon/{identifier}",
			}
		return

	capped_page = max(1, min(page_size, MAX_PAGE_SIZE))
	fetched = 0
	next_url: Optional[str] = f"{API_BASE}/pokemon?offset={offset}&limit={capped_page}"

	while next_url:
		response = session.get(next_url, timeout=30)
		response.raise_for_status()
		payload = response.json()
		for entry in payload.get("results", []):
			if limit is not None and fetched >= limit:
				return
			yield entry
			fetched += 1
		next_url = payload.get("next")
		if limit is not None and fetched >= limit:
			break


def fetch_json(session: requests.Session, url: str, delay: float) -> Dict:
	response = session.get(url, timeout=30)
	response.raise_for_status()
	if delay:
		time.sleep(delay)
	return response.json()


def json_dump(data: Dict) -> str:
	return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def upsert_pokemon_row(cursor: SQLiteCursor, pokemon: Dict, species: Dict) -> None:
	values = {
		"id": pokemon["id"],
		"name": pokemon["name"],
		"base_experience": pokemon.get("base_experience"),
		"height": pokemon.get("height"),
		"weight": pokemon.get("weight"),
		"pokemon_order": pokemon.get("order"),
		"is_default": pokemon.get("is_default"),
		"location_area_encounters": pokemon.get("location_area_encounters"),
		"species_name": species.get("name"),
		"species_color": species.get("color", {}).get("name") if species.get("color") else None,
		"species_capture_rate": species.get("capture_rate"),
		"species_base_happiness": species.get("base_happiness"),
		"species_growth_rate": species.get("growth_rate", {}).get("name") if species.get("growth_rate") else None,
		"habitat": species.get("habitat", {}).get("name") if species.get("habitat") else None,
		"shape": species.get("shape", {}).get("name") if species.get("shape") else None,
		"is_baby": species.get("is_baby"),
		"is_legendary": species.get("is_legendary"),
		"is_mythical": species.get("is_mythical"),
		"hatch_counter": species.get("hatch_counter"),
		"gender_rate": species.get("gender_rate"),
		"generation": species.get("generation", {}).get("name") if species.get("generation") else None,
		"pokemon_json": json_dump(pokemon),
		"species_json": json_dump(species),
	}

	columns = ", ".join(values.keys())
	placeholders = ", ".join(["?"] * len(values))
	updates = ", ".join([f"{column}=excluded.{column}" for column in values.keys() if column != "id"] + ["updated_at=CURRENT_TIMESTAMP"])

	cursor.execute(
		f"""
		INSERT INTO pokemon ({columns})
		VALUES ({placeholders})
		ON CONFLICT(id) DO UPDATE SET {updates}
		""",
		list(values.values()),
	)


def reset_and_insert(
	cursor: SQLiteCursor,
	delete_sql: str,
	insert_sql: str,
	rows: Iterable[tuple],
	delete_args: tuple,
) -> None:
	cursor.execute(delete_sql, delete_args)
	entries = list(rows)
	if entries:
		unique_entries = list(dict.fromkeys(entries))
		cursor.executemany(insert_sql, unique_entries)


def sync_collections(cursor: SQLiteCursor, pokemon: Dict) -> None:
	pokemon_id = pokemon["id"]

	reset_and_insert(
		cursor,
		"DELETE FROM pokemon_abilities WHERE pokemon_id = ?",
		"INSERT INTO pokemon_abilities (pokemon_id, ability_name, slot, is_hidden) VALUES (?, ?, ?, ?)",
		(
			(
				pokemon_id,
				ability["ability"]["name"],
				ability["slot"],
				ability["is_hidden"],
			)
			for ability in pokemon.get("abilities", [])
		),
		(pokemon_id,),
	)

	reset_and_insert(
		cursor,
		"DELETE FROM pokemon_types WHERE pokemon_id = ?",
		"INSERT INTO pokemon_types (pokemon_id, slot, type_name) VALUES (?, ?, ?)",
		(
			(
				pokemon_id,
				poke_type["slot"],
				poke_type["type"]["name"],
			)
			for poke_type in pokemon.get("types", [])
		),
		(pokemon_id,),
	)

	reset_and_insert(
		cursor,
		"DELETE FROM pokemon_stats WHERE pokemon_id = ?",
		"INSERT INTO pokemon_stats (pokemon_id, stat_name, base_stat, effort) VALUES (?, ?, ?, ?)",
		(
			(
				pokemon_id,
				stat["stat"]["name"],
				stat["base_stat"],
				stat["effort"],
			)
			for stat in pokemon.get("stats", [])
		),
		(pokemon_id,),
	)

	reset_and_insert(
		cursor,
		"DELETE FROM pokemon_moves WHERE pokemon_id = ?",
		"INSERT INTO pokemon_moves (pokemon_id, move_name, version_group, learn_method, level_learned_at) VALUES (?, ?, ?, ?, ?)",
		(
			(
				pokemon_id,
				move["move"]["name"],
				detail["version_group"]["name"],
				detail["move_learn_method"]["name"],
				detail["level_learned_at"],
			)
			for move in pokemon.get("moves", [])
			for detail in move.get("version_group_details", [])
		),
		(pokemon_id,),
	)

	reset_and_insert(
		cursor,
		"DELETE FROM pokemon_held_items WHERE pokemon_id = ?",
		"INSERT INTO pokemon_held_items (pokemon_id, item_name, version_name, rarity) VALUES (?, ?, ?, ?)",
		(
			(
				pokemon_id,
				item["item"]["name"],
				version["version"]["name"],
				version["rarity"],
			)
			for item in pokemon.get("held_items", [])
			for version in item.get("version_details", [])
		),
		(pokemon_id,),
	)

	reset_and_insert(
		cursor,
		"DELETE FROM pokemon_game_indices WHERE pokemon_id = ?",
		"INSERT INTO pokemon_game_indices (pokemon_id, version_name, game_index) VALUES (?, ?, ?)",
		(
			(
				pokemon_id,
				entry["version"]["name"],
				entry["game_index"],
			)
			for entry in pokemon.get("game_indices", [])
		),
		(pokemon_id,),
	)

	reset_and_insert(
		cursor,
		"DELETE FROM pokemon_forms WHERE pokemon_id = ?",
		"INSERT INTO pokemon_forms (pokemon_id, form_name) VALUES (?, ?)",
		(
			(
				pokemon_id,
				form.get("name"),
			)
			for form in pokemon.get("forms", [])
		),
		(pokemon_id,),
	)

	reset_and_insert(
		cursor,
		"DELETE FROM pokemon_past_types WHERE pokemon_id = ?",
		"INSERT INTO pokemon_past_types (pokemon_id, generation_name, slot, type_name) VALUES (?, ?, ?, ?)",
		(
			(
				pokemon_id,
				past_type.get("generation", {}).get("name"),
				t["slot"],
				t["type"]["name"],
			)
			for past_type in pokemon.get("past_types", [])
			for t in past_type.get("types", [])
		),
		(pokemon_id,),
	)


def process_pokemon(
	session: requests.Session,
	cursor: SQLiteCursor,
	target: Dict[str, str],
	delay: float,
) -> None:
	pokemon_data = fetch_json(session, target["url"], delay)
	species_url = pokemon_data.get("species", {}).get("url")
	if not species_url:
		raise RuntimeError(f"Missing species URL for Pokémon {pokemon_data.get('name')}")
	species_data = fetch_json(session, species_url, delay)

	upsert_pokemon_row(cursor, pokemon_data, species_data)
	sync_collections(cursor, pokemon_data)


def main() -> int:
	args = parse_args()
	configure_logging(args.log_level)
	session = build_session(args.max_retries, args.backoff)

	try:
		connection = connect_database(args)
	except SQLiteError as exc:
		logging.error("Database connection failed: %s", exc)
		return 1

	processed = 0
	cursor = connection.cursor()
	ensure_schema(cursor)
	connection.commit()

	try:
		for target in iter_pokemon_targets(
			session,
			names=args.names,
			limit=args.limit,
			offset=args.offset,
			page_size=args.page_size,
		):
			try:
				process_pokemon(session, cursor, target, args.sleep)
			except Exception:
				connection.rollback()
				logging.exception("Failed to process %s", target.get("name"))
				continue

			processed += 1
			if processed % args.batch_size == 0:
				connection.commit()
				logging.info("Committed %s Pokémon", processed)

		if processed % args.batch_size != 0:
			connection.commit()
	finally:
		cursor.close()
		connection.close()

	logging.info("Completed sync for %s Pokémon", processed)
	return 0


if __name__ == "__main__":
	sys.exit(main())
