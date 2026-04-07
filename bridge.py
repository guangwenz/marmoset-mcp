"""
Marmoset Toolbag 5 — MCP Bridge Plugin v1.1
=============================================
Install:
  Copy this file to your Marmoset plugins folder:
    Windows:  C:/Program Files/Marmoset Toolbag 5/data/plugins/MCP_Bridge.py
    macOS:    /Applications/Marmoset Toolbag 5.app/Contents/Resources/data/plugins/MCP_Bridge.py

  Restart Toolbag — the plugin loads automatically and shows a status window.

The plugin starts a lightweight HTTP server so an external MCP server
can control the scene, lights, camera, rendering, and more.

Default endpoint:  http://127.0.0.1:8765
"""

import mset
import json
import threading
import queue
import traceback
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─── Configuration ────────────────────────────────────────────────
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8765
PLUGIN_NAME = "MCP Bridge"

# ─── Internals ────────────────────────────────────────────────────
_cmd_queue  = queue.Queue()
_results    = {}
_rlock      = threading.Lock()
_server     = None
_thread     = None
_running    = False
_request_count = 0


# ═══════════════════════════════════════════════════════════════════
#  PLUGIN UI
# ═══════════════════════════════════════════════════════════════════

_window = mset.UIWindow()
_window.title = PLUGIN_NAME
_window.width = 320
_window.height = 180

_lbl_status_hdr = mset.UILabel()
_lbl_status_hdr.text = "Status:"
_lbl_status_hdr.fixedWidth = 80
_window.addElement(_lbl_status_hdr)
_lbl_status = mset.UILabel()
_lbl_status.text = "Starting..."
_window.addElement(_lbl_status)
_window.addReturn()

_lbl_endpoint_hdr = mset.UILabel()
_lbl_endpoint_hdr.text = "Endpoint:"
_lbl_endpoint_hdr.fixedWidth = 80
_window.addElement(_lbl_endpoint_hdr)
_lbl_endpoint = mset.UILabel()
_lbl_endpoint.text = f"http://{BRIDGE_HOST}:{BRIDGE_PORT}"
_window.addElement(_lbl_endpoint)
_window.addReturn()

_lbl_actions_hdr = mset.UILabel()
_lbl_actions_hdr.text = "Actions:"
_lbl_actions_hdr.fixedWidth = 80
_window.addElement(_lbl_actions_hdr)
_lbl_actions = mset.UILabel()
_lbl_actions.text = "loading..."
_window.addElement(_lbl_actions)
_window.addReturn()

_lbl_requests_hdr = mset.UILabel()
_lbl_requests_hdr.text = "Requests:"
_lbl_requests_hdr.fixedWidth = 80
_window.addElement(_lbl_requests_hdr)
_lbl_requests = mset.UILabel()
_lbl_requests.text = "0"
_window.addElement(_lbl_requests)
_window.addReturn()
_window.addSpace(10)

def _on_toggle():
    """Toggle the server on/off."""
    global _running
    if _running:
        _stop_server()
    else:
        _start_server()

_btn_toggle = mset.UIButton()
_btn_toggle.text = "Stop Server"
_btn_toggle.onClick = _on_toggle
_window.addElement(_btn_toggle)


def _update_ui():
    """Refresh the UI labels."""
    if _running:
        _lbl_status.text = "Running"
        _btn_toggle.text = "Stop Server"
    else:
        _lbl_status.text = "Stopped"
        _btn_toggle.text = "Start Server"
    _lbl_requests.text = str(_request_count)


# ═══════════════════════════════════════════════════════════════════
#  HTTP HANDLER
# ═══════════════════════════════════════════════════════════════════

