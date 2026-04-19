// import { useState, useEffect, useRef, useCallback } from "react";

// const API = "http://localhost:5000";

// const CLASS_COLORS = {
//   0: { live: "rgba(30,120,210,0.55)",   collapsed: "rgba(30,120,210,0.92)",  border: "#1e78d2", label: "water",      order: 2 },
//   1: { live: "rgba(60,180,80,0.55)",    collapsed: "rgba(60,180,80,0.92)",   border: "#3cb450", label: "transition", order: 3 },
//   2: { live: "rgba(220,60,60,0.55)",    collapsed: "rgba(220,60,60,0.92)",   border: "#dc3c3c", label: "urban",      order: 4 },
// };

// const STATUS_DOT = { live: "#4ade80", collapsed: "#f87171" };

// export default function HilbertViewer() {
//   const [zoom, setZoom] = useState(2);
//   const [lodData, setLodData] = useState(null);
//   const [segData, setSegData] = useState(null);
//   const [stats, setStats] = useState(null);
//   const [loading, setLoading] = useState(false);
//   const [error, setError] = useState(null);
//   const [hoveredTile, setHoveredTile] = useState(null);
//   const canvasRef = useRef(null);
//   const animRef = useRef({});

//   useEffect(() => {
//     fetch(`${API}/segmentation`)
//       .then(r => r.json())
//       .then(setSegData)
//       .catch(() => setError("Cannot reach tile server. Is it running on :5000?"));
//     fetch(`${API}/index_stats`)
//       .then(r => r.json())
//       .then(setStats)
//       .catch(() => {});
//   }, []);

//   const fetchLod = useCallback((z) => {
//     setLoading(true);
//     fetch(`${API}/lod?zoom=${z}`)
//       .then(r => r.json())
//       .then(d => { setLodData(d); setLoading(false); setError(null); })
//       .catch(() => { setError("LOD fetch failed — is tile_server.py running?"); setLoading(false); });
//   }, []);

//   useEffect(() => { fetchLod(zoom); }, [zoom, fetchLod]);
//     useEffect(() => {
//     if (!lodData || !segData || !canvasRef.current) return;
//     const canvas = canvasRef.current;
//     const ctx = canvas.getContext("2d");
//     const [imgW, imgH] = segData.image_size;

//     const scale = Math.min(canvas.width / imgW, canvas.height / imgH);
//     const offX = (canvas.width - imgW * scale) / 2;
//     const offY = (canvas.height - imgH * scale) / 2;

//     ctx.clearRect(0, 0, canvas.width, canvas.height);
//     ctx.fillStyle = "#0a0f1a";
//     ctx.fillRect(0, 0, canvas.width, canvas.height);

//     for (const tile of lodData.tiles) {
//         const { region_class, status, mean_color, hilbert_order, pixel_bbox } = tile;
//         if (!pixel_bbox) continue;

//         const [px0, py0, px1, py1] = pixel_bbox;
//         const x0 = offX + px0 * scale;
//         const y0 = offY + py0 * scale;
//         const tw = (px1 - px0) * scale;
//         const th = (py1 - py0) * scale;

//         const cfg = CLASS_COLORS[region_class] || CLASS_COLORS[2];

//         if (status === "collapsed") {
//         const [r, g, b] = mean_color;
//         ctx.fillStyle = `rgb(${Math.round(r)},${Math.round(g)},${Math.round(b)})`;
//         ctx.fillRect(x0, y0, tw, th);
//         ctx.fillStyle = "rgba(0,0,0,0.35)";
//         ctx.fillRect(x0, y0, tw, th);
//         } else {
//         ctx.fillStyle = cfg.live;
//         ctx.fillRect(x0, y0, tw, th);

//         if (hilbert_order >= 3) {
//             const subGrid = Math.pow(2, hilbert_order);
//             const sw = tw / subGrid;
//             const sh = th / subGrid;
//             ctx.strokeStyle = `${cfg.border}55`;
//             ctx.lineWidth = 0.4;
//             for (let sy = 0; sy <= subGrid; sy++) {
//             ctx.beginPath(); ctx.moveTo(x0, y0 + sy * sh); ctx.lineTo(x0 + tw, y0 + sy * sh); ctx.stroke();
//             }
//             for (let sx = 0; sx <= subGrid; sx++) {
//             ctx.beginPath(); ctx.moveTo(x0 + sx * sw, y0); ctx.lineTo(x0 + sx * sw, y0 + th); ctx.stroke();
//             }
//         }
//         }

