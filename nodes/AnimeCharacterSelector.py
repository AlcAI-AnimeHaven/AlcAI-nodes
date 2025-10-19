import torch
import numpy as np
import hashlib
import os
import requests
import json
import random
import re
from server import PromptServer
from aiohttp import web
from typing import Dict, List, Set, Tuple
from pathlib import Path

# Global configuration
CURRENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
# JSON_FOLDER: str = os.path.join(CURRENT_DIR, "Anime_character_json")
JSON_FOLDER: str = os.path.join(str(Path(__file__).parent.parent.resolve()), "json")
CHARACTER_DATA_LOADED: Dict[str, List[str]] = {}  # Stores categorized character data

# API Endpoint
@PromptServer.instance.routes.get("/mira/get_character_data")
async def get_character_data_api(request: web.Request) -> web.Response:
    """Serve categorized character data via API."""
    if not CHARACTER_DATA_LOADED:
        print("[ACS Warning]: Data not loaded for /mira/get_character_data.")
        return web.json_response({"Error": "Data not loaded"}, status=503)
    return web.json_response(CHARACTER_DATA_LOADED)

class AnimeCharacterSelector:
    """Custom node for selecting anime characters by category in ComfyUI."""
    
    def __init__(self) -> None:
        self.previous_character: str = ""

    @classmethod
    def INPUT_TYPES(cls) -> Dict[str, Dict[str, tuple]]:
        """Define input types using loaded character data."""
        if not CHARACTER_DATA_LOADED:
            print("[ACS Warning]: INPUT_TYPES called before data loaded. Using fallback.")
            return {
                "required": {
                    "Characters_from": (["Error: Data not loaded"],),
                    "character": (["random", "Error: Data not loaded"],)
                }
            }
        
        categories: List[str] = list(CHARACTER_DATA_LOADED.keys())
        all_characters: Set[str] = {"random"} | {c for cat in CHARACTER_DATA_LOADED.values() for c in cat if c != "random"}
        characters: List[str] = ["random"] + sorted(all_characters)
        return {
            "required": {
                "Characters_from": (categories,),
                "character": (characters,)
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("character_name",)
    FUNCTION = "select_character"
    CATEGORY = "generation_utils/character"

    @classmethod
    def IS_CHANGED(cls, characters_from: str, character: str, **kwargs) -> float:
        """Force re-execution if character is random or changed."""
        return float("nan") if character == "random" else hash(character)

    def select_character(self, Characters_from: str, character: str) -> Tuple[str]:
        """
        Select a character, handling random selection.

        Args:
            Characters_from: Category to select from.
            character: Specific character or "random".

        Returns:
            Tuple containing the selected character name.
        """
        if character != "random":
            return (character,)
        
        # Handle random selection
        possible_choices: List[str] = [c for c in CHARACTER_DATA_LOADED.get(Characters_from, []) if c != "random"]
        if not possible_choices:
            print(f"[ACS Warning]: No characters in '{Characters_from}'. Falling back to 'RANDOM'.")
            possible_choices = [c for c in CHARACTER_DATA_LOADED.get("RANDOM", []) if c != "random"]
            if not possible_choices:
                print("[ACS Error]: No characters available.")
                return ("Error: No characters available",)
        
        # Avoid repeating the previous character if possible
        potential_choices: List[str] = [c for c in possible_choices if c != self.previous_character] or possible_choices
        final_character: str = random.choice(potential_choices)
        self.previous_character = final_character
        return (final_character,)

def load_data() -> None:
    """Load character data from JSON or set error state."""
    global CHARACTER_DATA_LOADED
    json_file: str = os.path.join(JSON_FOLDER, "danbooru_chars_mp_sorted_top10p_no_multi.json")
    
    if not os.path.exists(json_file):
        print(f"[ACS Setup]: JSON file '{json_file}' not found.")
        CHARACTER_DATA_LOADED = {"Error": ["random", "Error: JSON Missing"]}
        return

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            CHARACTER_DATA_LOADED = json.load(f)
        print("[ACS Setup]: Character data loaded from JSON.")
        
        # Ensure "random" is first in each category and create "RANDOM" category
        all_characters: Set[str] = set()
        for category in CHARACTER_DATA_LOADED:
            if CHARACTER_DATA_LOADED[category][0] != "random":
                CHARACTER_DATA_LOADED[category].insert(0, "random")
            all_characters.update(c for c in CHARACTER_DATA_LOADED[category] if c != "random")
        CHARACTER_DATA_LOADED["RANDOM"] = ["random"] + sorted(all_characters)
        
    except Exception as e:
        print(f"[ACS Setup]: Error loading JSON: {e}")
        CHARACTER_DATA_LOADED = {"Error": ["random", "Error: JSON Load Failed"]}

# Initialize on script load
load_data()