class _Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        """Health check."""
        self._ok({"status": "ok", "bridge": "Marmoset Toolbag 5",
                  "plugin": PLUGIN_NAME,
                  "port": BRIDGE_PORT, "actions": sorted(_ACTIONS.keys())})

    def do_POST(self):
        global _request_count
        try:
            body = self._body()
            action = body.get("action", "")
            params = body.get("params", {})

            # Queue the command and wait for main-thread execution
            evt = threading.Event()
            cid = id(evt)
            _cmd_queue.put((cid, action, params, evt))
            if evt.wait(timeout=120):
                with _rlock:
                    result = _results.pop(cid, {"ok": False, "error": "result lost"})
            else:
                with _rlock:
                    _results.pop(cid, None)
                result = {"ok": False, "error": "timeout (120 s)"}

            _request_count += 1
            self._ok(result)
        except Exception as exc:
            self._ok({"ok": False, "error": str(exc),
                      "traceback": traceback.format_exc()}, code=500)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    # ── helpers ────────────────────────────────────────────────────
    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def _ok(self, data, code=200):
        payload = json.dumps(data, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._cors()
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, *_a):
        pass


# ═══════════════════════════════════════════════════════════════════
#  QUEUE PROCESSOR  (runs on main thread via onPeriodicUpdate)
# ═══════════════════════════════════════════════════════════════════

def _process_queue():
    """Drain up to 10 commands per tick.  Also refresh UI."""
    for _ in range(10):
        try:
            cid, action, params, evt = _cmd_queue.get_nowait()
        except queue.Empty:
            break
        result = _run_action(action, params)
        with _rlock:
            _results[cid] = result
        evt.set()
    _update_ui()


def _run_action(action, params):
    handler = _ACTIONS.get(action)
    if not handler:
        return {"ok": False, "error": f"Unknown action: {action}",
                "available": sorted(_ACTIONS.keys())}
    try:
        data = handler(params)
        return {"ok": True, "data": data}
    except Exception as exc:
        return {"ok": False, "error": str(exc),
                "traceback": traceback.format_exc()}


# ═══════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════

def _find_sky():
    for o in mset.getAllObjects():
        if type(o).__name__ == "SkyBoxObject":
            return o
    return None

def _find_render():
    for o in mset.getAllObjects():
        if type(o).__name__ == "RenderObject":
            return o
    return None

def _find_fog():
    for o in mset.getAllObjects():
        if type(o).__name__ == "FogObject":
            return o
    return None

def _obj_info(o):
    info = {"name": o.name, "type": type(o).__name__, "visible": o.visible}
    if hasattr(o, "position"):
        info["position"] = list(o.position)
        info["rotation"] = list(o.rotation)
    return info

def _light_info(o):
    info = _obj_info(o)
    info.update({
        "light_type": o.lightType,
        "color": list(o.color),
        "brightness": o.brightness,
        "cast_shadows": o.castShadows,
        "width": o.width,
        "use_temperature": o.useTemperature,
        "temperature": o.temperature,
    })
    if o.lightType == "spot":
        info.update({"spot_angle": o.spotAngle,
                     "spot_sharpness": o.spotSharpness})
    return info


# ═══════════════════════════════════════════════════════════════════
#  ACTION HANDLERS
# ═══════════════════════════════════════════════════════════════════

def _ping(_p):
    return {"pong": True, "version": str(mset.getToolbagVersion())}


def _get_scene_info(_p):
    objs = mset.getAllObjects()
    types = {}
    for o in objs:
        t = type(o).__name__
        types[t] = types.get(t, 0) + 1
    bounds = mset.getSceneBounds()
    return {"object_count": len(objs), "types": types, "bounds": bounds}


def _list_objects(p):
    filt = p.get("type", "").lower()
    out = []
    for o in mset.getAllObjects():
        t = type(o).__name__
        if filt and filt not in t.lower():
            continue
        out.append(_obj_info(o))
    return out


def _list_lights(_p):
    out = []
    for o in mset.getAllObjects():
        if type(o).__name__ == "LightObject":
            out.append(_light_info(o))
    return out


def _import_model(p):
    path = p["path"]
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    obj = mset.importModel(path)
    mset.frameScene()
    return {"name": obj.name, "type": type(obj).__name__}


