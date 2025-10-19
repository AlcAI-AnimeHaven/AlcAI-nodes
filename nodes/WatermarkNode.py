import os
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

# Mocked helpers and constants (replace with actual imports)
class MockIcons:
    def get(self, key): return key
icons = MockIcons()
COLORS = ["white", "black", "red", "green", "blue", "yellow", "cyan", "magenta", "orange", "purple", "pink", "brown", "gray", "light_gray", "dark_gray"]
color_mapping = {
    "white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0), "green": (0, 255, 0),
    "blue": (0, 0, 255), "yellow": (255, 255, 0), "cyan": (0, 255, 255), "magenta": (255, 0, 255),
    "orange": (255, 165, 0), "purple": (128, 0, 128), "pink": (255, 192, 203),
    "brown": (165, 42, 42), "gray": (128, 128, 128), "light_gray": (211, 211, 211), "dark_gray": (169, 169, 169)
}

def tensor2pil(image_tensor):
    """Convert torch tensor to PIL Image."""
    if image_tensor.ndim == 4: image_tensor = image_tensor[0]
    return Image.fromarray((image_tensor.cpu().numpy() * 255).astype(np.uint8), 'RGB')

def reduce_opacity(img, opacity):
    """Reduce image opacity."""
    if img.mode != 'RGBA': img = img.convert('RGBA')
    alpha = img.split()[3].point(lambda p: p * opacity)
    img.putalpha(alpha)
    return img

def get_color_values(color_name, color_hex, mapping):
    """Get RGB tuple from color name or hex."""
    if color_name != "Hex": return mapping.get(color_name, (0, 0, 0))
    try:
        hex_color = color_hex.lstrip('#')
        if len(hex_color) in (6, 8): return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        if len(hex_color) == 3: return tuple(int(c*2, 16) for c in hex_color)
        print(f"Warning: Invalid hex color {color_hex}. Using black.")
    except ValueError:
        print(f"Warning: Could not parse hex color {color_hex}. Using black.")
    return (0, 0, 0)

class CustomWatermarkMaker:
    """A ComfyUI node to overlay text watermarks on images with customizable alignment, font, and outline."""

    @classmethod
    def INPUT_TYPES(cls):
        """Define input types for the node."""
        font_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "fonts")
        file_list = [f for f in os.listdir(font_dir) if f.lower().endswith((".ttf", ".otf"))] if os.path.isdir(font_dir) else ["default"]
        ALIGN_OPTIONS = ["center", "top left", "top center", "top right", "bottom left", "bottom center", "bottom right"]
        return {
            "required": {
                "image": ("IMAGE",),
                "text": ("STRING", {"multiline": False, "default": "@AlcAIHaven"}),
                "align": (ALIGN_OPTIONS, {"default": ALIGN_OPTIONS[4]}),
                "opacity": ("FLOAT", {"default": 1, "min": 0.0, "max": 1.0, "step": 0.01}),
                "font_name": (file_list, {"default": file_list[1] if len(file_list) > 1 else file_list[0]}),
                "font_size": ("INT", {"default": 50, "min": 1, "max": 1024}),
                "font_color": (["Hex"] + COLORS,),
                "outline_width": ("INT", {"default": 4, "min": 0, "max": 100, "step": 1}),
                "outline_color": (["Hex"] + COLORS,),
                "x_margin": ("INT", {"default": 20, "min": -1024, "max": 1024}),
                "y_margin": ("INT", {"default": 20, "min": -1024, "max": 1024}),
            },
            "optional": {
                "font_color_hex": ("STRING", {"multiline": False, "default": "#FFFFFF"}),
                "outline_color_hex": ("STRING", {"multiline": False, "default": "#000000"}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("IMAGE",)
    FUNCTION = "overlay_text"
    CATEGORY = "generation_utils/image_composer"

    def overlay_text(self, image, text, align, font_name, font_size, font_color, opacity, outline_width, 
                     outline_color, x_margin, y_margin, font_color_hex="#FFFFFF", outline_color_hex="#000000"):
        """Overlay text on an image with specified alignment, font, opacity, and outline.

        Args:
            image (torch.Tensor): Input image tensor.
            text (str): Watermark text.
            align (str): Text alignment option.
            font_name (str): Font file name.
            font_size (int): Font size in pixels.
            font_color (str): Color name or "Hex".
            opacity (float): Text opacity (0.0 to 1.0).
            outline_width (int): Outline stroke width.
            outline_color (str): Outline color name or "Hex".
            x_margin (int): Horizontal margin in pixels.
            y_margin (int): Vertical margin in pixels.
            font_color_hex (str): Hex color code for text.
            outline_color_hex (str): Hex color code for outline.

        Returns:
            tuple: A single-element tuple containing the output image tensor.
        """
        # Get RGBA colors
        text_color_rgba = get_color_values(font_color, font_color_hex, color_mapping) + (255,)
        outline_color_rgba = get_color_values(outline_color, outline_color_hex, color_mapping) + (255,)

        # Load font
        font_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "fonts")
        font_path = os.path.join(font_dir, font_name)
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        total_images = []
        for img_tensor in image:
            img_pil = tensor2pil(img_tensor)
            draw = ImageDraw.Draw(textlayer := Image.new("RGBA", img_pil.size, (0, 0, 0, 0)))

            # Calculate text bounding box
            try:
                bbox = draw.textbbox((0, 0), text, font=font, stroke_width=outline_width)
                text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                offset_x, offset_y = bbox[0], bbox[1]
            except AttributeError:
                ascent, descent = font.getmetrics()
                text_width, text_height = font.getlength(text), ascent + descent
                offset_x, offset_y = 0, 0

            # Determine text position
            img_width, img_height = img_pil.size
            x, y = {
                "center": ((img_width - text_width) // 2, (img_height - text_height) // 2),
                "top left": (x_margin, y_margin),
                "top center": ((img_width - text_width) // 2, y_margin),
                "top right": (img_width - text_width - x_margin, y_margin),
                "bottom left": (x_margin, img_height - text_height - y_margin),
                "bottom center": ((img_width - text_width) // 2, img_height - text_height - y_margin),
                "bottom right": (img_width - text_width - x_margin, img_height - text_height - y_margin)
            }.get(align, ((img_width - text_width) // 2, (img_height - text_height) // 2))

            # Draw text with outline
            draw.text((x - offset_x, y - offset_y), text, font=font, fill=text_color_rgba, 
                     stroke_width=outline_width, stroke_fill=outline_color_rgba)

            # Apply opacity and composite
            if opacity < 1.0: textlayer = reduce_opacity(textlayer, opacity)
            out_image_pil = Image.alpha_composite(img_pil.convert("RGBA"), textlayer).convert("RGB")
            total_images.append(torch.from_numpy(np.array(out_image_pil).astype(np.float32) / 255.0).unsqueeze(0))

        return (torch.cat(total_images, 0) if total_images else torch.empty((0, 1, 1, 3)),)