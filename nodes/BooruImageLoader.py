import os
import tempfile
import requests
import hashlib
import random  # Added: Required for random mode selection
from PIL import Image
import numpy as np
import torch
from typing import List, Tuple, Dict, Optional

import folder_paths
import server

class BooruImageLoader:
    """Loads images from Safebooru/Danbooru based on tags in selective or random mode, with optional local caching.
    
    In selective mode, uses a dropdown (via JS extension) to select from fetched URLs.
    save_path is optional and dynamic: only required/visible when save_locally is True.
    """

    @classmethod
    def INPUT_TYPES(cls):
        """Define input types. save_path is optional to support dynamic hiding in JS."""
        return {
            "required": {
                "website": (["Safebooru", "Danbooru", "Safebooru & Danbooru"], {"default": "Safebooru"}),
                "mode": (["selective", "random"], {"default": "selective"}),
                "tags": ("STRING", {"multiline": False, "default": "1girl solo breasts -speech_bubble -furry -simple_background -white_background -commentary_request -translation_request"}),
                "page_number": ("INT", {"default": 0, "min": 0}),
                "selected_image_url": ("STRING", {"multiline": False, "default": "Select URL..."}),  # Populated by JS combo dropdown
                "save_locally": ("BOOLEAN", {"default": False, "label_on": "Yes", "label_off": "No"}),
            },
            "optional": {  # Dynamic: JS adds widget only when save_locally=True
                "save_path": ("STRING", {"default": "booru_downloads", "multiline": False}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "tags")
    FUNCTION = "load_image_from_booru"
    CATEGORY = "Alcatraz/Image Loaders"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Force re-execution on input changes, including dynamic optional fields."""
        return float("NaN")

    def _fetch_urls(self, website: str, tags: str, page: int) -> List[Tuple[str, str]]:
        """Fetch image URLs and tags from the specified booru website(s), deduplicating if combined."""
        safebooru_data = self._fetch_safebooru(tags, page) if website in ["Safebooru", "Safebooru & Danbooru"] else []
        danbooru_data = self._fetch_danbooru(tags, page) if website in ["Danbooru", "Safebooru & Danbooru"] else []
        
        if website == "Safebooru":
            return safebooru_data
        elif website == "Danbooru":
            return danbooru_data
        # Combine and deduplicate for dual mode
        seen_urls = set()
        combined = safebooru_data + danbooru_data
        return [(url, tags_str) for url, tags_str in combined if not (url in seen_urls or seen_urls.add(url))]

    def _fetch_safebooru(self, tags: str, page: int) -> List[Tuple[str, str]]:
        """Fetch URLs and tags from Safebooru API."""
        try:
            encoded_tags = tags.replace(',', '').replace(' ', '+')
            url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags={encoded_tags}&pid={page}"
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                print(f"Safebooru: Unexpected data format for tags '{tags}' page {page}")
                return []
            return [(item["file_url"], item["tags"].replace(" ", ", ")) for item in data if item.get("file_url") and item.get("tags")]
        except Exception as e:
            print(f"Safebooru: Error fetching for tags '{tags}': {e}")
            return []

    def _fetch_danbooru(self, tags: str, page: int) -> List[Tuple[str, str]]:
        """Fetch URLs and tags from Danbooru API, limiting tags to prevent overload."""
        tag_list = tags.split()
        encoded_tags = "+".join(tag_list[:2] if len(tag_list) > 2 else tag_list)
        try:
            url = f"https://danbooru.donmai.us/posts.json?limit=100&tags={encoded_tags}&page={page}"
            headers = {"User-Agent": "ComfyUI-BooruLoaderNode/1.0"}
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                print(f"Danbooru: Unexpected data format for tags '{tags}' page {page}")
                return []
            return [(item.get("large_file_url") or item["file_url"], item["tag_string"].replace(" ", ", "))
                    for item in data if item.get("file_url") and item.get("tag_string") and not item.get("is_banned", False)]
        except Exception as e:
            print(f"Danbooru: Error fetching for tags '{tags}': {e}")
            return []

    def _create_error_image(self, color: str = "black", message: str = "") -> Tuple[torch.Tensor, torch.Tensor, str]:
        """Generate a placeholder error image tensor with optional error message for tags output."""
        img = Image.new("RGB", (64, 64), color)
        img_np = np.array(img).astype(np.float32) / 255.0
        tensor = torch.from_numpy(img_np)[None,]
        mask = torch.ones_like(tensor[:, :, :, 0])
        return tensor, mask, message

    def _download_to_temp(self, url: str) -> str:
        """Download image to a temporary file (path returned; file deleted after loading)."""
        try:
            headers = {"User-Agent": "ComfyUI-BooruLoaderNode/1.0"}
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            suffix = os.path.splitext(url.split('?')[0])[1] or '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                for chunk in response.iter_content(8192):
                    temp_file.write(chunk)
                return temp_file.name
        except Exception as e:
            print(f"Temp download error for {url}: {e}")
            raise

    def load_image_from_booru(self, website: str, mode: str, tags: str, page_number: int, selected_image_url: str, save_locally: bool, save_path: Optional[str] = None, prompt: Optional[Dict] = None, extra_pnginfo: Optional[Dict] = None):
        """Load image based on mode, handle temp/local saving, return tensor, mask, and tags.
        
        Handles optional save_path: Errors if save_locally=True but save_path missing/empty.
        """
        # Handle optional save_path
        if save_locally:
            if save_path is None or not str(save_path).strip():
                print("Booru Loader: save_path required when save_locally is True")
                return self._create_error_image("red", "Missing save path")
            save_dir = os.path.join(folder_paths.get_output_directory(), str(save_path).strip())
            os.makedirs(save_dir, exist_ok=True)
        else:
            save_dir = None

        # Determine URL and tags based on mode
        url: Optional[str] = None
        tags_str: str = ""
        if mode == "random":
            image_data = self._fetch_urls(website, tags, page_number)
            if not image_data:
                print(f"Booru Loader: No images found for tags '{tags}', page {page_number}, website {website}")
                return self._create_error_image()
            url, tags_str = random.choice(image_data)
        else:  # selective mode
            # Skip placeholders/invalids; expect JS-populated URL (possibly 'url|tags')
            if (not selected_image_url or 
                selected_image_url.startswith(("Select URL...", "Loading", "Error", "No results", "Random mode")) or
                not selected_image_url.startswith(("http://", "https://"))):
                print(f"Booru Loader: Invalid selected_image_url '{selected_image_url}' in selective mode")
                return self._create_error_image("yellow", "Select a valid URL from dropdown")
            if "|" in selected_image_url:
                url, tags_str = selected_image_url.split("|", 1)
            else:
                url = selected_image_url
                tags_str = ""  # Tags not embedded; could fetch separately if needed

        if not url:
            print("Booru Loader: No valid URL determined")
            return self._create_error_image("red", "No URL available")

        # Generate cache filename based on URL hash
        filename_base = hashlib.sha256(url.encode()).hexdigest()[:16]
        parsed_url = requests.utils.urlparse(url)
        ext = os.path.splitext(parsed_url.path)[1].lower() or ".jpg"
        if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
            ext = ".jpg"
        filename = f"booru_{filename_base}{ext}"
        full_path = os.path.join(save_dir, filename) if save_locally else None

        # Download/load image (to local or temp)
        img_path = full_path
        delete_after = not save_locally
        img = None
        try:
            if save_locally and os.path.exists(full_path):
                # Load from cache
                img = Image.open(full_path).convert("RGB")
            else:
                if save_locally:
                    print(f"Booru Loader: Downloading to local: {full_path}")
                else:
                    print(f"Booru Loader: Downloading to temp for {url}")
                    img_path = self._download_to_temp(url)

                # Perform download
                headers = {"User-Agent": "ComfyUI-BooruLoaderNode/1.0"}
                response = requests.get(url, headers=headers, stream=True, timeout=30)
                response.raise_for_status()
                with open(img_path, "wb") as f:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                img = Image.open(img_path).convert("RGB")

            # Immediate cleanup for temp files
            if delete_after and os.path.exists(img_path):
                os.unlink(img_path)

            # Convert to ComfyUI tensor format
            img_np = np.array(img).astype(np.float32) / 255.0
            tensor = torch.from_numpy(img_np)[None,]
            mask = torch.ones_like(tensor[:, :, :, 0])

            # Embed metadata in PNG info if available
            if prompt and extra_pnginfo:
                metadata = {
                    "booru_source_website": website,
                    "booru_source_url": url,
                    "booru_tags": tags_str,
                    "booru_mode": mode,
                    "booru_query_tags": tags if mode == "random" else "N/A (Selective)",
                    "booru_query_page": page_number if mode == "random" else "N/A (Selective)",
                    "booru_save_locally": save_locally,
                    "booru_save_path": save_path if save_locally else "Temporary (deleted)"
                }
                extra_pnginfo.setdefault("workflow", {})["booru_loader_metadata"] = metadata

            print(f"Booru Loader: Successfully loaded {url}, tags: {tags_str[:100]}...")
            return tensor, mask, tags_str

        except Exception as e:
            # Cleanup on error
            if delete_after and img_path and os.path.exists(img_path):
                os.unlink(img_path)
            print(f"Booru Loader: Error processing {url}: {e}")
            return self._create_error_image("red", f"Load error: {str(e)[:50]}")

@server.PromptServer.instance.routes.get("/booru-proxy")
async def get_booru_urls(request):
    """API endpoint for JS extension to fetch URL/tag list for dropdown population."""
    tags = request.query.get("tags", "")
    try:
        page = int(request.query.get("page", "0"))
        website = request.query.get("website", "Safebooru")
    except ValueError:
        return server.web.json_response({"status": "error", "values": ["Invalid page number"]}, status=400)

    if not tags.strip():
        return server.web.json_response({"status": "error", "values": ["Missing tags"]}, status=400)

    loader = BooruImageLoader()
    image_data = loader._fetch_urls(website, tags, page)
    if image_data:
        return server.web.json_response({
            "status": "success",
            "values": [{"url": url, "tags": tags_str} for url, tags_str in image_data]
        })
    return server.web.json_response({"status": "info", "values": ["No results found"]})