def _add_light(p):
    """Create a light. Tries multiple Toolbag API patterns."""
    light = None
    # Attempt 1: factory
    for fn in ("addLight", "newLight", "addObject"):
        func = getattr(mset, fn, None)
        if func:
            try:
                light = func() if fn != "addObject" else func("Light")
                break
            except Exception:
                pass
    # Attempt 2: constructor
    if light is None:
        try:
            light = mset.LightObject()
        except Exception:
            pass
    # Attempt 3: duplicate an existing light
    if light is None:
        for o in mset.getAllObjects():
            if type(o).__name__ == "LightObject":
                light = o.duplicate(p.get("name", "New Light"))
                break
    if light is None:
        raise RuntimeError(
            "Could not create a new light. Try adding one manually in "
            "Toolbag first, then use modify_light to configure it.")

    light.name      = p.get("name", light.name)
    light.lightType = p.get("type", "directional")
    if "color"      in p: light.color      = p["color"]
    if "brightness" in p: light.brightness  = float(p["brightness"])
    if "position"   in p: light.position    = p["position"]
    if "rotation"   in p: light.rotation    = p["rotation"]
    if "cast_shadows" in p: light.castShadows = bool(p["cast_shadows"])
    if "width"      in p: light.width       = float(p["width"])
    if "temperature" in p:
        light.useTemperature = True
        light.temperature    = float(p["temperature"])
    if light.lightType == "spot":
        if "spot_angle"     in p: light.spotAngle     = float(p["spot_angle"])
        if "spot_sharpness" in p: light.spotSharpness = float(p["spot_sharpness"])
    return _light_info(light)


def _modify_light(p):
    name = p["name"]
    obj  = mset.findObject(name)
    if obj is None or type(obj).__name__ != "LightObject":
        raise ValueError(f"Light not found: {name}")
    _MAP = {
        "type": "lightType", "color": "color", "brightness": "brightness",
        "position": "position", "rotation": "rotation",
        "cast_shadows": "castShadows", "width": "width",
        "visible_shape": "visibleShape",
        "spot_angle": "spotAngle", "spot_sharpness": "spotSharpness",
        "spot_vignette": "spotVignette",
        "length_x": "lengthX", "length_y": "lengthY",
        "gel_path": "gelPath",
    }
    for k, v in p.items():
        attr = _MAP.get(k)
        if attr:
            setattr(obj, attr, v)
    if "temperature" in p:
        obj.useTemperature = True
        obj.temperature = float(p["temperature"])
    return _light_info(obj)


def _rename_object(p):
    obj = mset.findObject(p["name"])
    if not obj:
        raise ValueError(f"Not found: {p['name']}")
    obj.name = p["new_name"]
    return {"renamed": True, "new_name": obj.name}


def _remove_object(p):
    obj = mset.findObject(p["name"])
    if not obj:
        raise ValueError(f"Not found: {p['name']}")
    obj.destroy()
    return {"removed": p["name"]}


def _set_sky(p):
    sky = _find_sky()
    if not sky:
        raise ValueError("No SkyBoxObject in scene")
    _MAP = {
        "brightness": "brightness", "rotation": "rotation",
        "mode": "mode", "blur": "blur",
        "background_brightness": "backgroundBrightness",
        "background_color": "backgroundColor",
        "child_light_brightness": "childLightBrightness",
        # procedural
        "time": "time", "day": "day", "time_zone": "timeZone",
        "latitude": "latitude", "longitude": "longitude",
        "turbidity": "turbidity",
        "sun_brightness": "sunBrightness", "sun_scale": "sunScale",
        "saturation": "saturation", "white_balance": "whiteBalance",
    }
    for k, v in p.items():
        attr = _MAP.get(k)
        if attr:
            setattr(sky, attr, v)
    if p.get("compute_procedural"):
        sky.computeProcedural()
    return {"sky_configured": True}


def _load_sky(p):
    sky = _find_sky()
    if not sky:
        raise ValueError("No SkyBoxObject in scene")
    sky.loadSky(p["path"])
    return {"loaded": p["path"]}


