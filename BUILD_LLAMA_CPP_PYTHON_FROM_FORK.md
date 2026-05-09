# Building llama-cpp-python from JamePeng Fork

This guide enables proper Qwen3.5 support with `enable_thinking` parameter handling via `extra_body`.

## Prerequisites

- **Git**: Required for cloning repositories
- **MSVC Build Tools**: Visual Studio 2022 Community (C++ workload)
- **CUDA Toolkit** (optional but recommended for GPU support on Windows)
- **Python 3.9+** from your ComfyUI portable installation

## Build Steps

### Step 1: Clean Up Old Installation

```powershell
cd E:\_win_home_git\genai\ComfyUI-Win-Blackwell\ComfyUI_windows_portable

# Uninstall the current llama-cpp-python
.\python_embeded\python.exe -m pip uninstall llama-cpp-python -y
```

### Step 2: Set Up Build Environment

```powershell
# Open a PowerShell as Administrator and run this to set MSVC paths
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"

# Or in PowerShell (Administrator):
& "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
```

If you don't have Visual Studio installed, install it with the C++ development workload first.

### Step 3: Clone Both Repositories

Create a temporary build folder (e.g., `E:\llama_build\`):

```powershell
mkdir E:\llama_build
cd E:\llama_build

# Clone the JamePeng fork of llama-cpp-python
git clone https://github.com/JamePeng/llama-cpp-python.git
cd llama-cpp-python

# Clone llama.cpp as a vendor dependency
git clone https://github.com/ggml-org/llama.cpp.git vendor/llama.cpp
```

### Step 4: Build from Source

From the `llama-cpp-python` directory:

```powershell
cd E:\llama_build\llama-cpp-python

# Set build environment variables for Windows CUDA (if you have CUDA)
$env:CMAKE_ARGS = "-DGGML_CUDA=ON"  # Remove this if you don't have CUDA

# Install in development mode (rebuilds on import)
E:\_win_home_git\genai\ComfyUI-Win-Blackwell\ComfyUI_windows_portable\python_embeded\python.exe -m pip install -e .
```

**Build Time**: 10-30 minutes depending on your system and whether CUDA is enabled.

### Step 5: Verify Installation

```powershell
E:\_win_home_git\genai\ComfyUI-Win-Blackwell\ComfyUI_windows_portable\python_embeded\python.exe -c "import llama_cpp; print(llama_cpp.__version__)"
```

Should output a version like `0.3.35` or later with JamePeng changes.

### Step 6: Test enable_thinking Support

```powershell
cd E:\_win_home_git\genai\ComfyUI-Win-Blackwell\ComfyUI_windows_portable\ComfyUI\custom_nodes\comfyui-json-dict-tools

# Run the CLI with enable_thinking enabled (should now work)
.\examples\llama_cli_chat.py --model "..\..\models\llm\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q6_K.gguf" --enable-thinking true --verbose
```

**Expected Output**:
```
Note: Passing enable_thinking=True via extra_body
```

No more `TypeError: got an unexpected keyword argument 'extra_body'` error.

## Troubleshooting Build Issues

### Issue: "cmake not found"
**Solution**: Install CMake via `pip install cmake`

### Issue: "cl.exe not found" or MSVC errors
**Solution**: Run vcvars64.bat in the same PowerShell session where you're building. Don't close and reopen PowerShell.

### Issue: Build succeeds but enable_thinking still not working
**Solution**: Verify CUDA toolkit compatibility with llama.cpp:
```powershell
E:\_win_home_git\genai\ComfyUI-Win-Blackwell\ComfyUI_windows_portable\python_embeded\python.exe .\examples\llama_cli_chat.py --model "path/to/model.gguf" --verbose
```

Look for:
```
Note: Passing enable_thinking=True via extra_body
```

If you see warnings about unsupported args, that's OK - the build succeeded.

## After Successful Build

1. **Test with CLI**: Use `llama_cli_chat.py` with `--enable-thinking false` to verify thinking is suppressed
2. **Update ComfyUI Node**: The ComfyUI_Simple_Qwen3-VL-gguf node should now properly pass `enable_thinking` via config_override
3. **Cleanup**: Delete `E:\llama_build\` after successful installation (optional, only if space is needed)

## Alternative: Pre-built Wheels

If building fails and you need a quick workaround, check if pre-built wheels exist:
```powershell
E:\_win_home_git\genai\ComfyUI-Win-Blackwell\ComfyUI_windows_portable\python_embeded\python.exe -m pip install llama-cpp-python --only-binary=:all: --upgrade
```

This may not have the JamePeng changes, so building from fork is strongly preferred.

## References

- JamePeng Fork: https://github.com/JamePeng/llama-cpp-python
- llama.cpp Repo: https://github.com/ggml-org/llama.cpp
- Official Qwen Chat Template: https://huggingface.co/Qwen/Qwen3.5-9B-Instruct/blob/main/tokenizer_config.json