//         ctx.strokeStyle = cfg.border;
//         ctx.lineWidth = status === "collapsed" ? 1.5 : 0.8;
//         ctx.strokeRect(x0 + 0.5, y0 + 0.5, tw - 1, th - 1);

//         if (tw > 22) {
//         ctx.fillStyle = "rgba(255,255,255,0.7)";
//         ctx.font = `${Math.min(9, tw / 5)}px monospace`;
//         ctx.fillText(`o${hilbert_order}`, x0 + 3, y0 + 11);
//         }
//     }

//     if (hoveredTile?.pixel_bbox) {
//         const [px0, py0, px1, py1] = hoveredTile.pixel_bbox;
//         ctx.strokeStyle = "#ffffff";
//         ctx.lineWidth = 2;
//         ctx.strokeRect(offX + px0 * scale, offY + py0 * scale, (px1 - px0) * scale, (py1 - py0) * scale);
//     }
//     }, [lodData, segData, hoveredTile]);


// const [bgImage, setBgImage] = useState(null);

// useEffect(() => {
//   const img = new Image();
//   img.crossOrigin = "anonymous";
//   img.onload = () => setBgImage(img);
//   img.src = `${API}/image`;
// }, []);

// const handleCanvasMouseMove = useCallback((e) => {
//   if (!lodData || !segData || !canvasRef.current) return;
//   const canvas = canvasRef.current;
//   const rect = canvas.getBoundingClientRect();
//   const mx = (e.clientX - rect.left) * (canvas.width / rect.width);
//   const my = (e.clientY - rect.top) * (canvas.height / rect.height);
//   const [imgW, imgH] = segData.image_size;
//   const scale = Math.min(canvas.width / imgW, canvas.height / imgH);
//   const offX = (canvas.width - imgW * scale) / 2;
//   const offY = (canvas.height - imgH * scale) / 2;

//   // convert mouse to image pixel space
//   const ix = (mx - offX) / scale;
//   const iy = (my - offY) / scale;

//   const found = lodData.tiles.find(t => {
//     if (!t.pixel_bbox) return false;
//     const [x0, y0, x1, y1] = t.pixel_bbox;
//     return ix >= x0 && ix < x1 && iy >= y0 && iy < y1;
//   });
//   setHoveredTile(found || null);
// }, [lodData, segData]);

//   const liveCount = lodData?.lod_stats?.live ?? 0;
//   const collCount = lodData?.lod_stats?.collapsed ?? 0;
//   const total = lodData?.lod_stats?.total ?? 1;
//   const classCounts = lodData ? { 0: { live: 0, collapsed: 0 }, 1: { live: 0, collapsed: 0 }, 2: { live: 0, collapsed: 0 } } : null;
//   if (lodData) for (const t of lodData.tiles) classCounts[t.region_class][t.status]++;

//   return (
//     <div style={{ background: "#0a0f1a", minHeight: "100vh", color: "#e2e8f0", fontFamily: "'JetBrains Mono', 'Fira Code', monospace", padding: "0" }}>
//       <div style={{ borderBottom: "1px solid #1e293b", padding: "12px 24px", display: "flex", alignItems: "center", gap: "16px" }}>
//         <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
//           <div style={{ width: 8, height: 8, borderRadius: "50%", background: error ? "#f87171" : "#4ade80", boxShadow: `0 0 6px ${error ? "#f87171" : "#4ade80"}` }} />
//           <span style={{ fontSize: 13, color: "#94a3b8", letterSpacing: "0.05em" }}>ADAPTIVE HILBERT LOD VIEWER</span>
//         </div>
//         <div style={{ marginLeft: "auto", display: "flex", gap: "16px", fontSize: 12, color: "#475569" }}>
//           {stats && <>
//             <span>{stats.total_sub_tiles?.toLocaleString()} sub-tiles</span>
//             <span>{stats.base_tiles} base tiles</span>
//           </>}
//         </div>
//       </div>

