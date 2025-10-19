import os
import requests
import hashlib
from PIL import Image
import numpy as np
import torch
import json
import random
from typing import List, Tuple, Dict, Optional

import folder_paths
import server

class BooruImageLoader:
    """Loads images from Safebooru/Danbooru based on tags in selective or random mode, caching them locally."""

    @classmethod
    def INPUT_TYPES(cls):
        """Define input types for the node."""
        return {
            "required": {
                "website": (["Safebooru", "Danbooru", "Safebooru & Danbooru"], {"default": "Safebooru"}),
                "mode": (["selective", "random"], {"default": "selective"}),
                "tags": ("STRING", {"multiline": False, "default": "1girl solo breasts -speech_bubble -furry -simple_background -white_background -commentary_request -translation_request"}),
                "save_to": ("STRING", {"default": "booru_downloads"}),
                "page_number": ("INT", {"default": 0, "min": 0}),
                "selected_image_url": ("STRING", {"multiline": False, "default": "Select URL..."}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "tags")
    FUNCTION = "load_image_from_booru"
    CATEGORY = "Alcatraz/Image Loaders"
    OUTPUT_NODE = True

    def _fetch_urls(self, website: str, tags: str, page: int) -> List[Tuple[str, str]]:
        """Fetch image URLs and tags from specified booru website."""
        if website in ["Safebooru", "Safebooru & Danbooru"]:
            safebooru_data = self._fetch_safebooru(tags, page)
            if website == "Safebooru":
                return safebooru_data
        if website in ["Danbooru", "Safebooru & Danbooru"]:
            danbooru_data = self._fetch_danbooru(tags, page)
            if website == "Danbooru":
                return danbooru_data
        # Combine and deduplicate for Safebooru & Danbooru
        seen_urls = set()
        return [(url, tags_str) for url, tags_str in safebooru_data + danbooru_data if not (url in seen_urls or seen_urls.add(url))]

    def _fetch_safebooru(self, tags: str, page: int) -> List[Tuple[str, str]]:
        """Fetch image URLs and tags from Safebooru."""
        try:
            url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags={tags.replace(',', '').replace(' ', '+')}&pid={page}"
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                print(f"Safebooru: Unexpected data format for tags '{tags}' page {page}")
                return []
            return [(item["file_url"], item["tags"].replace(" ", ", "))
                    for item in data if item.get("file_url") and item.get("tags")]
        except Exception as e:
            print(f"Safebooru: Error fetching URLs for tags '{tags}': {e}")
            return []

    def _fetch_danbooru(self, tags: str, page: int) -> List[Tuple[str, str]]:
        """Fetch image URLs and tags from Danbooru."""
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
            print(f"Danbooru: Error fetching URLs for tags '{tags}': {e}")
            return []

    def _create_error_image(self, color: str = "black") -> Tuple[torch.Tensor, torch.Tensor, str]:
        """Generate an error image tensor with a solid mask."""
        img = Image.new("RGB", (64, 64), color)
        img_np = np.array(img).astype(np.float32) / 255.0
        tensor = torch.from_numpy(img_np)[None,]
        mask = torch.ones_like(tensor[:, :, :, 0])
        return tensor, mask, ""

    def load_image_from_booru(self, website: str, mode: str, tags: str, save_to: str, page_number: int, selected_image_url: str, prompt: Optional[Dict] = None, extra_pnginfo: Optional[Dict] = None):
        """Load an image from a booru website, cache it, and return tensor, mask, and tags."""
        save_dir = os.path.join(folder_paths.get_input_directory(), save_to or "booru_downloads")
        os.makedirs(save_dir, exist_ok=True)

        # Select image URL and tags
        if mode == "random":
            image_data = self._fetch_urls(website, tags, page_number)
            if not image_data:
                print(f"Booru Loader: No images found for tags '{tags}', page {page_number}, website {website}")
                return self._create_error_image()
            url, tags_str = random.choice(image_data)
        else:  # selective mode
            if selected_image_url == "Select URL..." or not selected_image_url.startswith(("http://", "https://")):
                print(f"Booru Loader: Invalid URL '{selected_image_url}' in selective mode")
                return self._create_error_image()
            url, tags_str = selected_image_url.split("|", 1) if "|" in selected_image_url else (selected_image_url, "")

        if not url:
            print("Booru Loader: No valid image URL determined")
            return self._create_error_image("red")

        # Generate cached filename
        filename_base = hashlib.sha256(url.encode()).hexdigest()[:16]
        ext = os.path.splitext(requests.utils.urlparse(url).path)[1].lower() or ".jpg"
        ext = ".jpg" if ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"] else ext
        filename = f"booru_{filename_base}{ext}"
        full_path = os.path.join(save_dir, filename)

        # Load or download image
        try:
            img = Image.open(full_path).convert("RGB") if os.path.exists(full_path) else None
            if not img:
                print(f"Booru Loader: Downloading {url}")
                headers = {"User-Agent": "ComfyUI-BooruLoaderNode/1.0"}
                response = requests.get(url, headers=headers, stream=True, timeout=30)
                response.raise_for_status()
                with open(full_path, "wb") as f:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                img = Image.open(full_path).convert("RGB")

            # Convert to tensor
            img_np = np.array(img).astype(np.float32) / 255.0
            tensor = torch.from_numpy(img_np)[None,]
            mask = torch.ones_like(tensor[:, :, :, 0])

            # Add metadata
            if prompt and extra_pnginfo:
                metadata = {
                    "booru_source_website": website,
                    "booru_source_url": url,
                    "booru_tags": tags_str,
                    "booru_mode": mode,
                    "booru_query_tags": tags if mode == "random" else "N/A (Selective)",
                    "booru_query_page": page_number if mode == "random" else "N/A (Selective)"
                }
                extra_pnginfo.setdefault("workflow", {})["booru_loader_metadata"] = metadata

            print(f"Booru Loader: Loaded {url}, tags: {tags_str[:100]}...")
            return tensor, mask, tags_str

        except Exception as e:
            print(f"Booru Loader: Error processing {url}: {e}")
            return self._create_error_image("red")

@server.PromptServer.instance.routes.get("/booru-proxy")
async def get_booru_urls(request):
    """API endpoint to fetch image URLs and tags from booru websites."""
    tags = request.query.get("tags", "")
    try:
        page = int(request.query.get("page", "0"))
        website = request.query.get("website", "Safebooru")
    except ValueError:
        return server.web.json_response({"status": "error", "values": ["Invalid page number"]}, status=400)

    if not tags:
        return server.web.json_response({"status": "error", "values": ["Missing tags parameter"]}, status=400)

    image_data = BooruImageLoader()._fetch_urls(website, tags, page)
    if image_data:
        return server.web.json_response({"status": "success", "values": [{"url": url, "tags": tags} for url, tags in image_data]})
    return server.web.json_response({"status": "info", "values": ["No results found"]})