import os
import json
from pathlib import Path
import requests
import folder_paths
import server
import concurrent.futures

# ---- Global Configuration for JSON Path ----

# Global configuration
CURRENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER: Path = Path(os.path.join(str(Path(__file__).parent.parent.resolve()), "json"))

# Define the full path for the keywords cache file
JSON_FILE = JSON_FOLDER / "lora_keywords.json"


# ---- JSON Cache Management ----

def load_keywords_from_json():
    """Loads the keywords dictionary from the JSON file."""
    if not os.path.exists(JSON_FILE):
        os.makedirs(JSON_FOLDER, exist_ok=True)
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        return {}
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}

def save_keywords_to_json(data):
    """Saves the keywords dictionary to the JSON file."""
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# In-memory cache to reduce disk reads during a session
LORA_KEYWORDS_CACHE = load_keywords_from_json()


# ---- Civitai API Search Worker ----

def search_civitai_paginated(lora_stem: str, query: str, model_type: str):
    """
    Performs a paginated search on the Civitai API for a specific model type.

    Args:
        lora_stem (str): The filename stem of the LoRA to match.
        query (str): The search query string.
        model_type (str): The model type to search for ('LORA' or 'LoCon').

    Returns:
        list: A list of found trigger words, or None if not found or on error.
    """
    session = requests.Session()
    base_url = f"https://civitai.com/api/v1/models?limit=25&query={query}&types={model_type}&nsfw=true"
    print(base_url)
    current_page_url = base_url

    while current_page_url:
        try:
            response = session.get(current_page_url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed for {model_type} at {current_page_url}: {e}")
            return None # Indicate failure for this search type

        items = data.get('items', [])
        if not items:
            break # No more items, end of search

        for model in items:
            for version in model.get('modelVersions', []):
                for file_info in version.get('files', []):
                    if Path(file_info.get('name', '')).stem == lora_stem:
                        print(f"Match found for '{lora_stem}' in type '{model_type}'!")
                        return version.get('trainedWords', [])

        # Move to the next page
        current_page_url = data.get("metadata", {}).get("nextPage")
    
    return None # Return None if not found after checking all pages


# ---- Main Fetch Logic with Multithreading ----

def fetch_triggers_for_lora(lora_name: str):
    """
    Queries the Civitai API in parallel for 'LORA' and 'LoCon' types with pagination.
    """
    global LORA_KEYWORDS_CACHE
    
    cached_data = LORA_KEYWORDS_CACHE.get(lora_name)
    if cached_data is not None:
        if isinstance(cached_data, dict) and cached_data.get("retry"):
            print(f"Retrying keyword search for '{lora_name}' due to a previous error.")
        else:
            return cached_data

    print(f"Searching keywords for '{lora_name}' on Civitai (parallel search for LORA & LoCon)...")
    
    lora_stem = Path(lora_name).stem
    query_word_1 = lora_stem.replace("_", "%20").replace("-", "%20")[:3].lower().strip()
    query_word_2 = lora_stem.replace("_", "%20").replace("-", "%20")[3:6].lower().strip()
    query = query_word_1 + "%20" + query_word_2
    
    found_words = None
    # NOUVEAU : Variable pour suivre si on a trouvé un match, même sans mots-clés
    match_found_with_empty_keywords = False
    model_types_to_search = ["LORA", "LoCon"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_type = {
            executor.submit(search_civitai_paginated, lora_stem, query, m_type): m_type
            for m_type in model_types_to_search
        }

        for future in concurrent.futures.as_completed(future_to_type):
            result = future.result()
            # Cas 1 : Résultat trouvé avec des mots-clés (liste non vide)
            if result: 
                found_words = result
                executor.shutdown(wait=False, cancel_futures=True)
                break
            # Cas 2 : Résultat trouvé mais la liste est vide ([])
            elif result is not None:
                match_found_with_empty_keywords = True

    # NOUVELLE LOGIQUE DE MISE EN CACHE AMÉLIORÉE
    if found_words:
        print(f"Keywords found for '{lora_name}': {found_words}")
        LORA_KEYWORDS_CACHE[lora_name] = found_words
    elif match_found_with_empty_keywords:
        print(f"No Keywords found for '{lora_name}', but a match was found. Caching empty list.")
        LORA_KEYWORDS_CACHE[lora_name] = [] # On sauvegarde une liste vide, pas une erreur !
        found_words = []
    else:
        print(f"Civitai API ERROR or no match found for '{lora_name}'. Caching error for retry.")
        error_info = {"error": "API search failed or no match found after full search.", "retry": True}
        LORA_KEYWORDS_CACHE[lora_name] = error_info
        found_words = [] # On retourne une liste vide à l'UI pour éviter de bloquer

    save_keywords_to_json(LORA_KEYWORDS_CACHE)
    return found_words

# ---- API Endpoint for JavaScript ----

@server.PromptServer.instance.routes.get("/lora_keywords/{lora_name}")
async def get_lora_keywords_endpoint(request):
    lora_name = request.match_info['lora_name']
    keywords = fetch_triggers_for_lora(lora_name)
    return server.web.json_response(keywords)


# ---- ComfyUI Node Class ----

class LoraLoaderAndKeywords:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "lora_name": (folder_paths.get_filename_list("loras"),),
                "lora_strength": ("FLOAT", {"default": 1.0, "min": -10.0, "max": 10.0, "step": 0.01}),
                "trigger_word": ("STRING", {"default": "", "multiline": False}), # Placeholder for the dynamic combo box
            },
            "optional": {
                "optional_lora_stack": ("LORA_STACK",),
            },
        }

    RETURN_TYPES = ("LORA_STACK", "STRING")
    RETURN_NAMES = ("lora_stack", "selected_trigger_word")
    FUNCTION = "load_lora"
    CATEGORY = "loaders"

    def load_lora(self, lora_name, lora_strength, trigger_word, optional_lora_stack=None):
        lora_stack = []
        if optional_lora_stack:
            lora_stack.extend([l for l in optional_lora_stack if l[0] != "None"])
        
        lora_stack.append((lora_name, lora_strength, lora_strength))
        
        return (lora_stack, trigger_word)