//       {error && (
//         <div style={{ margin: "12px 24px", padding: "10px 16px", background: "#1e0a0a", border: "1px solid #7f1d1d", borderRadius: 6, fontSize: 13, color: "#fca5a5" }}>
//           {error}
//         </div>
//       )}

//       <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 0, height: "calc(100vh - 57px)" }}>
//         <div style={{ position: "relative", padding: "16px" }}>
//           <canvas
//             ref={canvasRef}
//             width={800}
//             height={720}
//             onMouseMove={handleCanvasMouseMove}
//             onMouseLeave={() => setHoveredTile(null)}
//             style={{ width: "100%", height: "100%", display: "block", cursor: "crosshair", borderRadius: 6, border: "1px solid #1e293b" }}
//           />
//           {loading && (
//             <div style={{ position: "absolute", top: 24, left: 24, background: "rgba(10,15,26,0.85)", padding: "6px 12px", borderRadius: 4, fontSize: 12, color: "#94a3b8", border: "1px solid #1e293b" }}>
//               fetching LOD…
//             </div>
//           )}
//         </div>

//         <div style={{ borderLeft: "1px solid #1e293b", padding: "20px 16px", display: "flex", flexDirection: "column", gap: "20px", overflowY: "auto" }}>
//           <div>
//             <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 10 }}>ZOOM LEVEL</div>
//             <input
//               type="range" min={0} max={4} step={1} value={zoom}
//               onChange={e => setZoom(Number(e.target.value))}
//               style={{ width: "100%", accentColor: "#378add" }}
//             />
//             <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#475569", marginTop: 4 }}>
//               {[0,1,2,3,4].map(z => (
//                 <span key={z} style={{ color: z === zoom ? "#93c5fd" : "#475569", fontWeight: z === zoom ? 500 : 400 }}>{z}</span>
//               ))}
//             </div>
//             <div style={{ marginTop: 10, padding: "8px 12px", background: "#0f172a", borderRadius: 6, border: "1px solid #1e293b", fontSize: 13 }}>
//               <span style={{ color: "#475569" }}>zoom = </span>
//               <span style={{ color: "#93c5fd", fontWeight: 500 }}>{zoom}</span>
//               <span style={{ color: "#475569", marginLeft: 12 }}>
//                 {zoom === 0 ? "most collapsed" : zoom === 4 ? "finest detail" : ""}
//               </span>
//             </div>
//           </div>

//           <div>
//             <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 10 }}>LOD STATUS</div>
//             <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
//               {[
//                 { label: "live", count: liveCount, color: "#4ade80", bg: "#052e16" },
//                 { label: "collapsed", count: collCount, color: "#f87171", bg: "#2d0707" },
//               ].map(s => (
//                 <div key={s.label} style={{ background: s.bg, border: `1px solid ${s.color}33`, borderRadius: 6, padding: "10px", textAlign: "center" }}>
//                   <div style={{ fontSize: 22, fontWeight: 500, color: s.color }}>{s.count}</div>
//                   <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>{s.label}</div>
//                 </div>
//               ))}
//             </div>
//             <div style={{ marginTop: 8, height: 6, borderRadius: 3, background: "#1e293b", overflow: "hidden" }}>
//               <div style={{ height: "100%", width: `${total ? (liveCount / total) * 100 : 0}%`, background: "#4ade80", transition: "width 0.4s ease", borderRadius: 3 }} />
//             </div>
//             <div style={{ fontSize: 11, color: "#475569", marginTop: 4 }}>{total ? Math.round((liveCount / total) * 100) : 0}% live</div>
//           </div>

//           <div>
//             <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 10 }}>BY REGION CLASS</div>
//             {classCounts && Object.entries(CLASS_COLORS).map(([cls, cfg]) => {
//               const c = classCounts[cls];
//               return (
//                 <div key={cls} style={{ marginBottom: 10, padding: "10px 12px", background: "#0f172a", borderRadius: 6, borderLeft: `3px solid ${cfg.border}` }}>
//                   <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
//                     <span style={{ fontSize: 12, color: cfg.border, fontWeight: 500 }}>{cfg.label}</span>
//                     <span style={{ fontSize: 11, color: "#475569" }}>order {cfg.order} · {Math.pow(2, cfg.order)}×{Math.pow(2, cfg.order)} grid</span>
//                   </div>
//                   <div style={{ display: "flex", gap: 8, fontSize: 12 }}>
//                     <span style={{ color: "#4ade80" }}>{c.live} live</span>
//                     <span style={{ color: "#475569" }}>/</span>
//                     <span style={{ color: "#f87171" }}>{c.collapsed} collapsed</span>
//                   </div>
//                 </div>
//               );
//             })}
//           </div>

