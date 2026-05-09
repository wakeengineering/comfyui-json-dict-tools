import ast
import json
import os

try:
    from server import PromptServer
except ImportError:
    class _PromptServerStub:
        def send_sync(self, *args, **kwargs):
            return None

    class PromptServer:
        instance = _PromptServerStub()

def parse_json_text(text):
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error at line {e.lineno}, col {e.colno}: {e.msg}"


def parse_python_literal_text(text):
    try:
        value = ast.literal_eval(text)
    except (SyntaxError, ValueError) as e:
        return None, f"Python literal parse error: {e}"

    if isinstance(value, (dict, list, tuple, str, int, float, bool)) or value is None:
        return value, None

    return None, f"Python literal parse error: unsupported value type {type(value).__name__}"


def parse_structured_text(text, source_label):
    parsed, json_error = parse_json_text(text)
    if json_error is None:
        return parsed, None

    parsed, literal_error = parse_python_literal_text(text)
    if literal_error is None:
        return parsed, None

    return None, f"{source_label}: {json_error} | {literal_error}"


def safe_json_string(value):
    try:
        return json.dumps(value, indent=2)
    except TypeError:
        return json.dumps({"value": str(value)}, indent=2)


def build_input_preview(value, max_length=120):
    if isinstance(value, str) and len(value) > max_length:
        return value[:max_length] + "..."
    return value


def raise_user_input_error(node_name, action, source_value, errors, default_reason, preview_label):
    reason = " | ".join(errors) if errors else default_reason
    preview = build_input_preview(source_value)
    raise ValueError(
        f"{node_name}: unable to {action}\n"
        f"Reason: {reason}\n"
        f"{preview_label}: {preview}"
    )


def resolve_dict_key(mapping, lookup_key, allow_case_insensitive=False):
    if not isinstance(mapping, dict):
        return None, ""

    if lookup_key in mapping:
        return mapping[lookup_key], f"exact key: {lookup_key}"

    if not allow_case_insensitive:
        return None, ""

    lookup_key_lower = str(lookup_key).lower()
    for dict_key, dict_value in mapping.items():
        if str(dict_key).lower() == lookup_key_lower:
            return dict_value, f"case-insensitive key: {dict_key}"

    return None, ""


def resolve_inverse_top_level_key(mapping, lookup_text):
    if not isinstance(mapping, dict):
        return None, ""

    lookup_text_lower = str(lookup_text).lower().strip()
    if not lookup_text_lower:
        return None, ""

    # Prefer the longest matching key so more-specific keys win.
    matching_keys = [k for k in mapping.keys() if str(k).lower() in lookup_text_lower]
    if not matching_keys:
        return None, ""

    best_key = sorted(matching_keys, key=lambda k: (-len(str(k)), str(k).lower()))[0]
    return mapping[best_key], f"inverse key: {best_key}"


def looks_like_path(text):
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if os.path.isabs(stripped):
        return True
    if stripped.endswith(".json"):
        return True
    return ("/" in stripped) or ("\\" in stripped)


def normalize_structured_input(value, source_label):
    if not isinstance(value, str):
        return value, None

    candidate = value.strip()
    if not candidate:
        return None, [f"{source_label}: input is empty."]

    if os.path.exists(candidate):
        try:
            with open(candidate, 'r', encoding='utf-8') as f:
                file_text = f.read()
        except OSError as e:
            return None, [f"{source_label}: file read error: {e}"]

        parsed, parse_error = parse_structured_text(file_text, f"{source_label} file")
        if parse_error:
            return None, [parse_error]
        return parsed, None

    parsed, parse_error = parse_structured_text(candidate, source_label)
    if parse_error:
        if looks_like_path(candidate):
            return None, [f"{source_label}: file path not found '{candidate}'. {parse_error}"]
        return None, [parse_error]

    return parsed, None


