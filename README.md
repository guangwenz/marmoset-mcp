# 🎨 Marmoset Toolbag 5 — MCP Server

Control **Marmoset Toolbag 5** from any MCP-compatible AI client (Claude Desktop, Cursor, Windsurf, Agent Zero, etc.).

No more being the middle-man — your AI assistant talks directly to Marmoset.

---

## Architecture

```
┌──────────────────┐     stdio      ┌──────────────────┐    HTTP     ┌──────────────────────┐
│  Claude Desktop  │◄──────────────►│   MCP Server     │◄──────────►│  MCP Bridge Plugin   │
│  Cursor / etc.   │    (MCP)       │   server.py      │  :8765     │  (inside Toolbag)    │
│                  │                │  (your machine)  │            │  auto-loads on start │
└──────────────────┘                └──────────────────┘            └──────────────────────┘
```

**Two components:**
1. **MCP_Bridge.py** — A Toolbag **plugin** that auto-loads when Marmoset starts. Exposes the `mset` Python API over a local HTTP server with a status UI panel.
2. **server.py** — An MCP server that runs on your machine. Translates MCP tool calls into HTTP requests to the bridge plugin.

---

## Quick Start

### Step 1: Install the Marmoset Plugin

Copy `bridge.py` to your Marmoset Toolbag plugins folder and rename it:

**Windows:**
```
copy bridge.py "C:\Program Files\Marmoset Toolbag 5\data\plugins\MCP_Bridge.py"
```

**macOS:**
```
cp bridge.py "/Applications/Marmoset Toolbag 5.app/Contents/Resources/data/plugins/MCP_Bridge.py"
```

Restart Marmoset Toolbag. The plugin loads automatically and shows a status panel:

```
┌─ MCP Bridge ──────────────────┐
│  Status:    ● Running         │
│  Endpoint:  http://127.0.0.1:8765 │
│  Actions:   23                │
│  Requests:  0                 │
│                               │
│  [ Stop Server ]              │
└───────────────────────────────┘
```

You can toggle the server on/off with the button. No need to run scripts manually ever again.

### Step 2: Set up the MCP Server (Miniconda)

Create a dedicated conda environment:

```bash
conda create -n marmoset-mcp python=3.11 -y
conda activate marmoset-mcp
pip install mcp[cli] httpx
```

Test that the server can start:
```bash
python server.py
```

### Step 3: Connect your MCP client

#### Claude Desktop

Edit your `claude_desktop_config.json`:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`  
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "marmoset": {
      "command": "C:/Users/YOU/miniconda3/envs/marmoset-mcp/python.exe",
      "args": ["C:/path/to/server.py"]
    }
  }
}
```

> **Important:** Use the full path to the conda environment's `python.exe` so Claude Desktop picks up the right packages. Find it with:
> ```bash
> conda activate marmoset-mcp
> where python    # Windows
> which python    # macOS/Linux
> ```

Restart Claude Desktop. You'll see a 🔨 tool icon with Marmoset tools.

#### Cursor

Add to `.cursor/mcp.json` in your project or global Cursor settings:

```json
{
  "mcpServers": {
    "marmoset": {
      "command": "C:/Users/YOU/miniconda3/envs/marmoset-mcp/python.exe",
      "args": ["C:/path/to/server.py"]
    }
  }
}
```

#### Custom Bridge URL

If the bridge runs on a different port or machine:
```bash
python server.py --bridge-url http://192.168.1.50:8765
```

---

## Available MCP Tools (23 tools)

### 🔗 Connection
| Tool | Description |
|------|-------------|
| `ping` | Check if the Marmoset bridge is running |

### 🎬 Scene Management
| Tool | Description |
|------|-------------|
| `get_scene_info` | Object counts, types, scene bounds |
| `list_objects` | List all objects (optional type filter) |
| `import_model` | Import FBX, OBJ, etc. |
| `frame_scene` | Frame entire scene in camera |
| `frame_object` | Frame a specific object |
| `rename_object` | Rename any scene object |
| `remove_object` | Delete an object from the scene |