//           {hoveredTile && (
//             <div>
//               <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 10 }}>HOVERED TILE</div>
//               <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 6, padding: "12px", fontSize: 12 }}>
//                 {[
//                   ["pos", `(${hoveredTile.base_tx}, ${hoveredTile.base_ty})`],
//                   ["class", hoveredTile.class_name],
//                   ["hilbert order", hoveredTile.hilbert_order],
//                   ["sub-tiles", hoveredTile.sub_tile_count],
//                   ["entropy", hoveredTile.entropy?.toFixed(3)],
//                   ["status", hoveredTile.status],
//                 ].map(([k, v]) => (
//                   <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px solid #0f172a" }}>
//                     <span style={{ color: "#475569" }}>{k}</span>
//                     <span style={{ color: hoveredTile.status === "live" ? "#4ade80" : "#f87171" }}>{v}</span>
//                   </div>
//                 ))}
//                 <div style={{ marginTop: 8, display: "flex", gap: 4, alignItems: "center" }}>
//                   <span style={{ fontSize: 11, color: "#475569" }}>mean color</span>
//                   <div style={{
//                     marginLeft: "auto", width: 24, height: 16, borderRadius: 3,
//                     background: hoveredTile.mean_color ? `rgb(${hoveredTile.mean_color.map(Math.round).join(",")})` : "#333"
//                   }} />
//                 </div>
//               </div>
//             </div>
//           )}

//           <div style={{ marginTop: "auto" }}>
//             <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 8 }}>LEGEND</div>
//             {Object.entries(CLASS_COLORS).map(([cls, cfg]) => (
//               <div key={cls} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
//                 <div style={{ width: 12, height: 12, borderRadius: 2, background: cfg.live, border: `1px solid ${cfg.border}` }} />
//                 <span style={{ fontSize: 12, color: "#64748b" }}>{cfg.label} · live</span>
//                 <div style={{ width: 12, height: 12, borderRadius: 2, background: cfg.collapsed, border: `1px solid ${cfg.border}`, marginLeft: 8 }} />
//                 <span style={{ fontSize: 12, color: "#64748b" }}>collapsed</span>
//               </div>
//             ))}
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// }

import { useState, useEffect, useRef, useCallback } from "react";

const API = "http://localhost:5000";

const CLASS_COLORS = {
  0: { live: "rgba(30,120,210,0.18)",  collapsed: "rgba(30,120,210,0.82)",  border: "#1e78d2", label: "water",      order: 2 },
  1: { live: "rgba(60,180,80,0.18)",   collapsed: "rgba(60,180,80,0.82)",   border: "#3cb450", label: "transition", order: 3 },
  2: { live: "rgba(220,60,60,0.18)",   collapsed: "rgba(220,60,60,0.82)",   border: "#dc3c3c", label: "urban",      order: 4 },
};

