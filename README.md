# ComfyUI JSON / Dict Tools

JSON & Dictionary Utilities for Workflow Orchestration
A collection of Python-based modular components designed to streamline data manipulation within graph-based workflow engines. These tools focus on high-efficiency parsing, nested dictionary traversal, and data-type normalization for complex automated pipelines.

## Nodes Included

### 1. JSON / Dict Loader
Loads structured data from a file path or raw text.
- **Inputs**: 
  - `string_file_input`: Provide a file path (e.g., `C:\data.json`) or paste valid JSON/Python dict text.
  - `convert_input_to_dict`: Wraps lists in a dictionary (e.g., `[1,2,3]` becomes `{"data":[1,2,3]}`).
  - `refresh_on_run`: Ensures the file is re-read from disk every time you queue a prompt.
- **Outputs**:
  - `output`: Returns a dictionary or formatted JSON text.

### 2. JSON / Dict Key Extractor
A minimalist "Swiss Army Knife" for drilling into your data.
- **Inputs**:
  - `json_data`: The source dictionary or list.
  - `key`: The primary path to extract (supports dot notation like `user.profile.id`). Can be converted to an input dot for dynamic keys.
  - `fuzzy_match`: When enabled, if an exact dictionary-key match fails, it falls back to a case-insensitive key comparison. It does not do partial, alias, basename, or token matching.
  - `path_extension` (Optional): Appended to the `key`. Useful when `key` is a dynamic input but you still want to type a specific sub-path.
- **Outputs**:
  - `value`: The extracted value.

### 3. JSON / Dict Exploder
Explodes a dictionary into individual outputs based on its top-level keys. Perfect for breaking apart config files or routing multiple settings.
- **Inputs**:
  - `json_dict_data_1` *(Dynamic)*: Connect one or more dictionaries. As you connect a wire to the last available slot, a new empty slot will automatically appear. 
- **Outputs**: 
  - *(Dynamic)*: Outputs are automatically generated and named based on the top-level keys of your dictionary data.
- **Features**:
  - **Dictionary Merging**: If you plug in multiple dictionaries, the node merges them sequentially. If there are colliding keys, the data in the lower inputs will overwrite the higher ones.
  - **"Run to Update"**: Because ComfyUI only reads data during execution, this node spawns with a single output labeled `run_to_update...`. Simply plug your data in, hit "Run workflow / Queue Prompt", and watch the node magically expand and rename its slots to match your keys! (This state is saved in your workflow, so you only have to do it once).

## Pro Tips & Examples

### Dot Notation & Lists
You can reach deep into nested data and lists in one go using the Extractor:
- Path: `results.0.metadata.tags.1`
- This gets the 2nd tag from the metadata of the 1st result.

### Keys with Dots (Quoted Keys)
If your dictionary keys contain dots (like filenames), wrap that segment in quotes:
- Path: `"sd1.5.model".recommended.cfg`
- This treats `sd1.5.model` as a single key instead of splitting it.

### Dynamic Key + Path Extension
Let's say you have a dynamic input connected to your **Key** input:
1. The extractor first tries an exact key match against the current dictionary level.
2. If **`fuzzy_match`** is enabled, it then tries a case-insensitive key match.
3. Use **`path_extension`** to type something like `recommended.cfg` when you want to keep drilling into the matched object.

## CLI Testing

You can test the extractor without loading ComfyUI.

Example:

```bash
python examples/extractor_cli.py \
  --json-file "..\\models\\configs\\thrakks_model_configs.json" \
  --key "sdxl\\oneObsessionBranch_v7Matureeps.safetensors" \
  --path-extension "recommended.vae" \
  --fuzzy-match
```

The script prints both:
- `matched_against`: how the extractor resolved the key
- `value`: the extracted result

For a key like `sd1.5\\disneyPixarCartoon_v10.safetensors`, Python string escaping only matters in Python source code. Once the string reaches the node, it is compared directly against dictionary keys exactly as provided.

## Installation

1. Navigate to your ComfyUI `custom_nodes` folder.
2. Clone or download this repository into a folder named `ComfyUI-JSON-Tools`.
3. Restart ComfyUI.

## Requirements
- No external dependencies required (uses standard Python libraries).
- Fully compatible with both the Classic (V1) and Modern (V2) ComfyUI canvases.