class SplitTextByTokens:
    """
    A ComfyUI node that splits input text into a list of strings, each not exceeding a maximum number of tokens
    using a CLIP tokenizer. Outputs a Python list of strings. Requires a CLIP input for the tokenizer.
    """
    @classmethod
    def INPUT_TYPES(cls) -> dict:
        """Defines input types for the node."""
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": ""}),
                "max_tokens_per_chunk": ("INT", {"default": 77, "min": 1, "max": 308, "step": 1, "display": "number"}),
            }
        }

    RETURN_TYPES = ("LIST",)
    RETURN_NAMES = ("string_list",)
    FUNCTION = "split_text"
    CATEGORY = "utils/text"

    @classmethod
    def IS_CHANGED(cls, text: str, max_tokens_per_chunk: int) -> float:
        """Forces node re-execution if inputs change."""
        return float("nan") if text or max_tokens_per_chunk else 0.0

    def split_text(self, text: str, max_tokens_per_chunk: int) -> tuple[list[str]]:
        """
        Splits text into chunks based on token count.

        Args:
            text: Input text to split.
            max_tokens_per_chunk: Maximum tokens per chunk (before BOS/EOS).

        Returns:
            Tuple containing the list of text chunks.
        """
        if not text or max_tokens_per_chunk <= 0:
            return ([],)

        # Split text into chunks and join with commas
        text_list: list[str] = text.split(", ")
        chunks: list[str] = [
            ", ".join(text_list[i:i + max_tokens_per_chunk])
            for i in range(0, len(text_list), max_tokens_per_chunk)
        ]
        return (chunks,)


class GetTextListByIndex:
    """
    A ComfyUI node that retrieves a string from a list by index. Outputs a single string.
    """
    @classmethod
    def INPUT_TYPES(cls) -> dict:
        """Defines input types for the node."""
        return {
            "required": {
                "text_list": ("LIST",),
                "index": ("INT", {"default": 0, "min": 0, "max": 20, "step": 1, "display": "number"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("string",)
    FUNCTION = "get_list"
    CATEGORY = "utils/text"

    def get_list(self, text_list: list[str], index: int) -> tuple[str]:
        """
        Retrieves a string from the list by index.

        Args:
            text_list: List of strings to select from.
            heartbeat: Heartbeat signal (not used in logic).
            index: Index of the string to retrieve.

        Returns:
            Tuple containing the selected string or empty string if index is invalid.
        """
        return ("",) if index >= len(text_list) else (text_list[index],)