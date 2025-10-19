# --- START OF FILE ModelInfoSelector.py ---

import os
import folder_paths

class ModelInfoSelector:
    """
    A custom node that provides a dropdown to select a checkpoint model
    and outputs its filename (compatible with CheckpointLoader)
    and its base name (without extension).
    """
    # Define categories for the node menu
    CATEGORY = "utils/paths" # You can change "utils/paths" to your preferred category

    # Define input types using a class method
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # This creates a dropdown widget populated with checkpoint filenames
                # We use 'ckpt_name' here to be consistent with CheckpointLoader input
                "ckpt_name": (folder_paths.get_filename_list("checkpoints"), ),
            }
        }

    # Define the return types and their names
    # Output 1: The filename string, suitable for CheckpointLoader's 'ckpt_name' input
    # Output 2: The base model name (without path and extension) as a string
    RETURN_TYPES = (folder_paths.get_filename_list("checkpoints"), "STRING")
    RETURN_NAMES = ("ckpt_name", "base_model_name") # Renamed for clarity

    # Define the main function of the node
    FUNCTION = "get_model_info" # Renamed function for clarity

    # This node provides data for other nodes
    OUTPUT_NODE = False

    def get_model_info(self, ckpt_name):
        """
        Retrieves the filename for the selected model and its base name.
        """
        # The 'ckpt_name' input variable already holds the exact filename string
        # that the CheckpointLoader node requires. We just need to pass it through.
        selected_filename = ckpt_name
        selected_filename = folder_paths.get_full_path_or_raise("checkpoints", selected_filename)

        # Calculate the base name without the extension
        # os.path.splitext splits "model.safetensors" into ("model", ".safetensors")
        # We take the first part.
        base_model_name, _ = os.path.splitext(selected_filename)
        base_model_name = base_model_name.split("\\")[-1]

        # Return the full filename (for CheckpointLoader) and the base name
        return (selected_filename, base_model_name)