def _import_sky_image(p):
    sky = _find_sky()
    if not sky:
        raise ValueError("No SkyBoxObject in scene")
    sky.importImage(p["path"])
    return {"imported": p["path"]}


def _set_camera(p):
    cam = mset.getCamera()
    if not cam:
        raise ValueError("No active camera")
    _MAP = {
        "position": "position", "rotation": "rotation",
        "fov": "fov", "focal_length": "focalLength",
        "mode": "mode", "orbit_radius": "orbitRadius",
        "near_plane_scale": "nearPlaneScale",
    }
    for k, v in p.items():
        attr = _MAP.get(k)
        if attr:
            setattr(cam, attr, v)
    return {"camera_configured": True, "name": cam.name}


def _set_post_effects(p):
    cam = mset.getCamera()
    if not cam:
        raise ValueError("No active camera")
    pe = cam.postEffect
    _MAP = {
        "tone_mapping": "toneMappingMode", "exposure": "exposure",
        "contrast": "contrast", "contrast_center": "contrastCenter",
        "saturation": "saturation", "sharpen": "sharpen",
        "bloom_brightness": "bloomBrightness", "bloom_size": "bloomSize",
        "vignette_strength": "vignetteStrength",
        "vignette_softness": "vignetteSoftness",
        "film_grain_mode": "filmGrainMode",
        "film_grain_intensity": "filmGrainIntensity",
        "highlights": "highlights", "shadows": "shadows",
        "midtones": "midtones", "clarity": "clarity",
    }
    applied = []
    for k, v in p.items():
        attr = _MAP.get(k)
        if attr:
            setattr(pe, attr, v)
            applied.append(k)
    return {"applied": applied}


def _set_dof(p):
    cam = mset.getCamera()
    if not cam:
        raise ValueError("No active camera")
    lens = cam.lens
    _MAP = {
        "enabled": "dofEnabled", "focus_distance": "dofFocusDistance",
        "f_stop": "dofStop", "mode": "dofMode",
        "anamorphic_ratio": "dofAnamorphicRatio",
    }
    for k, v in p.items():
        attr = _MAP.get(k)
        if attr:
            setattr(lens, attr, v)
    return {"dof_configured": True}


def _set_lens(p):
    cam = mset.getCamera()
    if not cam:
        raise ValueError("No active camera")
    lens = cam.lens
    _MAP = {
        "barrel_distortion": "distortionBarrel",
        "chromatic_aberration": "distortionChromaticAberration",
        "lens_flare_strength": "lensFlareStrength",
        "motion_blur_enable": "motionBlurEnable",
        "motion_blur_shutter": "motionBlurShutterSpeed",
    }
    for k, v in p.items():
        attr = _MAP.get(k)
        if attr:
            setattr(lens, attr, v)
    return {"lens_configured": True}


def _set_render_settings(p):
    ro = _find_render()
    if not ro:
        raise ValueError("No RenderObject in scene")
    opts = ro.options
    _MAP = {
        "renderer": "renderer",
        "ray_trace_bounces": "rayTraceBounces",
        "ray_trace_transmission_bounces": "rayTraceTransmissionBounces",
        "shadow_quality": "shadowQuality",
        "occlusion_mode": "occlusionMode",
        "occlusion_strength": "occlusionStrength",
        "use_reflections": "useReflections",
        "reflection_intensity": "reflectionIntensity",
        "ray_trace_caustics": "rayTraceCaustics",
        "ray_trace_advanced_sampling": "rayTraceAdvancedSampling",
    }
    for k, v in p.items():
        attr = _MAP.get(k)
        if attr:
            setattr(opts, attr, v)
    return {"render_settings_configured": True}


def _render_image(p):
    path   = p.get("path", "")
    width  = int(p.get("width", 1920))
    height = int(p.get("height", 1080))
    samples = int(p.get("samples", 256))
    transp = bool(p.get("transparency", False))
    mset.renderCamera(path=path, width=width, height=height,
                      sampling=samples, transparency=transp)
    return {"rendered": path, "resolution": f"{width}x{height}",
            "samples": samples}