export default function HilbertViewer() {
  const [zoom, setZoom]           = useState(2);
  const [lodData, setLodData]     = useState(null);
  const [segData, setSegData]     = useState(null);
  const [stats, setStats]         = useState(null);
  const [bgImage, setBgImage]     = useState(null);   // MUST be declared before the draw useEffect
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);
  const [hoveredTile, setHovered] = useState(null);
  const canvasRef = useRef(null);

  // load segmentation metadata + index stats once
  useEffect(() => {
    fetch(`${API}/segmentation`)
      .then(r => r.json()).then(setSegData)
      .catch(() => setError("Cannot reach tile server on :5000"));
    fetch(`${API}/index_stats`)
      .then(r => r.json()).then(setStats)
      .catch(() => {});
  }, []);

  // load background satellite image once
  useEffect(() => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload  = () => setBgImage(img);
    img.onerror = () => console.warn("Could not load /image — add the /image endpoint to tile_server.py");
    img.src = `${API}/image`;
  }, []);

  // fetch LOD data whenever zoom changes
  const fetchLod = useCallback((z) => {
    setLoading(true);
    fetch(`${API}/lod?zoom=${z}`)
      .then(r => r.json())
      .then(d => { setLodData(d); setLoading(false); setError(null); })
      .catch(() => { setError("LOD fetch failed"); setLoading(false); });
  }, []);
  useEffect(() => { fetchLod(zoom); }, [zoom, fetchLod]);

  // draw canvas — bgImage is in deps so it redraws once image loads
  useEffect(() => {
    if (!lodData || !segData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx    = canvas.getContext("2d");
    const [imgW, imgH] = segData.image_size;

    const scale = Math.min(canvas.width / imgW, canvas.height / imgH);
    const drawW = imgW * scale;
    const drawH = imgH * scale;
    const offX  = (canvas.width  - drawW) / 2;
    const offY  = (canvas.height - drawH) / 2;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#0a0f1a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 1. satellite image as background
    if (bgImage) {
      ctx.drawImage(bgImage, offX, offY, drawW, drawH);
    }

    // 2. tile overlays
    for (const tile of lodData.tiles) {
      const { region_class, status, mean_color, hilbert_order, pixel_bbox } = tile;
      if (!pixel_bbox) continue;

      const [px0, py0, px1, py1] = pixel_bbox;
      const x0 = offX + px0 * scale;
      const y0 = offY + py0 * scale;
      const tw  = (px1 - px0) * scale;
      const th  = (py1 - py0) * scale;
      const cfg = CLASS_COLORS[region_class] || CLASS_COLORS[2];

      if (status === "collapsed") {
        const [r, g, b] = mean_color;
        ctx.fillStyle = `rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},0.85)`;
        ctx.fillRect(x0, y0, tw, th);
        ctx.fillStyle = "rgba(0,0,0,0.22)";
        ctx.fillRect(x0, y0, tw, th);
      } else {
        // light tint — image shows through
        ctx.fillStyle = cfg.live;
        ctx.fillRect(x0, y0, tw, th);

        // sub-tile grid lines
        if (hilbert_order >= 3) {
          const subGrid = Math.pow(2, hilbert_order);
          const sw = tw / subGrid;
          const sh = th / subGrid;
          ctx.strokeStyle = `${cfg.border}40`;
          ctx.lineWidth = 0.3;
          for (let sy = 0; sy <= subGrid; sy++) {
            ctx.beginPath(); ctx.moveTo(x0, y0 + sy * sh); ctx.lineTo(x0 + tw, y0 + sy * sh); ctx.stroke();
          }
          for (let sx = 0; sx <= subGrid; sx++) {
            ctx.beginPath(); ctx.moveTo(x0 + sx * sw, y0); ctx.lineTo(x0 + sx * sw, y0 + th); ctx.stroke();
          }
        }
      }

      // tile border
      ctx.strokeStyle = cfg.border;
      ctx.lineWidth   = status === "collapsed" ? 2 : 0.9;
      ctx.strokeRect(x0 + 0.5, y0 + 0.5, tw - 1, th - 1);

      // order label
      if (tw > 24) {
        ctx.fillStyle = status === "collapsed" ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.8)";
        ctx.font = `bold ${Math.min(10, tw / 5)}px monospace`;
        ctx.fillText(`o${hilbert_order}`, x0 + 4, y0 + 13);
      }
    }

    // 3. hover highlight
    if (hoveredTile?.pixel_bbox) {
      const [px0, py0, px1, py1] = hoveredTile.pixel_bbox;
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth   = 2.5;
      ctx.strokeRect(offX + px0 * scale, offY + py0 * scale, (px1-px0)*scale, (py1-py0)*scale);
    }
  }, [lodData, segData, hoveredTile, bgImage]);  // bgImage here is critical

  const handleMouseMove = useCallback((e) => {
    if (!lodData || !segData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const rect   = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (canvas.width  / rect.width);
    const my = (e.clientY - rect.top)  * (canvas.height / rect.height);
    const [imgW, imgH] = segData.image_size;
    const scale = Math.min(canvas.width / imgW, canvas.height / imgH);
    const offX  = (canvas.width  - imgW * scale) / 2;
    const offY  = (canvas.height - imgH * scale) / 2;
    const ix = (mx - offX) / scale;
    const iy = (my - offY) / scale;
    const found = lodData.tiles.find(t => {
      if (!t.pixel_bbox) return false;
      const [x0, y0, x1, y1] = t.pixel_bbox;
      return ix >= x0 && ix < x1 && iy >= y0 && iy < y1;
    });
    setHovered(found || null);
  }, [lodData, segData]);

  const liveCount   = lodData?.lod_stats?.live      ?? 0;
  const collCount   = lodData?.lod_stats?.collapsed  ?? 0;
  const total       = lodData?.lod_stats?.total      ?? 1;
  const classCounts = lodData
    ? { 0:{live:0,collapsed:0}, 1:{live:0,collapsed:0}, 2:{live:0,collapsed:0} }
    : null;
  if (lodData) for (const t of lodData.tiles) classCounts[t.region_class][t.status]++;

  return (
    <div style={{ background: "#0a0f1a", minHeight: "100vh", color: "#e2e8f0",
                  fontFamily: "'JetBrains Mono','Fira Code',monospace" }}>

      <div style={{ borderBottom: "1px solid #1e293b", padding: "12px 24px",
                    display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%",
                        background: error ? "#f87171" : "#4ade80",
                        boxShadow: `0 0 6px ${error ? "#f87171" : "#4ade80"}` }} />
          <span style={{ fontSize: 13, color: "#94a3b8", letterSpacing: "0.05em" }}>
            ADAPTIVE HILBERT LOD VIEWER
          </span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 16, fontSize: 12, color: "#475569" }}>
          {!bgImage && <span style={{ color: "#f59e0b" }}>⟳ loading image…</span>}
          {stats && <>
            <span>{stats.total_sub_tiles?.toLocaleString()} sub-tiles</span>
            <span>{stats.base_tiles} base tiles</span>
          </>}
        </div>
      </div>

      {error && (
        <div style={{ margin: "12px 24px", padding: "10px 16px", background: "#1e0a0a",
                      border: "1px solid #7f1d1d", borderRadius: 6, fontSize: 13, color: "#fca5a5" }}>
          {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", height: "calc(100vh - 57px)" }}>

        <div style={{ position: "relative", padding: 16 }}>
          <canvas ref={canvasRef} width={800} height={720}
            onMouseMove={handleMouseMove}
            onMouseLeave={() => setHovered(null)}
            style={{ width: "100%", height: "100%", display: "block",
                     cursor: "crosshair", borderRadius: 6, border: "1px solid #1e293b" }} />
          {loading && (
            <div style={{ position: "absolute", top: 24, left: 24,
                          background: "rgba(10,15,26,0.85)", padding: "6px 12px",
                          borderRadius: 4, fontSize: 12, color: "#94a3b8", border: "1px solid #1e293b" }}>
              fetching LOD…
            </div>
          )}
        </div>

        <div style={{ borderLeft: "1px solid #1e293b", padding: "20px 16px",
                      display: "flex", flexDirection: "column", gap: 20, overflowY: "auto" }}>

          <div>
            <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 10 }}>ZOOM LEVEL</div>
            <input type="range" min={0} max={4} step={1} value={zoom}
              onChange={e => setZoom(Number(e.target.value))}
              style={{ width: "100%", accentColor: "#378add" }} />
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#475569", marginTop: 4 }}>
              {[0,1,2,3,4].map(z => (
                <span key={z} style={{ color: z===zoom ? "#93c5fd" : "#475569", fontWeight: z===zoom ? 500 : 400 }}>{z}</span>
              ))}
            </div>
            <div style={{ marginTop: 10, padding: "8px 12px", background: "#0f172a",
                          borderRadius: 6, border: "1px solid #1e293b", fontSize: 13 }}>
              <span style={{ color: "#475569" }}>zoom = </span>
              <span style={{ color: "#93c5fd", fontWeight: 500 }}>{zoom}</span>
              <span style={{ color: "#475569", marginLeft: 12 }}>
                {zoom === 0 ? "most collapsed" : zoom === 4 ? "finest detail" : ""}
              </span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 10 }}>LOD STATUS</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {[
                { label: "live",      count: liveCount, color: "#4ade80", bg: "#052e16" },
                { label: "collapsed", count: collCount, color: "#f87171", bg: "#2d0707" },
              ].map(s => (
                <div key={s.label} style={{ background: s.bg, border: `1px solid ${s.color}33`,
                                            borderRadius: 6, padding: 10, textAlign: "center" }}>
                  <div style={{ fontSize: 22, fontWeight: 500, color: s.color }}>{s.count}</div>
                  <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>{s.label}</div>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 8, height: 6, borderRadius: 3, background: "#1e293b", overflow: "hidden" }}>
              <div style={{ height: "100%", background: "#4ade80", borderRadius: 3,
                            width: `${total ? (liveCount/total)*100 : 0}%`, transition: "width 0.4s ease" }} />
            </div>
            <div style={{ fontSize: 11, color: "#475569", marginTop: 4 }}>
              {total ? Math.round((liveCount/total)*100) : 0}% live
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 10 }}>BY REGION CLASS</div>
            {classCounts && Object.entries(CLASS_COLORS).map(([cls, cfg]) => {
              const c = classCounts[cls];
              return (
                <div key={cls} style={{ marginBottom: 10, padding: "10px 12px", background: "#0f172a",
                                        borderRadius: 6, borderLeft: `3px solid ${cfg.border}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: cfg.border, fontWeight: 500 }}>{cfg.label}</span>
                    <span style={{ fontSize: 11, color: "#475569" }}>order {cfg.order} · {Math.pow(2,cfg.order)}×{Math.pow(2,cfg.order)}</span>
                  </div>
                  <div style={{ display: "flex", gap: 8, fontSize: 12 }}>
                    <span style={{ color: "#4ade80" }}>{c.live} live</span>
                    <span style={{ color: "#475569" }}>/</span>
                    <span style={{ color: "#f87171" }}>{c.collapsed} collapsed</span>
                  </div>
                </div>
              );
            })}
          </div>

          {hoveredTile && (
            <div>
              <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 10 }}>HOVERED TILE</div>
              <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 6, padding: 12, fontSize: 12 }}>
                {[
                  ["pos",           `(${hoveredTile.base_tx}, ${hoveredTile.base_ty})`],
                  ["class",         hoveredTile.class_name],
                  ["hilbert order", hoveredTile.hilbert_order],
                  ["sub-tiles",     hoveredTile.sub_tile_count],
                  ["entropy",       hoveredTile.entropy?.toFixed(3)],
                  ["status",        hoveredTile.status],
                ].map(([k, v]) => (
                  <div key={k} style={{ display: "flex", justifyContent: "space-between",
                                        padding: "3px 0", borderBottom: "1px solid #1e293b" }}>
                    <span style={{ color: "#475569" }}>{k}</span>
                    <span style={{ color: hoveredTile.status==="live" ? "#4ade80" : "#f87171" }}>{v}</span>
                  </div>
                ))}
                <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ fontSize: 11, color: "#475569" }}>mean color</span>
                  <div style={{ marginLeft: "auto", width: 24, height: 16, borderRadius: 3,
                                background: hoveredTile.mean_color
                                  ? `rgb(${hoveredTile.mean_color.map(Math.round).join(",")})`
                                  : "#333" }} />
                </div>
              </div>
            </div>
          )}

          <div style={{ marginTop: "auto" }}>
            <div style={{ fontSize: 11, color: "#475569", letterSpacing: "0.1em", marginBottom: 8 }}>LEGEND</div>
            {Object.entries(CLASS_COLORS).map(([cls, cfg]) => (
              <div key={cls} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                <div style={{ width: 12, height: 12, borderRadius: 2, border: `2px solid ${cfg.border}`, background: "transparent" }} />
                <span style={{ fontSize: 11, color: "#64748b" }}>{cfg.label} live — image visible</span>
              </div>
            ))}
            {Object.entries(CLASS_COLORS).map(([cls, cfg]) => (
              <div key={`c${cls}`} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                <div style={{ width: 12, height: 12, borderRadius: 2, background: cfg.border }} />
                <span style={{ fontSize: 11, color: "#64748b" }}>{cfg.label} collapsed — avg color</span>
              </div>
            ))}
          </div>

        </div>
      </div>
    </div>
  );
}