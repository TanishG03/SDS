"""
sage2_display_coordinator.py
Demonstrates the SAGE2 distributed display middleware from Renambot et al. (2015).

FIXES over previous version:
  - Fetches a real high-res image to act as the collaborative canvas.
  - Generates a physical visualization of the 4x2 Display Wall.
  - Visually simulates LOD degradation on peripheral panels (pixelation).
  - Draws physical bezels between panels.
  - Overlays concurrent multi-user pointers onto the display wall.
"""

import math
import time
import queue
import threading
import logging
import os
import urllib.request
from io import BytesIO
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s"
)
log = logging.getLogger("SAGE2")

# ── Step 1: Fetch visual canvas ──────────────────────────────────

def load_local_canvas(file_path: str) -> Image.Image:
    """Loads a high-res image from the local disk to act as the shared map/canvas."""
    log.info(f"Loading visual canvas from local file: {file_path}...")
    try:
        img = Image.open(file_path).convert("RGB")
        log.info(f"Canvas loaded: {img.width}×{img.height} px")
        return img
    except FileNotFoundError:
        log.error(f"Could not find '{file_path}'. Please check the file name and path.")
        raise

def fetch_canvas_image() -> Image.Image:
    """Fetches a high-res image to act as our shared map/canvas."""
    url = (
        "https://d.ibtimes.co.uk/en/full/266566/"
        "stunning-images-earth-captured-geoeye-1-satellite.jpg"
        "?w=1920&h=1080&l=50&t=20&q=88&f=a469a52edad7c3e4c74c00ebb75c6ead"
    )
    log.info("Fetching visual canvas for the display wall...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    img = Image.open(BytesIO(data)).convert("RGB")
    log.info(f"Canvas downloaded: {img.width}×{img.height} px")
    return img

# ── Data Structures ──────────────────────────────────────────────

@dataclass
class Viewport:
    north: float; south: float
    east:  float; west:  float
    zoom:  int

    @property
    def center_lat(self): return (self.north + self.south) / 2
    @property
    def center_lon(self): return (self.east  + self.west)  / 2
    @property
    def lat_span(self):   return self.north - self.south
    @property
    def lon_span(self):   return self.east  - self.west

@dataclass
class PanelAssignment:
    panel_id:      str
    row:           int
    col:           int
    north:         float; south: float
    east:          float; west:  float
    base_zoom:     int
    effective_zoom: int
    lod_reduction: int

    @property
    def center_lat(self): return (self.north + self.south) / 2
    @property
    def center_lon(self): return (self.east  + self.west)  / 2
    @property
    def lod_label(self):
        return "near center" if self.lod_reduction == 0 else "peripheral"

@dataclass
class SAGEPointer:
    user_id:      str
    display_name: str
    color:        str
    pos_x: float = 0.5  # Normalized 0.0 to 1.0 across total wall width
    pos_y: float = 0.5  # Normalized 0.0 to 1.0 across total wall height

# ── Synchronization Barrier ──────────────────────────────────────

class SyncBarrier:
    def __init__(self, panel_ids: List[str], on_ready):
        self._needed  = set(panel_ids)
        self._done    = set()
        self._lock    = threading.Lock()
        self._on_ready = on_ready

    def signal(self, panel_id: str):
        with self._lock:
            self._done.add(panel_id)
            if self._done >= self._needed:
                self._on_ready(list(self._done))
                self._done.clear()

# ── SAGE2 Server ─────────────────────────────────────────────────

class SAGE2Server:
    LOD_STEP_DEG   = 15.0   # Degrees per LOD reduction step
    MAX_LOD_REDUCE = 2

    def __init__(self, panels_x: int, panels_y: int,
                 panel_w_px: int, panel_h_px: int, canvas_img: Image.Image):
        self.panels_x    = panels_x
        self.panels_y    = panels_y
        self.panel_w_px  = panel_w_px
        self.panel_h_px  = panel_h_px
        self.canvas_img  = canvas_img

        self.viewport = Viewport(
            north=35.0, south=25.0,
            east=82.0,  west=72.0,
            zoom=2
        )

        self.pointers:      Dict[str, SAGEPointer] = {}
        self.msg_log:       List[Dict]             = []
        self.frames_synced = 0
        self._sync_event   = threading.Event()

        all_ids = [f"P{r:02d}{c:02d}"
                   for r in range(panels_y)
                   for c in range(panels_x)]
        self.barrier = SyncBarrier(all_ids, self._on_all_ready)

        total_w = panels_x * panel_w_px
        total_h = panels_y * panel_h_px
        log.info(f"SAGE2 Server initialized")
        log.info(f"Display wall specs: {panels_x}×{panels_y} panels = {total_w}×{total_h} px total")

    def _broadcast(self, msg_type: str, payload: Dict, user_id: str = "server"):
        msg = {"type": msg_type, "from": user_id, "payload": payload, "ts": time.time()}
        self.msg_log.append(msg)

    def connect_user(self, user_id: str, name: str, color: str, start_x: float, start_y: float) -> SAGEPointer:
        p = SAGEPointer(user_id, name, color, start_x, start_y)
        self.pointers[user_id] = p
        self._broadcast("user_joined", {"user_id": user_id, "name": name, "color": color})
        log.info(f"[SAGE2] User joined: {name} ({user_id})")
        return p

    def _decompose(self) -> List[PanelAssignment]:
        lat_step = self.viewport.lat_span / self.panels_y
        lon_step = self.viewport.lon_span / self.panels_x
        result   = []
        for row in range(self.panels_y):
            for col in range(self.panels_x):
                pid = f"P{row:02d}{col:02d}"
                result.append(PanelAssignment(
                    panel_id=pid, row=row, col=col,
                    north=self.viewport.north - row       * lat_step,
                    south=self.viewport.north - (row + 1) * lat_step,
                    east =self.viewport.west  + (col + 1) * lon_step,
                    west =self.viewport.west  + col       * lon_step,
                    base_zoom=self.viewport.zoom,
                    effective_zoom=self.viewport.zoom,
                    lod_reduction=0
                ))
        return result

    def _apply_lod(self, panels: List[PanelAssignment], clat: float, clon: float) -> List[PanelAssignment]:
        for p in panels:
            dist = math.sqrt((p.center_lat - clat)**2 + (p.center_lon - clon)**2)
            red  = min(self.MAX_LOD_REDUCE, int(dist / self.LOD_STEP_DEG))
            p.lod_reduction  = red
            p.effective_zoom = max(0, p.base_zoom - red)
        return panels

    def _print_lod_table(self, panels: List[PanelAssignment]):
        log.info("\n  Panel-by-panel LOD Assignments:")
        log.info(f"  {'Panel':<8}{'Row':<5}{'Col':<5}{'Base Zoom':<12}{'Eff.Zoom':<10}{'LOD Reduction'}")
        log.info("  " + "-" * 55)
        for p in panels:
            log.info(f"  {p.panel_id:<8}{p.row:<5}{p.col:<5}{p.base_zoom:<12}{p.effective_zoom:<10}{p.lod_reduction}    ({p.lod_label})")
        log.info("")

    def zoom(self, new_zoom: int, clat: float, clon: float, user_id: str = "system"):
        old = self.viewport.zoom
        self.viewport.zoom = new_zoom
        hl = self.viewport.lat_span / 2
        hl_lon = self.viewport.lon_span / 2
        self.viewport.north = clat + hl
        self.viewport.south = clat - hl
        self.viewport.east  = clon + hl_lon
        self.viewport.west  = clon - hl_lon

        panels = self._apply_lod(self._decompose(), clat, clon)
        name = self.pointers[user_id].display_name if user_id in self.pointers else user_id
        log.info(f"\n[SAGE2] Zoom by {name}: {old}→{new_zoom}, center=({clat:.2f}, {clon:.2f})")
        self._print_lod_table(panels)
        self._broadcast("zoom", {"old": old, "new": new_zoom, "center": (clat, clon)}, user_id)
        return panels

    def pan(self, dlat: float, dlon: float, user_id: str = "system"):
        self.viewport.north += dlat
        self.viewport.south += dlat
        self.viewport.east  += dlon
        self.viewport.west  += dlon
        name = self.pointers[user_id].display_name if user_id in self.pointers else user_id
        log.info(f"[SAGE2] Pan by {name}: Δlat={dlat:+.2f}° Δlon={dlon:+.2f}°")
        self._broadcast("pan", {"dlat": dlat, "dlon": dlon}, user_id)

    def _on_all_ready(self, panel_ids: List[str]):
        self.frames_synced += 1
        self._broadcast("sync_draw", {"frame": self.frames_synced, "panels": len(panel_ids)})
        self._sync_event.set()

    def _render_panel(self, panel_id: str, delay_ms: float):
        time.sleep(delay_ms / 1000.0)
        self.barrier.signal(panel_id)

    def render_synchronized_frame(self):
        self._sync_event.clear()
        all_ids = [f"P{r:02d}{c:02d}" for r in range(self.panels_y) for c in range(self.panels_x)]
        threads = []
        for i, pid in enumerate(all_ids):
            delay = 8 + (i % 4) * 2.5
            t = threading.Thread(target=self._render_panel, args=(pid, delay), daemon=True)
            threads.append(t)

        log.info("[SAGE2] Triggering synchronized render across all panels...")
        for t in threads: t.start()
        for t in threads: t.join()

        ok = self._sync_event.wait(timeout=5.0)
        if ok:
            log.info(f"[SAGE2] ✓ All panels ready — synchronized draw event fired (frame {self.frames_synced})")
        else:
            log.warning("[SAGE2] ✗ Sync timeout")

    # ── Physical Wall Visualization ──────────────────────────────

    def visualize_display_wall(self, current_panels: List[PanelAssignment]):
        """Creates a visual output of the display wall, showing LOD and users."""
        log.info("\n  Rendering physical display wall visualization...")
        
        # Determine panel dimensions based on the source image
        img_w, img_h = self.canvas_img.size
        pw = img_w // self.panels_x
        ph = img_h // self.panels_y
        
        bezel = 12 # Pixels for the black bezel between screens
        wall_w = (pw * self.panels_x) + (bezel * (self.panels_x + 1))
        wall_h = (ph * self.panels_y) + (bezel * (self.panels_y + 1))
        
        wall_canvas = Image.new("RGB", (wall_w, wall_h), (20, 20, 20)) # Dark wall background
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except Exception:
            font = ImageFont.load_default()

        # 1. Decompose and render each panel
        for p in current_panels:
            # Crop the exact section of the main image for this panel
            left = p.col * pw
            top  = p.row * ph
            panel_crop = self.canvas_img.crop((left, top, left + pw, top + ph))
            
            # SIMULATE LOD: If peripheral, downsample to simulate low-res tiles, then scale back up
            if p.lod_reduction > 0:
                scale_factor = 2 ** p.lod_reduction
                low_res = panel_crop.resize((pw // scale_factor, ph // scale_factor), Image.LANCZOS)
                panel_crop = low_res.resize((pw, ph), Image.NEAREST) # Nearest to show pixelation

            # Paste into wall canvas with bezel offsets
            paste_x = bezel + (p.col * (pw + bezel))
            paste_y = bezel + (p.row * (ph + bezel))
            wall_canvas.paste(panel_crop, (paste_x, paste_y))
            
            # Draw Panel ID label
            draw = ImageDraw.Draw(wall_canvas)
            draw.rectangle([paste_x, paste_y, paste_x + 60, paste_y + 25], fill=(0, 0, 0, 180))
            draw.text((paste_x + 5, paste_y + 4), p.panel_id, fill=(255, 255, 255), font=font)

        # 2. Draw Remote Users / Pointers
        draw = ImageDraw.Draw(wall_canvas)
        for uid, pointer in self.pointers.items():
            # Convert normalized 0-1 coordinates to wall pixel coordinates
            px = int(pointer.pos_x * wall_w)
            py = int(pointer.pos_y * wall_h)
            
            # Draw cursor (circle)
            r = 8
            draw.ellipse([px - r, py - r, px + r, py + r], fill=pointer.color, outline="white", width=2)
            
            # Draw cursor tag
            draw.rectangle([px + 12, py, px + 110, py + 24], fill=pointer.color)
            draw.text((px + 16, py + 4), pointer.display_name, fill="white", font=font)

        out_path = "sage2_display_wall_sim.png"
        wall_canvas.save(out_path)
        log.info(f"  Visualization saved: {os.path.abspath(out_path)}")
        
        # Display if possible
        try:
            wall_canvas.show()
        except:
            pass

# ── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    
    # 1. Fetch the canvas image
    canvas_image = load_local_canvas("test1.jpg")
    
    # 2. Initialize the Server (4×2 panels)
    server = SAGE2Server(
        panels_x=4, panels_y=2,
        panel_w_px=1920, panel_h_px=1080,
        canvas_img=canvas_image
    )

    # 3. Connect analysts at different coordinates
    server.connect_user("analyst1", "Dr. Sharma", "#E63946", start_x=0.4, start_y=0.4)
    server.connect_user("analyst2", "Dr. Chen",   "#457B9D", start_x=0.8, start_y=0.6)

    # 4. Zoom interaction (triggering LOD logic)
    current_panels = server.zoom(new_zoom=4, clat=28.60, clon=77.20, user_id="analyst1")
    # 5. Synchronized frame render across all 8 panels
    server.render_synchronized_frame()

    # 6. Generate the visual output!
    server.visualize_display_wall(current_panels)