class JSONDICTLoaderNode:
    """
    ### JSON / Dict Loader
    This node loads structured data (JSON or Python dictionaries/lists) from either a **file path** or **raw text**.
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "string_file_input": ("STRING", {"multiline": True, "default": "C:\\Path\\To\\File\\data.json or {\"valid\": \"json\"} or {'valid': 'python'}", "tooltip": "Single text input. Provide a file path or paste valid JSON or Python dict/list literal text."}),
                "convert_input_to_dict": ("BOOLEAN", {"default": False, "tooltip": "If enabled, wraps non-dict parsed input in a dictionary. Real dict inputs always stay dictionaries."}),
                "refresh_on_run": ("BOOLEAN", {"default": True, "tooltip": "Bypasses ComfyUI caching to ensure the file is re-read from disk every time you queue a prompt."}),
            }
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("output",)
    FUNCTION = "load_json"
    CATEGORY = "JSON Tools"

    @classmethod
    def IS_CHANGED(cls, string_file_input, convert_input_to_dict, refresh_on_run):
        # When enabled, return NaN so ComfyUI always considers the node stale and re-executes it.
        # When disabled, return the input text so normal hash-based caching applies.
        if refresh_on_run:
            return float("nan")
        return string_file_input

    def load_json(self, string_file_input, convert_input_to_dict, refresh_on_run):
        data, errors = normalize_structured_input(string_file_input, "input")
        if errors:
            raise_user_input_error(
                "JSONDICTLoader",
                "load input",
                string_file_input,
                errors,
                "No readable file path or valid JSON input was provided.",
                "Source Preview",
            )

        if isinstance(data, dict):
            return (data,)

        if convert_input_to_dict:
            return ({"data": data},)

        return (safe_json_string(data),)

class JSONDICTExtractorNode:
    """
    ### JSON / Dict Key Extractor
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "json_data": ("*", {"tooltip": "Accepts a dictionary, list, JSON text, Python literal text, or a file path to structured data."}),
                "key": ("STRING", {"default": "", "tooltip": "Primary lookup text. Extractor uses top-level matching only: exact, case-insensitive, then inverse key-in-input match."}),
                "fuzzy_match": ("BOOLEAN", {"default": False, "tooltip": "Legacy compatibility toggle; retained for existing workflows."}),
            },
            "optional": {
                "path_extension": ("STRING", {"default": "", "tooltip": "Optional text appended to key with a dot before matching."}),
            }
        }

    RETURN_TYPES = ("*", "STRING")
    RETURN_NAMES = ("value", "matched_against")
    FUNCTION = "extract"
    CATEGORY = "JSON Tools"

    def extract(self, json_data, key, fuzzy_match=False, path_extension=""):
        normalized_data, errors = normalize_structured_input(json_data, "json_data")
        if errors:
            raise_user_input_error(
                "JSONDICTExtractor",
                "read input",
                json_data,
                errors,
                "No readable file path or valid structured input was provided.",
                "Input Preview",
            )

        matched_info = ""

        full_path = str(key).strip()
        ext = str(path_extension).strip()
        if full_path and ext:
            full_path = full_path.rstrip('.') + '.' + ext.lstrip('.')
        elif ext:
            full_path = ext

        if not full_path:
            return (normalized_data, matched_info)

        if isinstance(normalized_data, dict):
            resolved_value, matched_info = resolve_dict_key(
                normalized_data,
                full_path,
                allow_case_insensitive=True,
            )
            if matched_info:
                return (resolved_value, matched_info)

            resolved_value, matched_info = resolve_inverse_top_level_key(normalized_data, full_path)
            if matched_info:
                return (resolved_value, matched_info)

        # Dot-path traversal is intentionally disabled to avoid accidental nested
        # lookups when the key input is a file/model path-like string.
        return (None, matched_info)


