import os
import random
import torch
import numpy as np
from PIL import Image, ImageOps
import folder_paths
from aiohttp import web
import server
import hashlib
import shutil

class ImageLoaderEnhanced:
    """Enhanced image loader for selecting and processing images from directories."""
    
    IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff')

    @classmethod
    def INPUT_TYPES(cls):
        """Define input types for the node, including directories and file selection modes."""
        input_dir, output_dir = folder_paths.get_input_directory(), folder_paths.get_output_directory()
        files = folder_paths.filter_files_content_types(os.listdir(input_dir), ["image"])
        
        directories = ["[INPUT]", "[OUTPUT]"]
        for base, prefix in [(input_dir, ""), (output_dir, "")]:
            directories.extend(
                rel_path.replace(os.sep, "/")
                for dirpath, dirnames, _ in os.walk(base)
                for dirname in dirnames
                if (rel_path := os.path.relpath(os.path.join(dirpath, dirname), base)) != "."
            )
        
        return {
            "required": {
                "directory": (sorted(set(directories)), {"default": "[INPUT]"}),
                "mode": (["Random", "Filename"], {"default": "Filename"}),
                "filename": (sorted(files), {"image_upload": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load_image"
    CATEGORY = "image"
    OUTPUT_NODE = True

    def load_image(self, directory, mode, filename):
        """Load and process an image based on directory, mode, and filename."""
        # Resolve directory path
        input_dir, output_dir = folder_paths.get_input_directory(), folder_paths.get_output_directory()
        full_dir_path, subfolder = self._get_dir_path(directory, input_dir, output_dir)
        
        if not os.path.exists(full_dir_path):
            raise FileNotFoundError(f"Directory not found: {full_dir_path}")
        
        # Get and validate image files
        image_files = [f for f in os.listdir(full_dir_path) if f.lower().endswith(self.IMAGE_EXTENSIONS)]
        if not image_files:
            raise FileNotFoundError(f"No valid image files found in: {full_dir_path}")
        
        # Select image
        selected_file = random.choice(image_files) if mode == "Random" else self._validate_filename(filename, image_files, full_dir_path)
        
        # Load and process image
        img = ImageOps.exif_transpose(Image.open(os.path.join(full_dir_path, selected_file)))
        image_tensor, mask = self._process_image(img)
        
        # Determine image type for UI
        image_type = "input" if full_dir_path.startswith(input_dir) else "output"
        
        return {
            "ui": {"images": [{"filename": selected_file, "subfolder": subfolder, "type": image_type}]},
            "result": (image_tensor, mask)
        }

    def _get_dir_path(self, directory, input_dir, output_dir):
        """Resolve directory path and subfolder based on input."""
        if directory == "[INPUT]":
            return input_dir, ""
        if directory == "[OUTPUT]":
            return output_dir, ""
        path = os.path.join(input_dir, directory) if os.path.exists(os.path.join(input_dir, directory)) else os.path.join(output_dir, directory)
        return path, directory

    def _validate_filename(self, filename, image_files, dir_path):
        """Validate filename for Filename mode."""
        if not filename:
            raise ValueError("Filename must be specified in Filename mode.")
        if filename not in image_files:
            raise FileNotFoundError(f"File '{filename}' not found in: {dir_path}")
        return filename

    def _process_image(self, img):
        """Convert image to tensor and create mask."""
        w, h = img.size
        image = img.convert("RGB")
        if img.mode == 'I':
            image = img.point(lambda i: i * (1 / 255))
        
        image_np = np.array(image).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_np)[None,]
        
        if 'A' in img.getbands() or (img.mode == 'P' and 'transparency' in img.info):
            mask = np.array(img.convert('RGBA').getchannel('A')).astype(np.float32) / 255.0
            mask = 1. - torch.from_numpy(mask)
        else:
            mask = torch.zeros((w, h), dtype=torch.float32, device="cpu")
        
        return image_tensor, mask.unsqueeze(0)

    @classmethod
    def IS_CHANGED(cls, directory, mode, filename):
        """Check if the node needs to be re-executed based on file or directory changes."""
        full_dir_path = cls._resolve_dir_path(directory)
        if not os.path.exists(full_dir_path):
            return True
        
        image_files = [f for f in os.listdir(full_dir_path) if f.lower().endswith(cls.IMAGE_EXTENSIONS)]
        if mode == "Filename" and filename not in image_files:
            return True
        if mode == "Filename":
            with open(os.path.join(full_dir_path, filename), 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        return random.random()

    @classmethod
    def VALIDATE_INPUTS(cls, directory, mode, filename):
        """Validate inputs before execution."""
        full_dir_path = cls._resolve_dir_path(directory)
        if not os.path.exists(full_dir_path):
            return f"Directory not found: {full_dir_path}"
        if mode == "Filename":
            image_files = [f for f in os.listdir(full_dir_path) if f.lower().endswith(cls.IMAGE_EXTENSIONS)]
            if not filename:
                return "Filename must be specified in Filename mode."
            if filename not in image_files:
                return f"File '{filename}' not found in: {full_dir_path}"
        return True

    @staticmethod
    def _resolve_dir_path(directory):
        """Resolve directory path for validation and change detection."""
        input_dir, output_dir = folder_paths.get_input_directory(), folder_paths.get_output_directory()
        if directory == "[INPUT]":
            return input_dir
        if directory == "[OUTPUT]":
            return output_dir
        return os.path.join(input_dir, directory) if os.path.exists(os.path.join(input_dir, directory)) else os.path.join(output_dir, directory)

@server.PromptServer.instance.routes.get("/ril/get_directories")
async def get_directories(_):
    """API endpoint to fetch available directories."""
    try:
        directories = ["[INPUT]", "[OUTPUT]"]
        for base in [folder_paths.get_input_directory(), folder_paths.get_output_directory()]:
            directories.extend(
                rel_path.replace(os.sep, "/")
                for dirpath, dirnames, _ in os.walk(base)
                for dirname in dirnames
                if (rel_path := os.path.relpath(os.path.join(dirpath, dirname), base)) != "."
            )
        return web.json_response(sorted(set(directories)))
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

@server.PromptServer.instance.routes.post("/ril/ensure_input_preview")
async def ensure_input_preview(request):
    """Ensure a copy of the selected image exists in INPUT root for preview.

    If the selected image is already in INPUT root, no action is taken.
    Otherwise, copy it to INPUT root using the same filename if not present.
    """
    try:
        data = await request.json()
        filename = data.get("filename", "")
        subfolder = data.get("subfolder", "")
        image_type = data.get("type", "input")

        if not filename:
            return web.json_response({"error": "Missing filename"}, status=400)

        input_dir = folder_paths.get_input_directory()
        output_dir = folder_paths.get_output_directory()

        # Determine source path
        if image_type == "input":
            src_dir = os.path.join(input_dir, subfolder) if subfolder else input_dir
        else:
            src_dir = os.path.join(output_dir, subfolder) if subfolder else output_dir

        src_path = os.path.join(src_dir, filename)
        if not os.path.exists(src_path):
            return web.json_response({"error": f"Source file not found: {src_path}"}, status=404)

        # Destination is always INPUT root
        dest_path = os.path.join(input_dir, filename)

        created = False
        if not os.path.exists(dest_path):
            # Copy file to INPUT root with the same name
            shutil.copy2(src_path, dest_path)
            created = True

        return web.json_response({
            "filename": filename,
            "created": created
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

@server.PromptServer.instance.routes.get("/ril/get_filenames")
async def get_filenames(request):
    """API endpoint to fetch image filenames in a directory."""
    directory = request.query.get("directory", "")
    try:
        input_dir, output_dir = folder_paths.get_input_directory(), folder_paths.get_output_directory()
        # Resolve full path, subfolder and image type (input/output)
        if directory == "[INPUT]":
            full_path = input_dir
            subfolder = ""
            image_type = "input"
        elif directory == "[OUTPUT]":
            full_path = output_dir
            subfolder = ""
            image_type = "output"
        else:
            input_try = os.path.join(input_dir, directory)
            if os.path.exists(input_try):
                full_path = input_try
                subfolder = directory
                image_type = "input"
            else:
                full_path = os.path.join(output_dir, directory)
                subfolder = directory
                image_type = "output"
        
        if not os.path.exists(full_path):
            return web.json_response({"error": f"Directory not found: {full_path}"}, status=404)
        
        image_files = [f for f in os.listdir(full_path) if f.lower().endswith(ImageLoaderEnhanced.IMAGE_EXTENSIONS)]
        return web.json_response({
            "filenames": sorted(image_files),
            "subfolder": subfolder,
            "type": image_type
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)