def _render_images(p):
    """Uses the scene RenderObject settings (multi-camera / passes)."""
    width  = int(p.get("width", 1920))
    height = int(p.get("height", 1080))
    samples = int(p.get("samples", 256))
    transp = bool(p.get("transparency", False))
    mset.renderImages(width=width, height=height,
                      sampling=samples, transparency=transp)
    return {"rendered": True}


def _frame_scene(_p):
    mset.frameScene()
    return {"framed": True}


def _frame_object(p):
    obj = mset.findObject(p["name"])
    if not obj:
        raise ValueError(f"Not found: {p['name']}")
    mset.frameObject(obj)
    return {"framed": p["name"]}


def _set_fog(p):
    fog = _find_fog()
    if not fog:
        raise ValueError("No FogObject in scene")
    if "color"   in p: fog.color   = p["color"]
    if "density" in p: fog.density = float(p["density"])
    if "opacity" in p: fog.opacity = float(p["opacity"])
    return {"fog_configured": True}


def _execute_script(p):
    """Run arbitrary Python code inside Toolbag.  Set a `result`
    variable in your code to return data."""
    code = p.get("code", "")
    ns = {"mset": mset, "__builtins__": __builtins__}
    exec(code, ns)
    return ns.get("result", {"executed": True})


# ═══════════════════════════════════════════════════════════════════
#  ACTION REGISTRY
# ═══════════════════════════════════════════════════════════════════

_ACTIONS = {
    "ping":                 _ping,
    "get_scene_info":       _get_scene_info,
    "list_objects":         _list_objects,
    "list_lights":          _list_lights,
    "import_model":         _import_model,
    "add_light":            _add_light,
    "modify_light":         _modify_light,
    "rename_object":        _rename_object,
    "remove_object":        _remove_object,
    "set_sky":              _set_sky,
    "load_sky":             _load_sky,
    "import_sky_image":     _import_sky_image,
    "set_camera":           _set_camera,
    "set_post_effects":     _set_post_effects,
    "set_dof":              _set_dof,
    "set_lens":             _set_lens,
    "set_render_settings":  _set_render_settings,
    "render_image":         _render_image,
    "render_images":        _render_images,
    "frame_scene":          _frame_scene,
    "frame_object":         _frame_object,
    "set_fog":              _set_fog,
    "execute_script":       _execute_script,
}


# ═══════════════════════════════════════════════════════════════════
#  SERVER START / STOP
# ═══════════════════════════════════════════════════════════════════

def _start_server():
    global _server, _thread, _running
    if _running:
        return

    try:
        _server = HTTPServer((BRIDGE_HOST, BRIDGE_PORT), _Handler)
    except OSError as e:
        _lbl_status.text = f"ERROR: {e}"
        print(f"[{PLUGIN_NAME}] ERROR: {e}")
        return

    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()
    _running = True

    # Register main-thread callback to process command queue safely
    mset.callbacks.onPeriodicUpdate = _process_queue

    _lbl_actions.text = str(len(_ACTIONS))
    _update_ui()

    print(f"[{PLUGIN_NAME}] ✓ Bridge running → http://{BRIDGE_HOST}:{BRIDGE_PORT}")
    print(f"[{PLUGIN_NAME}]   {len(_ACTIONS)} actions available")


def _stop_server():
    global _server, _running
    if not _running:
        return

    try:
        _server.shutdown()
    except Exception:
        pass

    _running = False
    _update_ui()
    print(f"[{PLUGIN_NAME}] Server stopped.")


def _on_shutdown():
    """Called by Toolbag when the plugin is shut down."""
    _stop_server()
    print(f"[{PLUGIN_NAME}] Plugin shut down.")


# Register shutdown cleanup
mset.callbacks.onShutdownPlugin = _on_shutdown

# ── Auto-start ────────────────────────────────────────────────────
_start_server()
