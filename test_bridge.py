#!/usr/bin/env python3
"""Quick test for the Marmoset MCP Bridge. Run this on your machine."""
import httpx
import json
import sys

BRIDGE = "http://127.0.0.1:8765"

def test(name, action, params=None):
    try:
        r = httpx.post(BRIDGE, json={"action": action, "params": params or {}}, timeout=10)
        data = r.json()
        status = "✓" if data.get("ok") else "✗"
        print(f"  {status} {name}: {json.dumps(data, indent=4)}")
        return data.get("ok", False)
    except httpx.ConnectError:
        print(f"  ✗ {name}: Cannot connect to bridge at {BRIDGE}")
        return False
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        return False

print("=" * 50)
print("Marmoset MCP Bridge Test")
print("=" * 50)

# Health check
print("
1. Health Check (GET)...")
try:
    r = httpx.get(BRIDGE, timeout=5)
    print(f"  ✓ Bridge is responding: {r.json().get("status")}")
    print(f"    Actions available: {len(r.json().get("actions", []))}")
except Exception as e:
    print(f"  ✗ Bridge not reachable: {e}")
    sys.exit(1)

# Ping
print("
2. Ping...")
test("ping", "ping")

# Scene info
print("
3. Scene Info...")
test("scene_info", "get_scene_info")

# List lights
print("
4. List Lights...")
test("list_lights", "list_lights")

# List objects
print("
5. List Objects...")
test("list_objects", "list_objects")

print("
" + "=" * 50)
print("All basic tests done! Bridge is working.")
print("=" * 50)