### 💡 Lighting
| Tool | Description |
|------|-------------|
| `list_lights` | List all lights with full properties |
| `add_light` | Create directional, spot, or omni lights |
| `modify_light` | Change any light property (color, temperature, position, shadows, gels, etc.) |

### 📷 Camera & Post-Processing
| Tool | Description |
|------|-------------|
| `set_camera` | Position, rotation, FOV, focal length |
| `set_post_effects` | Tone mapping, bloom, vignette, grain, contrast, clarity |
| `set_depth_of_field` | DOF focus distance, f-stop, bokeh |
| `set_lens` | Distortion, chromatic aberration, lens flares, motion blur |

### 🌅 Environment
| Tool | Description |
|------|-------------|
| `set_sky` | Sky brightness, rotation, procedural sky (time, latitude, turbidity, etc.) |
| `load_sky` | Load a .tbsky file |
| `import_sky_image` | Import HDR/EXR environment map |
| `set_fog` | Fog color, density, opacity |

### 🖼️ Rendering
| Tool | Description |
|------|-------------|
| `set_render_settings` | Ray tracing, shadows, AO, reflections, caustics |
| `render_image` | Render single image at specified resolution + samples |
| `render_images` | Render all cameras/passes |

### ⚡ Advanced
| Tool | Description |
|------|-------------|
| `execute_script` | Run arbitrary Python code inside Toolbag |

---

## Built-in Prompts

The MCP server includes contextual prompt templates that guide the AI:

- **`setup_cinematic_lighting`** — 3-point cinematic lighting rig
- **`setup_studio_portrait`** — Portrait/character showcase lighting
- **`render_for_portfolio`** — Portfolio-quality render workflow

---

## Example Conversations

Once connected, just talk naturally:

> **You:** "Set up cinematic lighting for my character"  
> **AI:** *Inspects scene → creates key/fill/rim lights → configures post-effects*

> **You:** "Make it more dramatic with warmer tones"  
> **AI:** *Adjusts light brightness ratios and color temperatures*

> **You:** "Render at 4K with ray tracing"  
> **AI:** *Enables RT, sets quality, renders at 3840×2160*

> **You:** "Import my character from C:/exports/hero.fbx and set up a studio portrait"  
> **AI:** *Imports model → frames it → builds portrait lighting rig*

---

## Workflow: iClone 8 / Character Creator → Marmoset

### Export from iClone 8 / CC4
1. Export as **FBX** (Binary, recommended)
2. Enable **Embed Textures** or export textures to a subfolder
3. Use **iClone/CC default** coordinate system

### Import & Render in Marmoset (via AI)
1. *"Import C:/exports/my_character.fbx"*
2. *"Set up studio portrait lighting"*
3. *"Add some rim light from the left, increase bloom"*
4. *"Render 4K PNG with transparency"*

---

## Plugin Configuration

Edit these constants at the top of `bridge.py` if needed:

| Setting | Default | Description |
|---------|---------|-------------|
| `BRIDGE_HOST` | `"127.0.0.1"` | Bind address (use `"0.0.0.0"` for remote access) |
| `BRIDGE_PORT` | `8765` | HTTP port |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Cannot connect to bridge" | Check the MCP Bridge plugin panel in Marmoset — status should say "● Running" |
| Plugin doesn't appear | Verify the file is in the correct `data/plugins/` folder and named `.py` |
| Bridge port conflict | Change `BRIDGE_PORT` in bridge.py and use `--bridge-url` for server.py |
| Light creation fails | Toolbag may need at least one light in the scene first — add one manually, then the AI can duplicate/modify it |
| Claude Desktop can't find packages | Use the full conda python path in the config, not just `"python"` |
| Slow responses | The plugin queues commands on Toolbag's main thread via `onPeriodicUpdate`. Close heavy scenes for faster response |
| Script errors | Check Toolbag's Python Console (Edit → Python Console) for error details |

---

## Security Note

The bridge listens on `127.0.0.1` (localhost only) by default. To allow remote access, change `BRIDGE_HOST` in bridge.py to `"0.0.0.0"` — but only on trusted networks.

---

## License

MIT — Free to use, modify, and distribute.
