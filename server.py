#!/usr/bin/env python3
"""
Marmoset Toolbag 5 — MCP Server v1.0
=====================================
Connects to the bridge.py running inside Marmoset Toolbag and exposes
all actions as MCP tools for Claude Desktop, Cursor, Agent Zero, etc.

Usage:
    python server.py                      # default bridge at 127.0.0.1:8765
    python server.py --bridge-url http://192.168.1.50:8765

Claude Desktop config (claude_desktop_config.json):
{
  "mcpServers": {
    "marmoset": {
      "command": "python",
      "args": ["<path>/server.py"]
    }
  }
}
"""

import argparse
import json
import httpx
from mcp.server.fastmcp import FastMCP

# ─── Configuration ────────────────────────────────────────────────
DEFAULT_BRIDGE = "http://127.0.0.1:8765"

parser = argparse.ArgumentParser()
parser.add_argument("--bridge-url", default=DEFAULT_BRIDGE,
                    help="URL of the Marmoset bridge server")
args, _ = parser.parse_known_args()
BRIDGE_URL = args.bridge_url.rstrip("/")

mcp = FastMCP(
    "Marmoset Toolbag 5",
    description="Control Marmoset Toolbag 5 — lighting, cameras, rendering, scene management",
)


# ─── Bridge communication ────────────────────────────────────────
def _call(action: str, params: dict | None = None) -> dict:
    """Send an action to the Marmoset bridge and return the result."""
    try:
        r = httpx.post(
            BRIDGE_URL,
            json={"action": action, "params": params or {}},
            timeout=130,
        )
        return r.json()
    except httpx.ConnectError:
        return {
            "ok": False,
            "error": (
                f"Cannot connect to Marmoset bridge at {BRIDGE_URL}. "
                "Make sure bridge.py is running inside Marmoset Toolbag "
                "(Edit → Run Script → bridge.py)."
            ),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _fmt(result: dict) -> str:
    """Format bridge result as readable text for the LLM."""
    return json.dumps(result, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════
#  MCP TOOLS
# ═══════════════════════════════════════════════════════════════════

# ── Connection ────────────────────────────────────────────────────

@mcp.tool()
def ping() -> str:
    """Check if the Marmoset bridge is running and responsive."""
    return _fmt(_call("ping"))


# ── Scene ─────────────────────────────────────────────────────────

@mcp.tool()
def get_scene_info() -> str:
    """Get an overview of the current Marmoset scene: object counts by type, scene bounds."""
    return _fmt(_call("get_scene_info"))


@mcp.tool()
def list_objects(type: str = "") -> str:
    """List all objects in the scene. Optionally filter by type (e.g. 'light', 'mesh', 'camera').

    Args:
        type: Optional type filter substring (case-insensitive)
    """
    return _fmt(_call("list_objects", {"type": type}))


@mcp.tool()
def frame_scene() -> str:
    """Center and frame the entire scene in the current camera view."""
    return _fmt(_call("frame_scene"))


@mcp.tool()
def frame_object(name: str) -> str:
    """Center and frame a specific object in the camera view.

    Args:
        name: Name of the object to frame
    """
    return _fmt(_call("frame_object", {"name": name}))


@mcp.tool()
def rename_object(name: str, new_name: str) -> str:
    """Rename a scene object.

    Args:
        name: Current name of the object
        new_name: New name to assign
    """
    return _fmt(_call("rename_object", {"name": name, "new_name": new_name}))


@mcp.tool()
def remove_object(name: str) -> str:
    """Remove an object from the scene.

    Args:
        name: Name of the object to remove
    """
    return _fmt(_call("remove_object", {"name": name}))


@mcp.tool()
def import_model(path: str) -> str:
    """Import a 3D model file (FBX, OBJ, etc.) into the scene.

    Args:
        path: Absolute file path on the machine running Marmoset
    """
    return _fmt(_call("import_model", {"path": path}))


# ── Lights ────────────────────────────────────────────────────────

@mcp.tool()
def list_lights() -> str:
    """List all lights in the scene with their properties (type, color, brightness, position, etc.)."""
    return _fmt(_call("list_lights"))


@mcp.tool()
def add_light(
    name: str = "New Light",
    type: str = "directional",
    color: list[float] | None = None,
    brightness: float = 1.0,
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    cast_shadows: bool = True,
    width: float = 0.0,
    temperature: float | None = None,
    spot_angle: float = 45.0,
    spot_sharpness: float = 0.5,
) -> str:
    """Add a new light to the Marmoset scene.

    Args:
        name: Display name for the light
        type: Light type — 'directional', 'spot', or 'omni'
        color: RGB color as [r, g, b] floats (0-1). Default white.
        brightness: Light intensity
        position: World position [x, y, z]
        rotation: Euler rotation [x, y, z] in degrees
        cast_shadows: Whether the light casts shadows
        width: Radius of the light source (soft shadows)
        temperature: Color temperature in Kelvin (1000-10000). Overrides color.
        spot_angle: Spot cone angle in degrees (spot lights only)
        spot_sharpness: Spot edge sharpness (spot lights only)
    """
    params = {"name": name, "type": type, "brightness": brightness,
              "cast_shadows": cast_shadows, "width": width,
              "spot_angle": spot_angle, "spot_sharpness": spot_sharpness}
    if color is not None:
        params["color"] = color
    if position is not None:
        params["position"] = position
    if rotation is not None:
        params["rotation"] = rotation
    if temperature is not None:
        params["temperature"] = temperature
    return _fmt(_call("add_light", params))


@mcp.tool()
def modify_light(
    name: str,
    type: str | None = None,
    color: list[float] | None = None,
    brightness: float | None = None,
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    cast_shadows: bool | None = None,
    width: float | None = None,
    temperature: float | None = None,
    visible_shape: bool | None = None,
    spot_angle: float | None = None,
    spot_sharpness: float | None = None,
    spot_vignette: float | None = None,
    length_x: float | None = None,
    length_y: float | None = None,
    gel_path: str | None = None,
) -> str:
    """Modify an existing light's properties. Only provided values are changed.

    Args:
        name: Name of the light to modify (required)
        type: Change light type — 'directional', 'spot', or 'omni'
        color: RGB color [r, g, b] (0-1)
        brightness: Light intensity
        position: World position [x, y, z]
        rotation: Euler rotation [x, y, z] in degrees
        cast_shadows: Whether the light casts shadows
        width: Radius of the light source
        temperature: Color temperature in Kelvin (1000-10000)
        visible_shape: Make light shape visible in renders
        spot_angle: Spot cone angle (spot lights)
        spot_sharpness: Spot edge sharpness (spot lights)
        spot_vignette: Spot vignette amount (spot lights)
        length_x: Light area length X
        length_y: Light area length Y
        gel_path: Path to a gel/gobo texture image
    """
    params = {"name": name}
    for k, v in {
        "type": type, "color": color, "brightness": brightness,
        "position": position, "rotation": rotation,
        "cast_shadows": cast_shadows, "width": width,
        "temperature": temperature, "visible_shape": visible_shape,
        "spot_angle": spot_angle, "spot_sharpness": spot_sharpness,
        "spot_vignette": spot_vignette, "length_x": length_x,
        "length_y": length_y, "gel_path": gel_path,
    }.items():
        if v is not None:
            params[k] = v
    return _fmt(_call("modify_light", params))


# ── Camera ────────────────────────────────────────────────────────

@mcp.tool()
def set_camera(
    position: list[float] | None = None,
    rotation: list[float] | None = None,
    fov: float | None = None,
    focal_length: float | None = None,
    mode: str | None = None,
    orbit_radius: float | None = None,
) -> str:
    """Configure the active camera's transform and lens.

    Args:
        position: World position [x, y, z]
        rotation: Euler rotation [x, y, z] in degrees
        fov: Vertical field of view in degrees
        focal_length: Focal length in mm (alternative to fov)
        mode: 'perspective' or 'orthographic'
        orbit_radius: Orbit radius for camera rotation
    """
    params = {}
    for k, v in {"position": position, "rotation": rotation,
                 "fov": fov, "focal_length": focal_length,
                 "mode": mode, "orbit_radius": orbit_radius}.items():
        if v is not None:
            params[k] = v
    return _fmt(_call("set_camera", params))


@mcp.tool()
def set_post_effects(
    tone_mapping: str | None = None,
    exposure: float | None = None,
    contrast: float | None = None,
    saturation: float | None = None,
    sharpen: float | None = None,
    bloom_brightness: float | None = None,
    bloom_size: float | None = None,
    vignette_strength: float | None = None,
    vignette_softness: float | None = None,
    film_grain_mode: str | None = None,
    film_grain_intensity: float | None = None,
    highlights: float | None = None,
    shadows: float | None = None,
    midtones: float | None = None,
    clarity: float | None = None,
) -> str:
    """Set post-processing effects on the active camera.

    Args:
        tone_mapping: Tone map mode — 'linear', 'reinhard', 'hejl', 'aces', 'agx'
        exposure: Exposure multiplier
        contrast: Contrast multiplier
        saturation: Color saturation (1.0 = default)
        sharpen: Sharpening strength
        bloom_brightness: Bloom brightness multiplier
        bloom_size: Bloom size scalar
        vignette_strength: Vignette intensity
        vignette_softness: Vignette softness
        film_grain_mode: 'Off', 'Film', or 'Digital'
        film_grain_intensity: Grain intensity
        highlights: Highlights adjustment (-1 to 1)
        shadows: Shadows adjustment (-1 to 1)
        midtones: Midtones adjustment (-1 to 1)
        clarity: Clarity adjustment (-1 to 1)
    """
    params = {}
    for k, v in {
        "tone_mapping": tone_mapping, "exposure": exposure,
        "contrast": contrast, "saturation": saturation,
        "sharpen": sharpen, "bloom_brightness": bloom_brightness,
        "bloom_size": bloom_size, "vignette_strength": vignette_strength,
        "vignette_softness": vignette_softness,
        "film_grain_mode": film_grain_mode,
        "film_grain_intensity": film_grain_intensity,
        "highlights": highlights, "shadows": shadows,
        "midtones": midtones, "clarity": clarity,
    }.items():
        if v is not None:
            params[k] = v
    return _fmt(_call("set_post_effects", params))


@mcp.tool()
def set_depth_of_field(
    enabled: bool = True,
    focus_distance: float | None = None,
    f_stop: float | None = None,
    mode: str | None = None,
    anamorphic_ratio: float | None = None,
) -> str:
    """Configure depth of field on the active camera.

    Args:
        enabled: Turn DOF on or off
        focus_distance: Distance to the focus plane
        f_stop: Aperture f-stop value (lower = more blur)
        mode: DOF quality mode
        anamorphic_ratio: Anamorphic bokeh squeeze ratio
    """
    params = {"enabled": enabled}
    for k, v in {"focus_distance": focus_distance, "f_stop": f_stop,
                 "mode": mode, "anamorphic_ratio": anamorphic_ratio}.items():
        if v is not None:
            params[k] = v
    return _fmt(_call("set_dof", params))


@mcp.tool()
def set_lens(
    barrel_distortion: float | None = None,
    chromatic_aberration: float | None = None,
    lens_flare_strength: float | None = None,
    motion_blur_enable: bool | None = None,
    motion_blur_shutter: float | None = None,
) -> str:
    """Configure lens effects on the active camera.

    Args:
        barrel_distortion: Barrel distortion amount
        chromatic_aberration: Chromatic aberration strength
        lens_flare_strength: Lens flare intensity
        motion_blur_enable: Enable motion blur
        motion_blur_shutter: Shutter speed for motion blur
    """
    params = {}
    for k, v in {
        "barrel_distortion": barrel_distortion,
        "chromatic_aberration": chromatic_aberration,
        "lens_flare_strength": lens_flare_strength,
        "motion_blur_enable": motion_blur_enable,
        "motion_blur_shutter": motion_blur_shutter,
    }.items():
        if v is not None:
            params[k] = v
    return _fmt(_call("set_lens", params))


# ── Sky / Environment ─────────────────────────────────────────────

@mcp.tool()
def set_sky(
    brightness: float | None = None,
    rotation: float | None = None,
    mode: str | None = None,
    blur: float | None = None,
    background_brightness: float | None = None,
    background_color: list[float] | None = None,
    child_light_brightness: float | None = None,
    time: float | None = None,
    day: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    turbidity: float | None = None,
    sun_brightness: float | None = None,
    sun_scale: float | None = None,
    saturation: float | None = None,
    white_balance: float | None = None,
    compute_procedural: bool = False,
) -> str:
    """Configure the sky/environment in the scene.

    Args:
        brightness: Overall sky brightness
        rotation: Sky rotation angle in degrees
        mode: Background mode — 'color', 'sky', 'blurred sky', 'ambient sky'
        blur: Background blur amount
        background_brightness: Background-specific brightness
        background_color: Background color [r, g, b] when mode is 'color'
        child_light_brightness: Brightness of sky child lights
        time: Time of day 0-24 (procedural sky)
        day: Day of year 1-365 (procedural sky)
        latitude: Geographic latitude (procedural sky)
        longitude: Geographic longitude (procedural sky)
        turbidity: Atmospheric haze 0-1 (procedural sky)
        sun_brightness: Sun brightness (procedural sky)
        sun_scale: Sun apparent size (procedural sky)
        saturation: Sky color saturation (procedural sky)
        white_balance: Color temperature shift (procedural sky)
        compute_procedural: Set True to recompute the procedural sky after changes
    """
    params = {}
    for k, v in {
        "brightness": brightness, "rotation": rotation,
        "mode": mode, "blur": blur,
        "background_brightness": background_brightness,
        "background_color": background_color,
        "child_light_brightness": child_light_brightness,
        "time": time, "day": day, "latitude": latitude,
        "longitude": longitude, "turbidity": turbidity,
        "sun_brightness": sun_brightness, "sun_scale": sun_scale,
        "saturation": saturation, "white_balance": white_balance,
    }.items():
        if v is not None:
            params[k] = v
    if compute_procedural:
        params["compute_procedural"] = True
    return _fmt(_call("set_sky", params))


@mcp.tool()
def load_sky(path: str) -> str:
    """Load a .tbsky sky file.

    Args:
        path: Absolute path to the .tbsky file on the Marmoset machine
    """
    return _fmt(_call("load_sky", {"path": path}))


@mcp.tool()
def import_sky_image(path: str) -> str:
    """Import an HDR/EXR image as the sky environment.

    Args:
        path: Absolute path to the HDR/EXR image
    """
    return _fmt(_call("import_sky_image", {"path": path}))


# ── Fog ───────────────────────────────────────────────────────────

@mcp.tool()
def set_fog(
    color: list[float] | None = None,
    density: float | None = None,
    opacity: float | None = None,
) -> str:
    """Configure scene fog.

    Args:
        color: Fog color [r, g, b]
        density: Fog density
        opacity: Fog opacity
    """
    params = {}
    for k, v in {"color": color, "density": density, "opacity": opacity}.items():
        if v is not None:
            params[k] = v
    return _fmt(_call("set_fog", params))


# ── Render ────────────────────────────────────────────────────────

@mcp.tool()
def set_render_settings(
    renderer: str | None = None,
    ray_trace_bounces: int | None = None,
    shadow_quality: str | None = None,
    occlusion_mode: str | None = None,
    occlusion_strength: float | None = None,
    use_reflections: bool | None = None,
    reflection_intensity: float | None = None,
    ray_trace_caustics: bool | None = None,
    ray_trace_advanced_sampling: bool | None = None,
) -> str:
    """Configure render quality settings.

    Args:
        renderer: Enable ray tracing renderer
        ray_trace_bounces: Number of ray trace bounces
        shadow_quality: 'Low', 'High', or 'Mega'
        occlusion_mode: 'Disabled', 'Screen', or 'Raytraced'
        occlusion_strength: AO strength
        use_reflections: Enable reflections
        reflection_intensity: Reflection strength
        ray_trace_caustics: Enable caustics
        ray_trace_advanced_sampling: Enable advanced sampling
    """
    params = {}
    for k, v in {
        "renderer": renderer,
        "ray_trace_bounces": ray_trace_bounces,
        "shadow_quality": shadow_quality,
        "occlusion_mode": occlusion_mode,
        "occlusion_strength": occlusion_strength,
        "use_reflections": use_reflections,
        "reflection_intensity": reflection_intensity,
        "ray_trace_caustics": ray_trace_caustics,
        "ray_trace_advanced_sampling": ray_trace_advanced_sampling,
    }.items():
        if v is not None:
            params[k] = v
    return _fmt(_call("set_render_settings", params))


@mcp.tool()
def render_image(
    path: str,
    width: int = 1920,
    height: int = 1080,
    samples: int = 256,
    transparency: bool = False,
) -> str:
    """Render a single image from the active camera.

    Args:
        path: Output file path (e.g. C:/renders/shot.png)
        width: Image width in pixels
        height: Image height in pixels
        samples: Number of samples (higher = less noise)
        transparency: Render with transparent background
    """
    return _fmt(_call("render_image", {
        "path": path, "width": width, "height": height,
        "samples": samples, "transparency": transparency,
    }))


@mcp.tool()
def render_images(
    width: int = 1920,
    height: int = 1080,
    samples: int = 256,
    transparency: bool = False,
) -> str:
    """Render all configured cameras/passes using the scene's RenderObject settings.

    Args:
        width: Image width in pixels
        height: Image height in pixels
        samples: Number of samples
        transparency: Render with transparent background
    """
    return _fmt(_call("render_images", {
        "width": width, "height": height,
        "samples": samples, "transparency": transparency,
    }))


# ── Advanced ──────────────────────────────────────────────────────

@mcp.tool()
def execute_script(code: str) -> str:
    """Execute arbitrary Python code inside Marmoset Toolbag.
    The `mset` module is available. Set a variable named `result`
    to return data to the MCP client.

    Example:
        result = [o.name for o in mset.getAllObjects()]

    Args:
        code: Python code to execute inside Toolbag
    """
    return _fmt(_call("execute_script", {"code": code}))


# ═══════════════════════════════════════════════════════════════════
#  RESOURCES
# ═══════════════════════════════════════════════════════════════════

@mcp.resource("marmoset://scene/info")
def resource_scene_info() -> str:
    """Current scene information."""
    return _fmt(_call("get_scene_info"))


@mcp.resource("marmoset://scene/lights")
def resource_lights() -> str:
    """All lights in the current scene."""
    return _fmt(_call("list_lights"))


@mcp.resource("marmoset://scene/objects")
def resource_objects() -> str:
    """All objects in the current scene."""
    return _fmt(_call("list_objects"))


# ═══════════════════════════════════════════════════════════════════
#  PROMPTS (contextual templates for the LLM)
# ════════════════════════���══════════════════════════════════════════

@mcp.prompt()
def setup_cinematic_lighting() -> str:
    """Guide for setting up cinematic 3-point lighting in Marmoset."""
    return """You are a lighting artist setting up cinematic lighting in Marmoset Toolbag 5.

First use `get_scene_info` and `list_lights` to understand the current scene.
Then create a classic 3-point lighting setup:

1. **Key Light** (main): Warm directional or spot, positioned 45° to the right and 30° above.
   - Brightness: 2-3, Temperature: ~5500K, Shadows: on
2. **Fill Light**: Cool, soft light opposite the key, about 50% the key's brightness.
   - Brightness: 1-1.5, Temperature: ~7000K, Width: larger for softness
3. **Rim/Back Light**: Strong light from behind to separate subject from background.
   - Brightness: 2-4, positioned behind and above the subject

After placing lights, set post-processing:
- Tone mapping: 'aces'
- Slight bloom for glow
- Subtle vignette
- ACES or AgX tone mapping

Adjust based on the scene content and user's desired mood."""


@mcp.prompt()
def setup_studio_portrait() -> str:
    """Guide for setting up studio portrait lighting for character showcases."""
    return """You are a portrait lighting specialist working in Marmoset Toolbag 5.

First inspect the scene to understand the character positioning.
Then create flattering portrait lighting:

1. **Key Light**: Large area light (spot with wide angle or large width) at 30-45° to one side.
   - Soft shadows, brightness 2, neutral-warm temperature ~5000K
2. **Fill Light**: Very soft, almost shadowless, on the opposite side.
   - Brightness: 0.8-1.2, cool temperature ~6500K
3. **Hair/Rim Light**: From behind-above to highlight hair and shoulders.
   - Brightness: 1.5-2, slightly warm
4. **Background Light** (optional): To separate subject from background.

Post-processing: subtle, enhance skin tones:
- Tone mapping: 'aces' or 'agx'
- Slight positive shadows lift
- Gentle bloom
- Minimal sharpening"""


@mcp.prompt()
def render_for_portfolio() -> str:
    """Guide for rendering portfolio-quality images from Marmoset."""
    return """You are helping create portfolio-quality renders in Marmoset Toolbag 5.

Workflow:
1. Check the scene with `get_scene_info` and `list_objects`
2. Frame the subject with `frame_scene` or `frame_object`
3. Set up camera: good FOV (35-85mm), slight DOF for depth
4. Configure lighting appropriate to the subject
5. Set render quality:
   - Enable ray tracing if available
   - Shadow quality: 'High' or 'Mega'
   - Raytraced AO
   - Enable reflections
6. Post-processing: ACES tone mapping, subtle bloom, slight vignette
7. Render at high resolution (2K-4K) with 512+ samples
8. Consider rendering with transparency for compositing"""


# ═══════════════════════════════════════════════════════════════════
#  ENTRY
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run()
