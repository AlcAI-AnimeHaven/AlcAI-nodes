# --- START OF FILE __init__.py ---
import importlib # Import the importlib module
import traceback # Import traceback for more detailed error information
import os # Import os to check for nodes/__init__.py

# Get the directory of the current __init__.py file
package_dir = os.path.dirname(__file__)
nodes_dir = os.path.join(package_dir, "nodes")
nodes_init_file = os.path.join(nodes_dir, "__init__.py")

# Check if nodes directory exists and has __init__.py
if not os.path.isdir(nodes_dir):
    print(f"⚠️   Warning: 'nodes' directory not found in {package_dir}. Cannot load nodes.")
    nodes_to_load = [] # Skip loading if directory doesn't exist
elif not os.path.isfile(nodes_init_file):
    print(f"⚠️   Warning: Missing __init__.py in '{nodes_dir}'. Relative imports might fail.")
    print(f"      Please create an empty file named __init__.py inside the 'nodes' directory.")
    # Depending on Python version/environment, imports might still fail later.
    # You could choose to set nodes_to_load = [] here too if you want to be strict.

# Initialize empty dictionaries and counter
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
loaded_nodes_count = 0
attempted_nodes_count = 0

# List of node information: (class_name, module_subpath, display_name)
# module_subpath is relative to the 'nodes' directory
nodes_to_load = [
    ("AnimeCharacterSelector", ".nodes.AnimeCharacterSelector", "Anime Character Selector (API)"),
    ("BooruImageLoader", ".nodes.BooruImageLoader", "Load Image from Booru"),
    ("ImageLoaderEnhanced", ".nodes.ImageLoaderEnhanced", "Load Image Enhanced"),
    ("WordShuffler", ".nodes.WordShuffler", "Text/String Shuffler"),
    ("LogicGatesForBoolean", ".nodes.LogicGates", "Logic Gate (BOOLEAN)"),
    ("LogicGateForAnyValue", ".nodes.LogicGates", "Logic Gate (ANY)"),
    ("LogicGateSwitchForAnyValue", ".nodes.LogicGates", "Logic Gate (SWITCH ANY)"),
    ("SplitTextByTokens", ".nodes.BatchTokenizeText", "Tokenize Text (batch)"),
    ("GetTextListByIndex", ".nodes.BatchTokenizeText", "Get Text by Index"),
    ("RandomResSDXL", ".nodes.RandomResSDXL", "SDXL Random Latent Resolution"),
    ("ModelInfoSelector", ".nodes.ModelInfoSelector", "Checkpoint Model Selector"),
    ("CustomWatermarkMaker", ".nodes.WatermarkNode", "Custom Watermark Writer"),
    ("LoraNameSelector", ".nodes.LoraNameSelector", "Lora Name Selector"),
    ("LoraLoaderAndKeywords", ".nodes.CustomLoraLoader", "Load Lora with Keywords"),
    # Add more nodes here in the same format if needed
]

print("\n   --- Loading AlcAI Custom Nodes ---   \n")

# Iterate through the list and try to import/map each node
for class_name, import_path, display_name in nodes_to_load:
    attempted_nodes_count += 1
    try:
        # Use importlib for dynamic relative import
        # The 'package=__package__' argument is crucial for relative imports
        # It tells import_module *relative to which package* it should resolve the dot '.'
        module = importlib.import_module(import_path, package=__package__)

        # Get the class from the imported module
        node_class = getattr(module, class_name)

        # Add to mappings if successful
        NODE_CLASS_MAPPINGS[class_name] = node_class
        NODE_DISPLAY_NAME_MAPPINGS[class_name] = display_name

        # Increment the counter for successfully loaded nodes
        loaded_nodes_count += 1
        if loaded_nodes_count == 0 or loaded_nodes_count == 1:
            print("\n")
        print(f"  ✅     Node loaded: {class_name}")

    except ImportError as e:
        print(f"  ❌     ImportError: Failed to import {class_name} from '{import_path}'. Check file/path existence, dependencies, and presence of 'nodes/__init__.py'. Error: {e}")
        # print(f"      (Looking relative to package: {__package__})") # Uncomment for debugging package context
    except AttributeError as e:
         print(f"  ❌     AttributeError: Failed to find class '{class_name}' within module '{import_path}'. Check class name spelling in the Python file and in this list. Error: {e}")
    except Exception as e:
        print(f"  ❌     Unexpected Error loading {class_name}: {str(e)}")
        # Optionally print full traceback for debugging
        traceback.print_exc()

WEB_DIRECTORY = "./web/extensions"

# Export them so ComfyUI can discover them
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

print("\n-----------------------------------------------------------------------------")
# Use the counter in the final print message
if attempted_nodes_count > 0:
    print(f"  ✅   AlcAI NODES: {loaded_nodes_count} / {attempted_nodes_count} Custom Node(s) Loaded!")
    if loaded_nodes_count < attempted_nodes_count:
         print(f"  ⚠️   Note: {attempted_nodes_count - loaded_nodes_count} node(s) failed to load. See errors above.")
else:
    print("  ❌   AlcAI NODES: No nodes were attempted to load (check 'nodes' directory and __init__.py).")
print("-----------------------------------------------------------------------------\n")
# --- END OF FILE __init__.py ---