class JSONDICTSelectorNode:
    """
    ### JSON / Dict Selector
    Select a single key from a dictionary and return its value.
    
    - **Dynamic Inputs**: Connect one or more dictionaries to merge them.
    - **Key Selection**: Use the key_selector to choose which value to return.
    - **Smart Validation**: Automatically detects available keys and provides helpful errors.
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "json_dict_data": ("*", {"tooltip": "The dictionary to select from."}),
                "key_selector": ("STRING", {"default": "", "tooltip": "Enter the key name to select from the provided dictionary. Available keys will be shown in error messages."}),
            },
            "optional": {
                "default_if_missing": ("*", {"default": None, "tooltip": "If key is not found, return this value instead of erroring."}),
            },
            "hidden": {
                # Used by frontend extension to update selector combo options after execution.
                "unique_id": "UNIQUE_ID",
            }
        }

    RETURN_TYPES = ("*", "STRING")
    RETURN_NAMES = ("value", "selected_key_info")
    FUNCTION = "select"
    CATEGORY = "JSON Tools"

    def select(self, json_dict_data, key_selector, default_if_missing=None, unique_id=-1):
        # Normalize the input
        normalized_data, errors = normalize_structured_input(json_dict_data, "json_dict_data")
        if errors:
            raise_user_input_error(
                "JSONDICTSelector",
                "read input",
                json_dict_data,
                errors,
                "No readable file path or valid structured input was provided.",
                "Input Preview",
            )

        # Ensure we have a dict
        if not isinstance(normalized_data, dict):
            PromptServer.instance.send_sync("JSONDICTSelector_keys", {
                "node_id": unique_id,
                "keys": [],
                "selected": "",
            })
            raise ValueError(
                f"JSONDICTSelector: expected a dictionary, got {type(normalized_data).__name__}\n"
                f"Available keys: (none - input is not a dict)"
            )

        available_keys_sorted = [str(k) for k in sorted(normalized_data.keys(), key=lambda x: str(x).lower())]

        # Trim the key selector
        key_selector = str(key_selector).strip()

        # If empty, return the whole dict
        if not key_selector:
            PromptServer.instance.send_sync("JSONDICTSelector_keys", {
                "node_id": unique_id,
                "keys": available_keys_sorted,
                "selected": "",
            })
            return (normalized_data, "No key selected - returning full dictionary")

        # Try exact match
        if key_selector in normalized_data:
            PromptServer.instance.send_sync("JSONDICTSelector_keys", {
                "node_id": unique_id,
                "keys": available_keys_sorted,
                "selected": key_selector,
            })
            return (normalized_data[key_selector], f"Selected key: {key_selector}")

        # Try case-insensitive match
        key_selector_lower = key_selector.lower()
        for existing_key in normalized_data.keys():
            if str(existing_key).lower() == key_selector_lower:
                PromptServer.instance.send_sync("JSONDICTSelector_keys", {
                    "node_id": unique_id,
                    "keys": available_keys_sorted,
                    "selected": str(existing_key),
                })
                return (normalized_data[existing_key], f"Selected key (case-insensitive): {existing_key}")

        # Key not found - handle with default or error
        PromptServer.instance.send_sync("JSONDICTSelector_keys", {
            "node_id": unique_id,
            "keys": available_keys_sorted,
            "selected": "",
        })
        available_keys = ", ".join(available_keys_sorted)
        error_msg = (
            f"JSONDICTSelector: key '{key_selector}' not found\n"
            f"Available keys: {available_keys}"
        )

        if default_if_missing is not None:
            return (default_if_missing, f"Key not found, returned default. Available: {available_keys}")

        raise ValueError(error_msg)


class JSONDICTExploderNode:
    """
    ### JSON / Dict Exploder
    Explodes a dictionary into individual outputs based on its top-level keys.
    
    - **Dynamic Inputs**: Connect multiple dictionaries to merge them.
    - **Dynamic Outputs**: Automatically maps top-level keys to named outputs.
    - **Real-time Renaming**: Outputs are renamed in the UI to match the keys.
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "json_dict_data_1": ("*", {"tooltip": "The primJary dictionary to explode."}),
            },
            "hidden": {
                # UNIQUE_ID is automatically populated by ComfyUI with the node's true ID 
                # strings without needing a physical UI widget.
                "unique_id": "UNIQUE_ID",
            }
        }

    # Define the 50 potential outputs statically so ComfyUI validation passes.
    RETURN_TYPES = ("*",) * 50
    RETURN_NAMES = tuple(f"output_{i+1}" for i in range(50))
    FUNCTION = "explode"
    CATEGORY = "JSON Tools"
    OUTPUT_NODE = True

    def explode(self, **kwargs):
        merged_dict = {}
        
        # 1. Merge all inputs sequentially
        # Sort keys to ensure 'json_dict_data_1' is merged before 'json_dict_data_2'
        input_keys = sorted([k for k in kwargs.keys() if k.startswith("json_dict_data")], 
            key=lambda x: int(x.split("_")[-1]) if "_" in x and x.split("_")[-1].isdigit() else 0
        )
        
        for k in input_keys:
            val = kwargs[k]
            normalized, _ = normalize_structured_input(val, k) # Assumes your existing helper
            if isinstance(normalized, dict):
                merged_dict.update(normalized)

        # 2. Extract top-level keys sorted alphabetically (limit to 50)
        keys = sorted(merged_dict.keys(), key=lambda x: str(x).lower())[:50]
        results = []
        for k in keys:
            results.append(merged_dict[k])
        
        # 3. Fill the remaining slots out of 50 with None
        for _ in range(len(results), 50):
            results.append(None)

        # 4. Send keys to the UI for dynamic renaming
        unique_id = kwargs.get("unique_id", -1)
        PromptServer.instance.send_sync("JSONDICTExploder_keys", {
            "node_id": unique_id,
            "keys": keys
        })

        return tuple(results)

NODE_CLASS_MAPPINGS = {
    "JSONDICTLoader": JSONDICTLoaderNode,
    "JSONDICTExtractor": JSONDICTExtractorNode,
    "JSONDICTSelector": JSONDICTSelectorNode,
    "JSONDICTExploder": JSONDICTExploderNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "JSONDICTLoader": "JSON / Dict Loader",
    "JSONDICTExtractor": "JSON / Dict Key Extractor",
    "JSONDICTSelector": "JSON / Dict Selector",
    "JSONDICTExploder": "JSON / Dict Exploder"
}