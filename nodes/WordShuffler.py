import re
import random

class WordShuffler:
    """A ComfyUI node to shuffle word order in a string. Words are split by spaces or commas."""
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input types for the node."""
        return {
            "required": {
                "text": ("STRING", {"multiline": False, "default": ""}),
                "shuffle": ("BOOLEAN", {"default": False, "label_on": "True", "label_off": "False"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("shuffled_text",)
    FUNCTION = "shuffle_words"
    CATEGORY = "utils/text"

    @classmethod
    def IS_CHANGED(cls, text, shuffle):
        """Return NaN if text is non-empty and shuffle is True to indicate potential change."""
        return float("nan") if text and shuffle else None

    def shuffle_words(self, text, shuffle):
        """Shuffle words in the input text if shuffle is True, else return original text.
        
        Args:
            text (str): Input text to process.
            shuffle (bool): Whether to shuffle the words.
        
        Returns:
            tuple: A single-element tuple containing the processed text.
        """
        if not text or not shuffle:
            return (text,)
        
        # Split by ", " or multiple spaces, filter out empty strings, shuffle, and join
        words = [w for w in re.split(r'\s*,\s*|\s+', text.strip()) if w]
        random.shuffle(words)
        return (", ".join(words),)