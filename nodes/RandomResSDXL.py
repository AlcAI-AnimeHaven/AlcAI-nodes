import torch
import random
import math
from fractions import Fraction
from typing import Tuple

class RandomResSDXL:
    """
    Computes the aspect ratio of an image and generates random dimensions (width, height)
    that preserve the ratio, stay within a pixel range, and are multiples of a step.
    """
    @classmethod
    def INPUT_TYPES(cls) -> dict:
        """Defines input types for the node."""
        return {
            "required": {
                "image": ("IMAGE",),
                "ratio_mode": (["Any", "Image", "Portrait", "Landscape"], {"default": "Any"}),
                "min_total_pixels": ("INT", {"default": 1024*1024, "min": 1024*1024, "max": 1536*1536, "step": 64*64, "display": "number"}),
                "max_total_pixels": ("INT", {"default": 1536*1536, "min": 1280*1280, "max": 2048*2048, "step": 64*64, "display": "number"}),
                "step_multiple": ("INT", {"default": 8, "min": 1, "max": 64, "step": 1, "display": "number"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "STRING")
    RETURN_NAMES = ("width", "height", "aspect_ratio")
    FUNCTION = "calculate_random_dimensions"
    CATEGORY = "utils"

    def calculate_random_dimensions(self, image: torch.Tensor, ratio_mode: str, min_total_pixels: int, max_total_pixels: int, step_multiple: int, seed: int) -> Tuple[int, int, str]:
        """
        Generates random dimensions preserving the input image's aspect ratio.

        Args:
            image: Input image tensor (Batch, Height, Width, Channels).
            min_total_pixels: Minimum total pixels for the output dimensions.
            max_total_pixels: Maximum total pixels for the output dimensions.
            step_multiple: Step size for dimension rounding (e.g., 8 or 64 for SDXL).
            seed: Random seed for reproducibility.

        Returns:
            Tuple of (width, height, aspect_ratio_str) with rounded dimensions and simplified aspect ratio.
        """
        # Ensure min_total_pixels <= max_total_pixels
        min_total_pixels = min(min_total_pixels, max_total_pixels)

        # Get input dimensions
        _, height_in, width_in, _ = image.shape
        if height_in == 0 or width_in == 0:
            print(f"[ERROR] RandomResSDXL: Invalid dimensions ({width_in}x{height_in}). Returning defaults.")
            return (512, 512, "1/1")

        # Calculate and simplify aspect ratio
        aspect_ratio: float = width_in / height_in
        simplified_ratio: Fraction = Fraction(aspect_ratio).limit_denominator(100)
        aspect_ratio_str: str = f"{simplified_ratio.numerator}/{simplified_ratio.denominator}"

        # Set random seed and choose target area
        random.seed(seed)
        target_area: float = random.uniform(min_total_pixels, max_total_pixels)

        # Calculate ideal dimensions
        ideal_height: float = math.sqrt(target_area / aspect_ratio)
        ideal_width: float = aspect_ratio * ideal_height

        # Round width and height to nearest step_multiple
        new_width: int = max(step_multiple, round(ideal_width / step_multiple) * step_multiple)
        new_height: int = max(step_multiple, round((new_width / aspect_ratio) / step_multiple) * step_multiple)


        # Log details
        print(f"[INFO] RandomResSDXL: Input: {width_in}x{height_in} (AR: {aspect_ratio:.4f}), Target Area: {target_area:.0f}px")
        print(f"[INFO] RandomResSDXL: Output: {new_width}x{new_height} w/ ratio: {ratio_mode}, Area: {new_width*new_height}px)")

        # Get the larger and smaller of the two dimensions
        long_side = max(new_width, new_height)
        short_side = min(new_width, new_height)

        if ratio_mode == "Any":
            # This handles the "Any" case
            choices = [(new_width, new_height), (new_height, new_width)]
            final_width, final_height = random.choice(choices)
            print(f"[INFO] RandomResSDXL: {ratio_mode} output, resolution: {final_width}x{final_height}")
        elif ratio_mode == "Image":
            # For image, width should be the longer side
            final_width = new_width
            final_height = new_height
            print(f"[INFO] RandomResSDXL: {ratio_mode} output, resolution: {new_width}x{new_height} -> {final_width}x{final_height}")
        elif ratio_mode == "Landscape":
            # For landscape, width should be the longer side
            final_width = long_side
            final_height = short_side
            print(f"[INFO] RandomResSDXL: {ratio_mode} output, resolution: {new_width}x{new_height} -> {final_width}x{final_height}")
        elif ratio_mode == "Portrait":
            # For portrait, height should be the longer side
            final_width = short_side
            final_height = long_side
            print(f"[INFO] RandomResSDXL: {ratio_mode} output, resolution: {new_width}x{new_height} -> {final_height}x{final_width}")



        return (final_width, final_height, aspect_ratio_str)

# Node registration
NODE_CLASS_MAPPINGS = {"RandomResSDXL": RandomResSDXL}
NODE_DISPLAY_NAME_MAPPINGS = {"RandomResSDXL": "Random Res From Aspect Ratio (SDXL)"}