"""
AlcAI Custom Nodes Package
=========================

This package dynamically loads and registers custom nodes for AlcAI workflows, 
optimized for anime generation and AI pipelines (e.g., integration with ComfyUI).

Key Components:
- NODE_CLASS_MAPPINGS: Maps node class names to their classes.
- NODE_DISPLAY_NAME_MAPPINGS: Maps node class names to user-friendly display names.
- WEB_DIRECTORY: Path for web extensions (e.g., UI assets).

The loading process checks for the 'nodes' directory, attempts to import each node module,
and reports success/failure counts. Failed loads are logged with specific error details.

Author: AlcAI-AnimeHaven
Version: 1.0.0

Usage:
    # In ComfyUI or similar: Import this module to auto-register nodes
    from alcai_nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

For adding nodes: Append to the `nodes_to_load` list in the format (class_name, module_subpath, display_name).
Ensure each node module is in the 'nodes' subdirectory with proper __init__.py.
"""

__version__ = "1.0.0"
__author__ = "AlcAI-AnimeHaven"

import importlib  # For dynamic module imports
import traceback  # For detailed error tracebacks in exceptions
import os  # For directory and file path operations

# Determine package paths
package_dir = os.path.dirname(__file__)  # Root directory of this package
nodes_dir = os.path.join(package_dir, "nodes")  # Subdirectory for node modules
nodes_init_file = os.path.join(nodes_dir, "__init__.py")  # Required init file for relative imports

# Validate nodes directory structure
if not os.path.isdir(nodes_dir):
    print(f"⚠️   Warning: 'nodes' directory not found in {package_dir}. Skipping node loads.")
    nodes_to_load = []  # No nodes to attempt loading
elif not os.path.isfile(nodes_init_file):
    print(f"⚠️   Warning: Missing __init__.py in '{nodes_dir}'. Relative imports may fail.")
    print(f"      Tip: Create an empty __init__.py file in the 'nodes' directory.")
    # Proceed with loads, but imports may still error later

# Global mappings for ComfyUI-style node registration
NODE_CLASS_MAPPINGS = {}  # {class_name: node_class}
NODE_DISPLAY_NAME_MAPPINGS = {}  # {class_name: display_name}

# Counters for load summary
loaded_nodes_count = 0
attempted_nodes_count = 0

# Node registry: (class_name, relative_module_path, display_name)
# - class_name: The class to extract from the module.
# - relative_module_path: Dot-separated path from 'nodes' (e.g., '.subfolder.Module').
# - display_name: Human-readable name for UI display.
# Add new nodes here; ensure the module exports the class and handles dependencies.
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
    # Extend this list for additional nodes
]

print("\n   --- Loading AlcAI Custom Nodes ---   \n")

# Dynamically load and register each node
for class_name, import_path, display_name in nodes_to_load:
    attempted_nodes_count += 1
    try:
        # Perform relative import using the current package context
        # This resolves '.nodes.SubModule' relative to the package root
        module = importlib.import_module(import_path, package=__package__)
        
        # Extract the node class from the module
        node_class = getattr(module, class_name)
        
        # Register in global mappings
        NODE_CLASS_MAPPINGS[class_name] = node_class
        NODE_DISPLAY_NAME_MAPPINGS[class_name] = display_name
        
        loaded_nodes_count += 1
        print(f"  ✅     {class_name}: Loaded ({display_name})")
        
    except ImportError as e:
        print(f"  ❌     Import failed for {class_name} ({import_path}): {e}")
        print(f"         Check: File exists? Dependencies installed? 'nodes/__init__.py' present?")
    except AttributeError as e:
        print(f"  ❌     Class '{class_name}' not found in {import_path}: {e}")
        print(f"         Check: Class name matches in module? Exported correctly?")
    except Exception as e:
        print(f"  ❌     Unexpected error loading {class_name}: {e}")
        traceback.print_exc()  # Full traceback for debugging

# Web extensions directory (relative to package root)
WEB_DIRECTORY = "./web/extensions"

# Export public APIs for external discovery (e.g., by ComfyUI)
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

print("\n-----------------------------------------------------------------------------")
if attempted_nodes_count > 0:
    print(f"  ✅   AlcAI Nodes: {loaded_nodes_count}/{attempted_nodes_count} loaded successfully!")
    failed_count = attempted_nodes_count - loaded_nodes_count
    if failed_count > 0:
        print(f"  ⚠️   {failed_count} node(s) failed. Review errors above for details.")
else:
    print("  ❌   No nodes attempted: Verify 'nodes' directory and __init__.py.")
print("-----------------------------------------------------------------------------\n")