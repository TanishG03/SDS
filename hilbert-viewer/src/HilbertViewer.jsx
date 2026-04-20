
// import { useState, useEffect, useRef, useCallback } from "react";

// const API = "http://localhost:5000";

// const CLASS_CFG = {
//   0: { live: "rgba(30,120,210,0.15)",  collapsed: "rgba(30,120,210,0.80)",  border: "#1e78d2", label: "water",      order: 2 },
//   1: { live: "rgba(60,180,80,0.15)",   collapsed: "rgba(60,180,80,0.80)",   border: "#3cb450", label: "transition", order: 3 },
//   2: { live: "rgba(220,60,60,0.15)",   collapsed: "rgba(220,60,60,0.80)",   border: "#dc3c3c", label: "urban",      order: 4 },
// };

// // ── tiny reusable components ─────────────────────────────────────
// const Mono = ({ children, color = "#94a3b8" }) => (
//   <span style={{ fontFamily: "monospace", color, fontSize: 12 }}>{children}</span>
// );

// const Row = ({ label, value, color = "#e2e8f0" }) => (
//   <div style={{ display:"flex", justifyContent:"space-between", padding:"3px 0",
//                 borderBottom:"1px solid #1e293b", fontSize:12 }}>
//     <span style={{ color:"#475569" }}>{label}</span>
//     <span style={{ color }}>{value}</span>
//   </div>
// );

// const SectionLabel = ({ children }) => (
//   <div style={{ fontSize:10, color:"#475569", letterSpacing:"0.1em",
//                 marginBottom:8, marginTop:16, textTransform:"uppercase" }}>
//     {children}
//   </div>
// );

// // ── animated counter ──────────────────────────────────────────────
// function useCountUp(target, duration = 600) {
//   const [val, setVal] = useState(0);
//   useEffect(() => {
//     if (target === 0) { setVal(0); return; }
//     let start = null;
//     const from = 0;
//     const step = ts => {
//       if (!start) start = ts;
//       const p = Math.min((ts - start) / duration, 1);
//       setVal(Math.round(from + (target - from) * p));
//       if (p < 1) requestAnimationFrame(step);
//     };
//     requestAnimationFrame(step);
//   }, [target, duration]);
//   return val;
// }

// // ── SpeedupBar ────────────────────────────────────────────────────
// function SpeedupBar({ hilbert_ms, naive_ms, speedup }) {
//   const frac = hilbert_ms / naive_ms;
//   return (
//     <div style={{ marginTop:4 }}>
//       <div style={{ fontSize:11, color:"#475569", marginBottom:6 }}>
//         scan time comparison
//       </div>
//       <div style={{ marginBottom:6 }}>
//         <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4 }}>
//           <div style={{ width:80, fontSize:11, color:"#4ade80", textAlign:"right" }}>hilbert</div>
//           <div style={{ flex:1, background:"#1e293b", borderRadius:3, height:14, overflow:"hidden" }}>
//             <div style={{ width:`${frac*100}%`, height:"100%", background:"#4ade80",
//                           borderRadius:3, transition:"width 0.6s ease",
//                           display:"flex", alignItems:"center", justifyContent:"flex-end", paddingRight:4 }}>
//               <span style={{ fontSize:9, color:"#052e16", fontWeight:700 }}>
//                 {hilbert_ms < 0.5 ? `${(hilbert_ms*1000).toFixed(0)}µs` : `${hilbert_ms.toFixed(1)}ms`}
//               </span>
//             </div>
//           </div>
//         </div>
//         <div style={{ display:"flex", alignItems:"center", gap:8 }}>
//           <div style={{ width:80, fontSize:11, color:"#f87171", textAlign:"right" }}>naive</div>
//           <div style={{ flex:1, background:"#1e293b", borderRadius:3, height:14, overflow:"hidden" }}>
//             <div style={{ width:"100%", height:"100%", background:"#f87171",
//                           borderRadius:3, display:"flex", alignItems:"center",
//                           justifyContent:"flex-end", paddingRight:4 }}>
//               <span style={{ fontSize:9, color:"#450a0a", fontWeight:700 }}>
//                 {naive_ms.toFixed(1)}ms
//               </span>
//             </div>
//           </div>
//         </div>
//       </div>
//       <div style={{ textAlign:"center", padding:"8px 0", background:"#0f172a",
//                     borderRadius:6, border:"1px solid #1e293b", marginTop:8 }}>
//         <span style={{ fontSize:22, fontWeight:700, color:"#fbbf24" }}>{speedup.toFixed(1)}×</span>
//         <span style={{ fontSize:11, color:"#475569", marginLeft:6 }}>faster</span>
//       </div>
//     </div>
//   );
// }

// // ── QueryPanel ────────────────────────────────────────────────────
// function QueryPanel({ query, onClose }) {
//   const hExamined = useCountUp(query?.hilbert_result?.examined ?? 0);
//   const nExamined = useCountUp(query?.naive_result?.examined ?? 0);

//   if (!query) return null;
//   const { hilbert_result: hr, naive_result: nr, speedup,
//           tiles_saved, pct_skipped, viewport_bbox, click_point, zoom } = query;

//   return (
//     <div style={{ background:"#0f172a", border:"1px solid #1e293b",
//                   borderRadius:8, padding:"14px 14px 10px" }}>
//       <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8 }}>
//         <span style={{ fontSize:11, color:"#475569", letterSpacing:"0.08em" }}>QUERY RESULT</span>
//         <button onClick={onClose}
//           style={{ background:"none", border:"none", color:"#475569",
//                    cursor:"pointer", fontSize:16, lineHeight:1, padding:0 }}>×</button>
//       </div>

//       <Row label="click" value={`(${click_point.map(v=>Math.round(v)).join(", ")})`} />
//       <Row label="zoom"  value={zoom} />
//       <Row label="viewport"
//            value={`${Math.round(viewport_bbox[2]-viewport_bbox[0])}×${Math.round(viewport_bbox[3]-viewport_bbox[1])}px`} />

//       <SectionLabel>hilbert range scan</SectionLabel>
//       <Row label="tiles found"    value={hr.count}                    color="#4ade80" />
//       <Row label="entries scanned" value={hExamined.toLocaleString()} color="#4ade80" />
//       <Row label="time"
//            value={hr.time_ms < 0.5 ? `${(hr.time_ms*1000).toFixed(0)} µs` : `${hr.time_ms.toFixed(2)} ms`}
//            color="#4ade80" />

//       <SectionLabel>naive linear scan</SectionLabel>
//       <Row label="tiles found"    value={nr.count}                    color="#f87171" />
//       <Row label="entries scanned" value={nExamined.toLocaleString()} color="#f87171" />
//       <Row label="time"           value={`${nr.time_ms.toFixed(2)} ms`} color="#f87171" />

//       <div style={{ marginTop:12 }}>
//         <SpeedupBar hilbert_ms={hr.time_ms} naive_ms={nr.time_ms} speedup={speedup} />
//       </div>

//       <div style={{ marginTop:10, display:"grid", gridTemplateColumns:"1fr 1fr", gap:6 }}>
//         <div style={{ background:"#0a0f1a", border:"1px solid #1e293b",
//                       borderRadius:6, padding:"8px 10px", textAlign:"center" }}>
//           <div style={{ fontSize:18, fontWeight:700, color:"#fbbf24" }}>
//             {tiles_saved.toLocaleString()}
//           </div>
//           <div style={{ fontSize:10, color:"#475569", marginTop:2 }}>entries skipped</div>
//         </div>
//         <div style={{ background:"#0a0f1a", border:"1px solid #1e293b",
//                       borderRadius:6, padding:"8px 10px", textAlign:"center" }}>
//           <div style={{ fontSize:18, fontWeight:700, color:"#fbbf24" }}>
//             {pct_skipped}%
//           </div>
//           <div style={{ fontSize:10, color:"#475569", marginTop:2 }}>of index skipped</div>
//         </div>
//       </div>
//     </div>
//   );
// }

// // ── Main component ────────────────────────────────────────────────
// export default function HilbertViewer() {
//   const [zoom, setZoom]             = useState(2);
//   const [lodData, setLodData]       = useState(null);
//   const [segData, setSegData]       = useState(null);
//   const [stats, setStats]           = useState(null);
//   const [bgImage, setBgImage]       = useState(null);
//   const [loading, setLoading]       = useState(false);
//   const [querying, setQuerying]     = useState(false);
//   const [queryResult, setQueryResult] = useState(null);
//   const [queryViewport, setQueryVP]   = useState(null);   // pixel bbox to highlight
//   const [queryTiles, setQueryTiles]   = useState([]);     // hilbert-matched tiles
//   const [error, setError]           = useState(null);
//   const [hoveredTile, setHovered]   = useState(null);
//   const canvasRef = useRef(null);

//   // load metadata once
//   useEffect(() => {
//     fetch(`${API}/segmentation`)
//       .then(r => r.json()).then(setSegData)
//       .catch(() => setError("Cannot reach tile server on :5000"));
//     fetch(`${API}/index_stats`)
//       .then(r => r.json()).then(setStats)
//       .catch(() => {});
//   }, []);

//   // background image
//   useEffect(() => {
//     const img = new window.Image();
//     img.crossOrigin = "anonymous";
//     img.onload  = () => setBgImage(img);
//     img.onerror = () => console.warn("No /image endpoint — canvas will be dark");
//     img.src = `${API}/image`;
//   }, []);

//   // LOD data on zoom change
//   const fetchLod = useCallback((z) => {
//     setLoading(true);
//     fetch(`${API}/lod?zoom=${z}`)
//       .then(r => r.json())
//       .then(d => { setLodData(d); setLoading(false); setError(null); })
//       .catch(() => { setError("LOD fetch failed"); setLoading(false); });
//   }, []);
//   useEffect(() => { fetchLod(zoom); }, [zoom, fetchLod]);

//   // canvas coords helper
//   const getScaleOffset = useCallback(() => {
//     if (!segData || !canvasRef.current) return null;
//     const canvas = canvasRef.current;
//     const [imgW, imgH] = segData.image_size;
//     const scale = Math.min(canvas.width / imgW, canvas.height / imgH);
//     const offX  = (canvas.width  - imgW * scale) / 2;
//     const offY  = (canvas.height - imgH * scale) / 2;
//     return { scale, offX, offY, imgW, imgH };
//   }, [segData]);

//   // ── draw ──────────────────────────────────────────────────────
//   useEffect(() => {
//     if (!lodData || !segData || !canvasRef.current) return;
//     const canvas = canvasRef.current;
//     const ctx    = canvas.getContext("2d");
//     const so     = getScaleOffset();
//     if (!so) return;
//     const { scale, offX, offY } = so;

//     ctx.clearRect(0, 0, canvas.width, canvas.height);
//     ctx.fillStyle = "#0a0f1a";
//     ctx.fillRect(0, 0, canvas.width, canvas.height);

//     if (bgImage) ctx.drawImage(bgImage, offX, offY, so.imgW * scale, so.imgH * scale);

//     // LOD tile overlays
//     for (const tile of lodData.tiles) {
//       const { region_class, status, mean_color, hilbert_order, pixel_bbox } = tile;
//       if (!pixel_bbox) continue;
//       const [px0, py0, px1, py1] = pixel_bbox;
//       const x0 = offX + px0 * scale;
//       const y0 = offY + py0 * scale;
//       const tw  = (px1 - px0) * scale;
//       const th  = (py1 - py0) * scale;
//       const cfg = CLASS_CFG[region_class] ?? CLASS_CFG[2];

//       if (status === "collapsed") {
//         const [r,g,b] = mean_color;
//         ctx.fillStyle = `rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},0.82)`;
//         ctx.fillRect(x0, y0, tw, th);
//       } else {
//         ctx.fillStyle = cfg.live;
//         ctx.fillRect(x0, y0, tw, th);
//         if (hilbert_order >= 3) {
//           const sg = Math.pow(2, hilbert_order);
//           ctx.strokeStyle = `${cfg.border}35`;
//           ctx.lineWidth   = 0.25;
//           for (let s = 0; s <= sg; s++) {
//             ctx.beginPath(); ctx.moveTo(x0, y0 + s * th/sg); ctx.lineTo(x0+tw, y0 + s * th/sg); ctx.stroke();
//             ctx.beginPath(); ctx.moveTo(x0 + s * tw/sg, y0); ctx.lineTo(x0 + s * tw/sg, y0+th); ctx.stroke();
//           }
//         }
//       }
//       ctx.strokeStyle = cfg.border;
//       ctx.lineWidth   = status === "collapsed" ? 1.8 : 0.7;
//       ctx.strokeRect(x0 + 0.5, y0 + 0.5, tw - 1, th - 1);
//       if (tw > 22) {
//         ctx.fillStyle = "rgba(255,255,255,0.8)";
//         ctx.font      = `bold ${Math.min(9, tw/6)}px monospace`;
//         ctx.fillText(`o${hilbert_order}`, x0 + 3, y0 + 12);
//       }
//     }

//     // Query viewport highlight
//     if (queryViewport) {
//       const [vx0, vy0, vx1, vy1] = queryViewport;
//       const qx = offX + vx0 * scale;
//       const qy = offY + vy0 * scale;
//       const qw = (vx1 - vx0) * scale;
//       const qh = (vy1 - vy0) * scale;

//       // dim outside viewport
//       ctx.fillStyle = "rgba(0,0,0,0.45)";
//       ctx.fillRect(offX, offY, qx - offX, so.imgH * scale);           // left
//       ctx.fillRect(qx + qw, offY, so.imgW * scale - qx - qw + offX, so.imgH * scale); // right
//       ctx.fillRect(qx, offY, qw, qy - offY);                           // top
//       ctx.fillRect(qx, qy + qh, qw, so.imgH * scale - qy - qh + offY); // bottom

//       // viewport border
//       ctx.strokeStyle = "#fbbf24";
//       ctx.lineWidth   = 2;
//       ctx.setLineDash([6, 3]);
//       ctx.strokeRect(qx, qy, qw, qh);
//       ctx.setLineDash([]);
//     }

//     // Highlight hilbert-matched tiles
//     for (const t of queryTiles) {
//       const bb = t.abs_bbox;
//       if (!bb || bb.length < 4) continue;
//       const [bx0, by0, bx1, by1] = bb;
//       ctx.fillStyle = "rgba(251,191,36,0.35)";
//       ctx.fillRect(offX + bx0 * scale, offY + by0 * scale,
//                    (bx1-bx0)*scale, (by1-by0)*scale);
//       ctx.strokeStyle = "#fbbf24";
//       ctx.lineWidth   = 1.5;
//       ctx.strokeRect(offX + bx0 * scale + 0.5, offY + by0 * scale + 0.5,
//                      (bx1-bx0)*scale - 1, (by1-by0)*scale - 1);
//     }

//     // Hover
//     if (hoveredTile?.pixel_bbox) {
//       const [px0, py0, px1, py1] = hoveredTile.pixel_bbox;
//       ctx.strokeStyle = "#ffffff";
//       ctx.lineWidth   = 2.5;
//       ctx.strokeRect(offX + px0*scale, offY + py0*scale,
//                      (px1-px0)*scale, (py1-py0)*scale);
//     }
//   }, [lodData, segData, bgImage, hoveredTile, queryViewport, queryTiles, getScaleOffset]);

//   // ── click → query ─────────────────────────────────────────────
//   const handleCanvasClick = useCallback((e) => {
//     const so = getScaleOffset();
//     if (!so) return;
//     const canvas = canvasRef.current;
//     const rect   = canvas.getBoundingClientRect();
//     const mx = (e.clientX - rect.left) * (canvas.width  / rect.width);
//     const my = (e.clientY - rect.top)  * (canvas.height / rect.height);
//     const ix = (mx - so.offX) / so.scale;
//     const iy = (my - so.offY) / so.scale;
//     if (ix < 0 || ix > so.imgW || iy < 0 || iy > so.imgH) return;

//     setQuerying(true);
//     fetch(`${API}/query?cx=${ix.toFixed(1)}&cy=${iy.toFixed(1)}&zoom=${zoom}`)
//       .then(r => r.json())
//       .then(d => {
//         setQueryResult(d);
//         setQueryVP(d.viewport_bbox);
//         setQueryTiles(d.hilbert_result.tiles);
//         setQuerying(false);
//       })
//       .catch(() => { setError("Query failed"); setQuerying(false); });
//   }, [getScaleOffset, zoom]);

//   const handleMouseMove = useCallback((e) => {
//     if (!lodData || !segData || !canvasRef.current) return;
//     const so   = getScaleOffset();
//     if (!so) return;
//     const canvas = canvasRef.current;
//     const rect   = canvas.getBoundingClientRect();
//     const mx = (e.clientX - rect.left) * (canvas.width  / rect.width);
//     const my = (e.clientY - rect.top)  * (canvas.height / rect.height);
//     const ix = (mx - so.offX) / so.scale;
//     const iy = (my - so.offY) / so.scale;
//     const found = lodData.tiles.find(t => {
//       if (!t.pixel_bbox) return false;
//       const [x0,y0,x1,y1] = t.pixel_bbox;
//       return ix >= x0 && ix < x1 && iy >= y0 && iy < y1;
//     });
//     setHovered(found || null);
//   }, [lodData, segData, getScaleOffset]);

//   // lod stats
//   const liveCount = lodData?.lod_stats?.live      ?? 0;
//   const collCount = lodData?.lod_stats?.collapsed ?? 0;
//   const total     = lodData?.lod_stats?.total     ?? 1;

//   return (
//     <div style={{ background:"#0a0f1a", minHeight:"100vh", color:"#e2e8f0",
//                   fontFamily:"'JetBrains Mono','Fira Code',monospace" }}>

//       {/* header */}
//       <div style={{ borderBottom:"1px solid #1e293b", padding:"10px 20px",
//                     display:"flex", alignItems:"center", gap:12 }}>
//         <div style={{ width:8, height:8, borderRadius:"50%",
//                       background: error ? "#f87171" : "#4ade80",
//                       boxShadow:`0 0 6px ${error ? "#f87171" : "#4ade80"}` }} />
//         <span style={{ fontSize:12, color:"#94a3b8", letterSpacing:"0.08em" }}>
//           ADAPTIVE HILBERT LOD VIEWER
//         </span>
//         <span style={{ fontSize:11, color:"#334155", marginLeft:4 }}>
//           click on map to benchmark a spatial query
//         </span>
//         {querying && (
//           <span style={{ marginLeft:"auto", fontSize:11, color:"#fbbf24" }}>
//             ⟳ querying…
//           </span>
//         )}
//         {stats && !querying && (
//           <div style={{ marginLeft:"auto", display:"flex", gap:14, fontSize:11, color:"#475569" }}>
//             <span>{stats.total_sub_tiles?.toLocaleString()} indexed tiles</span>
//             <span>{stats.base_tiles} base tiles</span>
//           </div>
//         )}
//       </div>

//       {error && (
//         <div style={{ margin:"10px 20px", padding:"8px 14px", background:"#1e0a0a",
//                       border:"1px solid #7f1d1d", borderRadius:6, fontSize:12, color:"#fca5a5" }}>
//           {error} — make sure tile_server.py is running on :5000
//         </div>
//       )}

//       <div style={{ display:"grid", gridTemplateColumns:"1fr 290px",
//                     height:"calc(100vh - 53px)" }}>

//         {/* canvas */}
//         <div style={{ position:"relative", padding:14 }}>
//           <canvas ref={canvasRef} width={820} height={740}
//             onClick={handleCanvasClick}
//             onMouseMove={handleMouseMove}
//             onMouseLeave={() => setHovered(null)}
//             style={{ width:"100%", height:"100%", display:"block",
//                      cursor: querying ? "wait" : "crosshair",
//                      borderRadius:6, border:"1px solid #1e293b" }} />
//           {loading && (
//             <div style={{ position:"absolute", top:22, left:22,
//                           background:"rgba(10,15,26,0.85)", padding:"5px 10px",
//                           borderRadius:4, fontSize:11, color:"#94a3b8",
//                           border:"1px solid #1e293b" }}>
//               fetching LOD…
//             </div>
//           )}
//           {queryViewport && (
//             <div style={{ position:"absolute", bottom:22, left:22,
//                           background:"rgba(10,15,26,0.9)", padding:"5px 10px",
//                           borderRadius:4, fontSize:11, color:"#fbbf24",
//                           border:"1px solid #fbbf2440" }}>
//               {queryTiles.length} hilbert-matched tiles highlighted
//             </div>
//           )}
//         </div>

//         {/* sidebar */}
//         <div style={{ borderLeft:"1px solid #1e293b", padding:"16px 14px",
//                       display:"flex", flexDirection:"column", gap:0, overflowY:"auto" }}>

//           {/* zoom */}
//           <SectionLabel>zoom level</SectionLabel>
//           <input type="range" min={0} max={4} step={1} value={zoom}
//             onChange={e => { setZoom(Number(e.target.value)); setQueryResult(null); setQueryVP(null); setQueryTiles([]); }}
//             style={{ width:"100%", accentColor:"#378add", marginBottom:6 }} />
//           <div style={{ display:"flex", justifyContent:"space-between",
//                         fontSize:10, color:"#475569", marginBottom:4 }}>
//             {[0,1,2,3,4].map(z => (
//               <span key={z} style={{ color: z===zoom ? "#93c5fd" : "#334155",
//                                      fontWeight: z===zoom ? 600 : 400 }}>{z}</span>
//             ))}
//           </div>
//           <div style={{ padding:"6px 10px", background:"#0f172a", borderRadius:5,
//                         border:"1px solid #1e293b", fontSize:12, marginBottom:2 }}>
//             <span style={{ color:"#475569" }}>zoom </span>
//             <span style={{ color:"#93c5fd", fontWeight:600 }}>{zoom}</span>
//             <span style={{ color:"#334155", marginLeft:10, fontSize:11 }}>
//               {["full image","÷2 viewport","÷4 viewport","÷8 viewport","÷16 viewport"][zoom]}
//             </span>
//           </div>

//           {/* LOD stats */}
//           <SectionLabel>lod status</SectionLabel>
//           <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:6, marginBottom:8 }}>
//             {[
//               { label:"live",      count:liveCount, color:"#4ade80", bg:"#052e16" },
//               { label:"collapsed", count:collCount, color:"#f87171", bg:"#2d0707" },
//             ].map(s => (
//               <div key={s.label} style={{ background:s.bg, border:`1px solid ${s.color}33`,
//                                           borderRadius:6, padding:"8px 6px", textAlign:"center" }}>
//                 <div style={{ fontSize:20, fontWeight:600, color:s.color }}>{s.count}</div>
//                 <div style={{ fontSize:10, color:"#475569", marginTop:1 }}>{s.label}</div>
//               </div>
//             ))}
//           </div>
//           <div style={{ height:5, borderRadius:3, background:"#1e293b", overflow:"hidden", marginBottom:4 }}>
//             <div style={{ height:"100%", background:"#4ade80", borderRadius:3,
//                           width:`${(liveCount/total)*100}%`, transition:"width 0.4s" }} />
//           </div>
//           <div style={{ fontSize:10, color:"#475569", marginBottom:4 }}>
//             {Math.round((liveCount/total)*100)}% live at zoom {zoom}
//           </div>

//           {/* by class */}
//           <SectionLabel>by region class</SectionLabel>
//           {lodData && (() => {
//             const cc = { 0:{live:0,coll:0}, 1:{live:0,coll:0}, 2:{live:0,coll:0} };
//             for (const t of lodData.tiles) {
//               const b = cc[t.region_class];
//               if (t.status==="live") b.live++; else b.coll++;
//             }
//             return Object.entries(CLASS_CFG).map(([cls, cfg]) => (
//               <div key={cls} style={{ marginBottom:6, padding:"8px 10px", background:"#0f172a",
//                                       borderRadius:5, borderLeft:`3px solid ${cfg.border}` }}>
//                 <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
//                   <span style={{ fontSize:11, color:cfg.border, fontWeight:600 }}>{cfg.label}</span>
//                   <span style={{ fontSize:10, color:"#334155" }}>order {cfg.order}</span>
//                 </div>
//                 <div style={{ display:"flex", gap:8, fontSize:11 }}>
//                   <span style={{ color:"#4ade80" }}>{cc[cls].live} live</span>
//                   <span style={{ color:"#334155" }}>/</span>
//                   <span style={{ color:"#f87171" }}>{cc[cls].coll} collapsed</span>
//                 </div>
//               </div>
//             ));
//           })()}

//           {/* query result */}
//           {queryResult && (
//             <>
//               <SectionLabel>benchmark</SectionLabel>
//               <QueryPanel query={queryResult}
//                           onClose={() => { setQueryResult(null); setQueryVP(null); setQueryTiles([]); }} />
//             </>
//           )}

//           {!queryResult && (
//             <div style={{ marginTop:12, padding:"10px 12px", background:"#0f172a",
//                           border:"1px dashed #1e293b", borderRadius:6,
//                           fontSize:11, color:"#334155", textAlign:"center" }}>
//               click anywhere on the map<br/>to run a spatial query benchmark
//             </div>
//           )}

//           {/* hovered tile */}
//           {hoveredTile && (
//             <>
//               <SectionLabel>hovered tile</SectionLabel>
//               <div style={{ background:"#0f172a", border:"1px solid #1e293b",
//                             borderRadius:6, padding:"10px 12px", fontSize:11 }}>
//                 {[
//                   ["pos",    `(${hoveredTile.base_tx ?? hoveredTile.tile_x}, ${hoveredTile.base_ty ?? hoveredTile.tile_y})`],
//                   ["class",  hoveredTile.class_name],
//                   ["order",  hoveredTile.hilbert_order],
//                   ["status", hoveredTile.status],
//                   ["entropy", hoveredTile.entropy?.toFixed(3)],
//                 ].map(([k,v]) => <Row key={k} label={k} value={v}
//                   color={hoveredTile.status==="live" ? "#4ade80" : "#f87171"} />)}
//               </div>
//             </>
//           )}

//           {/* legend */}
//           <div style={{ marginTop:"auto", paddingTop:16,
//                         borderTop:"1px solid #1e293b" }}>
//             {Object.entries(CLASS_CFG).map(([c, cfg]) => (
//               <div key={c} style={{ display:"flex", alignItems:"center",
//                                     gap:7, marginBottom:4 }}>
//                 <div style={{ width:10, height:10, borderRadius:2,
//                               border:`2px solid ${cfg.border}`,
//                               background: "transparent" }} />
//                 <span style={{ fontSize:10, color:"#475569" }}>
//                   {cfg.label} · live (order {cfg.order})
//                 </span>
//               </div>
//             ))}
//             <div style={{ display:"flex", alignItems:"center", gap:7, marginTop:6 }}>
//               <div style={{ width:10, height:10, borderRadius:2, background:"#fbbf24" }} />
//               <span style={{ fontSize:10, color:"#475569" }}>hilbert query result</span>
//             </div>
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// }

import { useState, useEffect, useRef, useCallback } from "react";

const API = "http://localhost:5000";
const MAX_DEPTH = 5;

const CLASS_CFG = {
  0: { border: "#1e78d2", label: "water",      hilbert: "#60a5fa" },
  1: { border: "#3cb450", label: "transition", hilbert: "#4ade80" },
  2: { border: "#dc3c3c", label: "urban",      hilbert: "#f87171" },
};

// ── draw Hilbert curve path inside a tile ─────────────────────────
function drawHilbertPath(ctx, codes, x0, y0, tw, th, color, depth) {
  if (!codes || codes.length < 2) return;
  const sorted = [...codes].sort((a, b) => a.code - b.code);
  const centers = sorted.map(c => {
    const bx = c.bbox[0], by = c.bbox[1], bx1 = c.bbox[2], by1 = c.bbox[3];
    return [(bx + bx1) / 2, (by + by1) / 2];
  });

  ctx.strokeStyle = color;
  ctx.lineWidth   = Math.max(0.4, 1.5 - depth * 0.2);
  ctx.globalAlpha = 0.7;
  ctx.beginPath();
  ctx.moveTo(centers[0][0], centers[0][1]);
  for (let i = 1; i < centers.length; i++) ctx.lineTo(centers[i][0], centers[i][1]);
  ctx.stroke();
  ctx.globalAlpha = 1;

  // node dots at finest zoom
  if (depth >= 3 && tw > 60) {
    ctx.fillStyle = color;
    for (const [cx, cy] of centers) {
      ctx.beginPath();
      ctx.arc(cx, cy, 1.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

// ── draw vector features ──────────────────────────────────────────
function drawVectorFeatures(ctx, features, scale, offX, offY, color) {
  if (!features) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  for (const f of features) {
    if (f.type === "LineString" && f.coordinates) {
      ctx.beginPath();
      for (let i = 0; i < f.coordinates.length; i++) {
        const [x, y] = f.coordinates[i];
        const cx = offX + x * scale;
        const cy = offY + y * scale;
        if (i === 0) ctx.moveTo(cx, cy);
        else ctx.lineTo(cx, cy);
      }
      ctx.stroke();
    }
  }
}

// ── SpeedupBar ────────────────────────────────────────────────────
function SpeedupBar({ hms, nms, speedup }) {
  const frac = Math.min(hms / (nms || 1), 1);
  const fmt  = ms => ms < 0.5 ? `${(ms*1000).toFixed(0)}µs` : `${ms.toFixed(2)}ms`;
  return (
    <div>
      {[["hilbert", frac,   "#4ade80", hms],
        ["naive",   1,      "#f87171", nms]].map(([lbl, w, col, ms]) => (
        <div key={lbl} style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>
          <span style={{width:44,fontSize:10,color:col,textAlign:"right"}}>{lbl}</span>
          <div style={{flex:1,background:"#1e293b",borderRadius:3,height:12,overflow:"hidden"}}>
            <div style={{width:`${w*100}%`,height:"100%",background:col,borderRadius:3,
                         transition:"width 0.5s ease",display:"flex",alignItems:"center",
                         justifyContent:"flex-end",paddingRight:3}}>
              <span style={{fontSize:8,color:"#000",fontWeight:700}}>{fmt(ms)}</span>
            </div>
          </div>
        </div>
      ))}
      <div style={{textAlign:"center",padding:"6px 0",background:"#0f172a",
                   borderRadius:5,border:"1px solid #1e293b",marginTop:6}}>
        <span style={{fontSize:20,fontWeight:700,
                      color: speedup >= 1 ? "#fbbf24" : "#94a3b8"}}>{speedup.toFixed(1)}×</span>
        <span style={{fontSize:10,color:"#475569",marginLeft:5}}>
          {speedup >= 1 ? "faster" : "slower (dense region)"}
        </span>
      </div>
    </div>
  );
}

// ── Breadcrumb ────────────────────────────────────────────────────
function Breadcrumb({ history, onJump }) {
  if (!history.length) return null;
  return (
    <div style={{display:"flex",alignItems:"center",gap:4,flexWrap:"wrap",
                 fontSize:10,color:"#475569",marginBottom:8}}>
      <span onClick={() => onJump(-1)}
            style={{cursor:"pointer",color:"#93c5fd",textDecoration:"underline"}}>
        root
      </span>
      {history.map((h, i) => (
        <span key={i} style={{display:"flex",alignItems:"center",gap:4}}>
          <span style={{color:"#334155"}}>›</span>
          <span onClick={() => onJump(i)}
                style={{cursor:"pointer",
                        color: i === history.length-1 ? "#fbbf24" : "#93c5fd",
                        textDecoration: i < history.length-1 ? "underline" : "none",
                        fontWeight: i === history.length-1 ? 600 : 400}}>
            d{i+1} ({Math.round(h.cx)},{Math.round(h.cy)})
          </span>
        </span>
      ))}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────
export default function HilbertViewer() {
  const [segData,  setSegData]  = useState(null);
  const [stats,    setStats]    = useState(null);
  const [bgImage,  setBgImage]  = useState(null);
  const [lodData,  setLodData]  = useState(null);      // full-image LOD (base view)
  const [zoomData, setZoomData] = useState(null);      // /zoom_lod result
  const [query,    setQuery]    = useState(null);      // /query benchmark result
  const [history,  setHistory]  = useState([]);        // [{cx,cy,depth}]
  const [depth,    setDepth]    = useState(0);
  const [viewport, setViewport] = useState(null);      // current pixel bbox
  const [loading,  setLoading]  = useState(false);
  const [mode,     setMode]     = useState("raster");
  const [rasterDataset, setRasterDataset] = useState("test1");
  const [error,    setError]    = useState(null);
  const [hovered,  setHovered]  = useState(null);
  const canvasRef = useRef(null);
  const minimapCanvasRef = useRef(null);

  // ── load metadata ──────────────────────────────────────────────
  const activeDataset = mode === "vector" ? "vector" : rasterDataset;

  // reset state on dataset change
  useEffect(() => {
    setDepth(0);
    setViewport(null);
    setHistory([]);
    setHovered(null);
    setZoomData(null);
    setQuery(null);
  }, [activeDataset]);

  useEffect(() => {
    fetch(`${API}/segmentation?dataset=${activeDataset}`).then(r=>r.json()).then(setSegData)
      .catch(()=>setError("Cannot reach server on :5000"));
  }, [activeDataset]);

  useEffect(() => {
    fetch(`${API}/index_stats?dataset=${activeDataset}`).then(r=>r.json()).then(setStats).catch(()=>{});
    fetch(`${API}/lod?zoom=0&dataset=${activeDataset}`).then(r=>r.json()).then(setLodData).catch(()=>{});
    
    // reset zoom/history state on mode switch
    setZoomData(null); setHistory([]); setDepth(0); setViewport(null);
    
    // fetch baseline query so vector features render at depth 0
    if (segData) {
      const cx = segData.image_size[0] / 2;
      const cy = segData.image_size[1] / 2;
      fetch(`${API}/query?cx=${cx}&cy=${cy}&zoom=0&dataset=${activeDataset}`)
        .then(r=>r.json()).then(setQuery).catch(()=>{});
    } else {
      setQuery(null);
    }
  }, [activeDataset, segData]);

  useEffect(() => {
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.onload = () => setBgImage(img);
    img.src = `${API}/image?dataset=${activeDataset}&t=${new Date().getTime()}`;
  }, [activeDataset]);

  // ── coord helpers ──────────────────────────────────────────────
  const getScaleOffset = useCallback(() => {
    if (!segData || !canvasRef.current) return null;
    const c = canvasRef.current;
    const [iw, ih] = segData.image_size;
    const scale = Math.min(c.width / iw, c.height / ih);
    return { scale, offX:(c.width - iw*scale)/2, offY:(c.height - ih*scale)/2, imgW:iw, imgH:ih };
  }, [segData]);

  const toCanvas = (ix, iy, so) => [so.offX + ix*so.scale, so.offY + iy*so.scale];
  const toImage  = (cx, cy, so) => [(cx - so.offX)/so.scale, (cy - so.offY)/so.scale];

  // ── draw ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!canvasRef.current || !segData) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const so  = getScaleOffset();
    if (!so) return;

    const tiles = zoomData ? zoomData.tiles : (lodData?.tiles ?? []);
    const inZoom = !!zoomData;

    const drawMap = (targetCtx, width, height, scale, offX, offY, isMinimap=false) => {
      targetCtx.clearRect(0, 0, width, height);
      targetCtx.fillStyle = "#0a0f1a";
      targetCtx.fillRect(0, 0, width, height);

      if (bgImage && mode === "raster") {
        targetCtx.drawImage(bgImage, offX, offY, so.imgW*scale, so.imgH*scale);
      }

      for (const tile of tiles) {
        const cfg   = CLASS_CFG[tile.region_class] ?? CLASS_CFG[2];
        const bb    = inZoom ? tile.clip_bbox : tile.pixel_bbox;
        if (!bb) continue;

        const [px0,py0,px1,py1] = bb;
        const x0 = offX + px0*scale, y0 = offY + py0*scale;
        const tw  = (px1-px0)*scale,  th  = (py1-py0)*scale;

        // Skip drawing if completely out of bounds (useful for minimap)
        if (x0 > width || y0 > height || x0+tw < 0 || y0+th < 0) continue;

        if (tile.status === "collapsed") {
          if (mode === "raster") {
            const [r,g,b] = tile.mean_color;
            targetCtx.fillStyle = `rgba(${Math.round(r)},${Math.round(g)},${Math.round(b)},0.82)`;
            targetCtx.fillRect(x0,y0,tw,th);
          }
        } else {
          if (mode === "raster") {
            targetCtx.fillStyle = `${cfg.border}22`;
            targetCtx.fillRect(x0,y0,tw,th);
          }

          const vg = inZoom ? tile.vis_grid : Math.pow(2, tile.hilbert_order ?? 2);
          if (vg > 1) {
            targetCtx.strokeStyle = `${cfg.border}30`;
            targetCtx.lineWidth   = isMinimap ? 0.5 : 0.25;
            for (let s = 1; s < vg; s++) {
              const lx = x0 + s*(tw/vg), ly = y0 + s*(th/vg);
              targetCtx.beginPath(); targetCtx.moveTo(lx, y0); targetCtx.lineTo(lx, y0+th); targetCtx.stroke();
              targetCtx.beginPath(); targetCtx.moveTo(x0, ly); targetCtx.lineTo(x0+tw, ly); targetCtx.stroke();
            }
          }

          if (inZoom && tile.visible_codes?.length >= 2) {
            const scaled = tile.visible_codes.map(c => ({
              ...c,
              bbox: c.bbox.map((v,i) => i%2===0 ? offX+v*scale : offY+v*scale)
            }));
            drawHilbertPath(targetCtx, scaled, x0, y0, tw, th, cfg.hilbert, depth);
          }
        }

        targetCtx.strokeStyle = cfg.border;
        targetCtx.lineWidth   = tile.status==="collapsed" ? 1.5 : (isMinimap ? 1.5 : 0.7);
        targetCtx.strokeRect(x0+0.5, y0+0.5, tw-1, th-1);

        if (tw > 20 && mode === "raster") {
          targetCtx.fillStyle = "rgba(255,255,255,0.75)";
          targetCtx.font = `bold ${Math.min(9,tw/5)}px monospace`;
          const ord = inZoom ? tile.visible_order : tile.hilbert_order;
          targetCtx.fillText(`o${ord}`, x0+3, y0+11);
        }
      }

      if (mode === "vector" && query?.hilbert_result?.tiles) {
        for (const t of query.hilbert_result.tiles) {
          const cfg = CLASS_CFG[t.region_class] ?? CLASS_CFG[2];
          drawVectorFeatures(targetCtx, t.features, scale, offX, offY, cfg.hilbert);
        }
      }
    };

    // 1. Draw main map
    drawMap(ctx, canvas.width, canvas.height, so.scale, so.offX, so.offY, false);

    // 2. Viewport overlay on main map
    if (viewport) {
      const [vx0,vy0,vx1,vy1] = viewport;
      const qx = so.offX+vx0*so.scale, qy = so.offY+vy0*so.scale;
      const qw = (vx1-vx0)*so.scale, qh = (vy1-vy0)*so.scale;
      ctx.fillStyle = "rgba(0,0,0,0.42)";
      ctx.fillRect(so.offX, so.offY, qx-so.offX, so.imgH*so.scale);
      ctx.fillRect(qx+qw, so.offY, so.imgW*so.scale-(qx-so.offX)-qw, so.imgH*so.scale);
      ctx.fillRect(qx, so.offY, qw, qy-so.offY);
      ctx.fillRect(qx, qy+qh, qw, so.imgH*so.scale-(qy-so.offY)-qh);
      ctx.strokeStyle = "#fbbf24";
      ctx.lineWidth   = 2;
      ctx.setLineDash([5,3]);
      ctx.strokeRect(qx,qy,qw,qh);
      ctx.setLineDash([]);
    }

    // 3. Hover on main map
    if (hovered?.pixel_bbox) {
      const [px0,py0,px1,py1] = hovered.pixel_bbox;
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.strokeRect(so.offX+px0*so.scale, so.offY+py0*so.scale, (px1-px0)*so.scale, (py1-py0)*so.scale);
    }

    // 4. Draw minimap
    if (minimapCanvasRef.current) {
      const mCanvas = minimapCanvasRef.current;
      const mCtx = mCanvas.getContext("2d");
      if (viewport) {
        const [vx0,vy0,vx1,vy1] = viewport;
        const vw = vx1 - vx0;
        const vh = vy1 - vy0;
        // Map the viewport to fill the 250x250 minimap
        const mScale = Math.min(mCanvas.width / vw, mCanvas.height / vh) * 0.95; 
        const mOffX = (mCanvas.width - vw * mScale) / 2 - vx0 * mScale;
        const mOffY = (mCanvas.height - vh * mScale) / 2 - vy0 * mScale;
        drawMap(mCtx, mCanvas.width, mCanvas.height, mScale, mOffX, mOffY, true);
      } else {
        // Clear minimap when not zoomed
        mCtx.clearRect(0, 0, mCanvas.width, mCanvas.height);
        mCtx.fillStyle = "#0a0f1a";
        mCtx.fillRect(0, 0, mCanvas.width, mCanvas.height);
      }
    }

  }, [lodData, zoomData, segData, bgImage, hovered, viewport, depth, getScaleOffset, query, mode]);

  // ── click → zoom in ───────────────────────────────────────────
  const handleClick = useCallback((e) => {
    const so = getScaleOffset();
    if (!so) return;
    const canvas = canvasRef.current;
    const rect   = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const my = (e.clientY - rect.top)  * (canvas.height / rect.height);
    const [ix, iy] = toImage(mx, my, so);
    if (ix < 0 || ix > so.imgW || iy < 0 || iy > so.imgH) return;

    const newDepth = depth + 1;
    if (newDepth > MAX_DEPTH) return;

    setLoading(true);
    const newHistory = [...history, { cx: ix, cy: iy, depth: newDepth }];

    // Fire /zoom_lod and /query in parallel
    Promise.all([
      fetch(`${API}/zoom_lod?cx=${ix.toFixed(1)}&cy=${iy.toFixed(1)}&depth=${newDepth}&dataset=${activeDataset}`).then(r=>r.json()),
      fetch(`${API}/query?cx=${ix.toFixed(1)}&cy=${iy.toFixed(1)}&zoom=${newDepth}&dataset=${activeDataset}`).then(r=>r.json()),
    ]).then(([zd, qd]) => {
      setZoomData(zd);
      setViewport(zd.viewport);
      setQuery(qd);
      setDepth(newDepth);
      setHistory(newHistory);
      setLoading(false);
      setError(null);
    }).catch(() => { setError("Request failed"); setLoading(false); });
  }, [depth, history, getScaleOffset, activeDataset]);

  // ── jump to history point ─────────────────────────────────────
  const handleJump = useCallback((idx) => {
    if (idx === -1) {
      // back to root
      setDepth(0); setHistory([]); setZoomData(null);
      setViewport(null); setQuery(null);
      return;
    }
    const h = history[idx];
    const newHistory = history.slice(0, idx + 1);
    setLoading(true);
    Promise.all([
      fetch(`${API}/zoom_lod?cx=${h.cx.toFixed(1)}&cy=${h.cy.toFixed(1)}&depth=${h.depth}&dataset=${activeDataset}`).then(r=>r.json()),
      fetch(`${API}/query?cx=${h.cx.toFixed(1)}&cy=${h.cy.toFixed(1)}&zoom=${h.depth}&dataset=${activeDataset}`).then(r=>r.json()),
    ]).then(([zd, qd]) => {
      setZoomData(zd); setViewport(zd.viewport); setQuery(qd);
      setDepth(h.depth); setHistory(newHistory); setLoading(false);
    }).catch(()=>setLoading(false));
  }, [history, activeDataset]);

  const handleMouseMove = useCallback((e) => {
    if (!lodData || !segData || !canvasRef.current) return;
    const so = getScaleOffset(); if (!so) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = (e.clientX-rect.left)*(canvasRef.current.width/rect.width);
    const my = (e.clientY-rect.top)*(canvasRef.current.height/rect.height);
    const [ix,iy] = toImage(mx,my,so);
    const src = zoomData?.tiles ?? lodData.tiles;
    setHovered(src.find(t => {
      const b = t.pixel_bbox; if (!b) return false;
      return ix>=b[0]&&ix<b[2]&&iy>=b[1]&&iy<b[3];
    }) || null);
  }, [lodData, zoomData, segData, getScaleOffset]);

  const liveCount = (zoomData ?? lodData)?.tiles?.filter(t=>t.status==="live").length ?? 0;
  const collCount = (zoomData ?? lodData)?.tiles?.filter(t=>t.status==="collapsed").length ?? 0;

  return (
    <div style={{background:"#0a0f1a", height:"100vh", overflow:"hidden", color:"#e2e8f0",
                 fontFamily:"'JetBrains Mono','Fira Code',monospace"}}>

      {/* header */}
      <div style={{borderBottom:"1px solid #1e293b",padding:"9px 18px",
                   display:"flex",alignItems:"center",gap:12}}>
        <div style={{width:7,height:7,borderRadius:"50%",
                     background:error?"#f87171":"#4ade80",
                     boxShadow:`0 0 5px ${error?"#f87171":"#4ade80"}`}} />
        <span style={{fontSize:11,color:"#94a3b8",letterSpacing:"0.08em"}}>
          ADAPTIVE HILBERT LOD VIEWER
        </span>
        <span style={{fontSize:10,color:"#334155"}}>
          {depth===0 ? "click to zoom in" : `depth ${depth} — click to go deeper`}
        </span>
        {depth > 0 && (
          <button onClick={()=>handleJump(-1)}
            style={{marginLeft:8,padding:"2px 10px",background:"#1e293b",
                    border:"1px solid #334155",borderRadius:4,color:"#93c5fd",
                    fontSize:10,cursor:"pointer"}}>
            ⟲ reset
          </button>
        )}
        {loading && <span style={{marginLeft:"auto",fontSize:10,color:"#fbbf24"}}>⟳ loading…</span>}
        {stats && !loading && (
          <div style={{marginLeft:"auto",display:"flex",gap:12,fontSize:10,color:"#475569"}}>
            <span>{stats.total_sub_tiles?.toLocaleString()} tiles</span>
            <span>{stats.base_tiles} base</span>
          </div>
        )}
      </div>

      {error && (
        <div style={{margin:"8px 18px",padding:"7px 12px",background:"#1e0a0a",
                     border:"1px solid #7f1d1d",borderRadius:5,fontSize:11,color:"#fca5a5"}}>
          {error}
        </div>
      )}

      <div style={{display:"grid",gridTemplateColumns:"1fr 280px",
                   height:"calc(100vh - 50px)"}}>

        {/* canvas wrapper */}
        <div style={{position:"relative", padding:12, overflow:"auto", display:"flex", justifyContent:"center", alignItems:"flex-start"}}>
          <canvas ref={canvasRef} width={1000} height={1000}
            onClick={handleClick}
            onMouseMove={handleMouseMove}
            onMouseLeave={()=>setHovered(null)}
            style={{display:"block",
                    cursor: depth>=MAX_DEPTH ? "default" : loading ? "wait" : "zoom-in",
                    borderRadius:6, border:"1px solid #1e293b",
                    boxShadow:"0 4px 6px -1px rgba(0, 0, 0, 0.5)"}} />
          {viewport && (
            <div style={{position:"absolute",bottom:20,left:20,
                         background:"rgba(10,15,26,0.9)",padding:"4px 10px",
                         borderRadius:4,fontSize:10,color:"#fbbf24",
                         border:"1px solid #fbbf2440"}}>
              viewport · depth {depth} · {zoomData?.tile_count} tiles visible
            </div>
          )}
        </div>

        {/* sidebar */}
        <div style={{borderLeft:"1px solid #1e293b",padding:"14px 13px",
                     display:"flex",flexDirection:"column",gap:0,overflowY:"auto"}}>

          {/* minimap viewport */}
          <div style={{marginBottom: 16, border: "1px solid #334155", borderRadius: 4, 
                       background: "#0f172a", overflow: "hidden", display: viewport ? "block" : "none"}}>
            <div style={{fontSize:9, padding:"4px 8px", background:"#1e293b", color:"#94a3b8", borderBottom:"1px solid #334155"}}>
              ZOOM VIEWPORT
            </div>
            <canvas ref={minimapCanvasRef} width={252} height={252} style={{display:"block"}} />
          </div>

          {/* breadcrumb */}
          {history.length > 0 && (
            <>
              <div style={{fontSize:10,color:"#475569",letterSpacing:"0.1em",marginBottom:6}}>
                ZOOM HISTORY
              </div>
              <Breadcrumb history={history} onJump={handleJump} />
            </>
          )}

          {/* mode toggle */}
          <div style={{fontSize:10,color:"#475569",letterSpacing:"0.1em",marginBottom:6,
                       marginTop: history.length ? 10 : 0}}>
            DATA MODE
          </div>
          <div style={{display:"flex",gap:4,marginBottom: mode === "raster" ? 6 : 12}}>
            <button onClick={() => setMode("raster")}
              style={{flex:1,padding:"6px 0",background:mode==="raster"?"#1e3a8a":"#1e293b",
                      border:mode==="raster"?"1px solid #3b82f6":"1px solid #334155",
                      color:mode==="raster"?"#93c5fd":"#64748b",borderRadius:4,fontSize:11,cursor:"pointer",
                      fontWeight:mode==="raster"?600:400}}>
              Raster
            </button>
            <button onClick={() => setMode("vector")}
              style={{flex:1,padding:"6px 0",background:mode==="vector"?"#1e3a8a":"#1e293b",
                      border:mode==="vector"?"1px solid #3b82f6":"1px solid #334155",
                      color:mode==="vector"?"#93c5fd":"#64748b",borderRadius:4,fontSize:11,cursor:"pointer",
                      fontWeight:mode==="vector"?600:400}}>
              Vector
            </button>
          </div>

          {mode === "raster" && (
            <div style={{marginBottom:12}}>
              <select 
                value={rasterDataset} 
                onChange={(e) => setRasterDataset(e.target.value)}
                style={{width:"100%", padding:"6px", background:"#1e293b", border:"1px solid #334155",
                        color:"#e2e8f0", borderRadius:4, fontSize:11, cursor:"pointer",
                        outline:"none"}}
              >
                <option value="test1">Test 1 (Small Town)</option>
                <option value="test2">Test 2 (Coastal Strip)</option>
              </select>
            </div>
          )}

          {/* depth indicator */}
          <div style={{fontSize:10,color:"#475569",letterSpacing:"0.1em",marginBottom:6}}>
            DEPTH
          </div>
          <div style={{display:"flex",gap:4,marginBottom:10}}>
            {Array.from({length:MAX_DEPTH+1},(_,i)=>(
              <div key={i} style={{flex:1,height:6,borderRadius:3,
                                   background: i<=depth ? "#fbbf24" : "#1e293b",
                                   transition:"background 0.3s"}} />
            ))}
          </div>
          <div style={{padding:"5px 9px",background:"#0f172a",borderRadius:4,
                       border:"1px solid #1e293b",fontSize:11,marginBottom:2}}>
            <span style={{color:"#475569"}}>depth </span>
            <span style={{color:"#fbbf24",fontWeight:600}}>{depth}</span>
            <span style={{color:"#334155",marginLeft:8,fontSize:10}}>
              {["full image  (click to zoom)","÷2","÷4","÷8","÷16","÷32"][depth]}
            </span>
          </div>
          <div style={{fontSize:10,color:"#334155",marginBottom:10,textAlign:"right"}}>
            hilbert order shown: base + {depth} per tile
          </div>

          {/* lod */}
          <div style={{fontSize:10,color:"#475569",letterSpacing:"0.1em",marginBottom:6}}>
            LOD STATUS
          </div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:5,marginBottom:8}}>
            {[{l:"live",c:liveCount,col:"#4ade80",bg:"#052e16"},
              {l:"collapsed",c:collCount,col:"#f87171",bg:"#2d0707"}].map(s=>(
              <div key={s.l} style={{background:s.bg,border:`1px solid ${s.col}33`,
                                     borderRadius:5,padding:"7px 5px",textAlign:"center"}}>
                <div style={{fontSize:18,fontWeight:600,color:s.col}}>{s.c}</div>
                <div style={{fontSize:9,color:"#475569",marginTop:1}}>{s.l}</div>
              </div>
            ))}
          </div>

          {/* by class */}
          <div style={{fontSize:10,color:"#475569",letterSpacing:"0.1em",marginBottom:6}}>
            BY CLASS
          </div>
          {(zoomData ?? lodData)?.tiles && (() => {
            const src = (zoomData ?? lodData).tiles;
            const cc  = {0:{live:0,coll:0},1:{live:0,coll:0},2:{live:0,coll:0}};
            for (const t of src) { const b=cc[t.region_class]; t.status==="live"?b.live++:b.coll++; }
            return Object.entries(CLASS_CFG).map(([c,cfg])=>(
              <div key={c} style={{marginBottom:5,padding:"7px 9px",background:"#0f172a",
                                   borderRadius:4,borderLeft:`3px solid ${cfg.border}`}}>
                <div style={{display:"flex",justifyContent:"space-between",marginBottom:3}}>
                  <span style={{fontSize:10,color:cfg.border,fontWeight:600}}>{cfg.label}</span>
                  <span style={{fontSize:9,color:"#334155"}}>
                    o{[2,3,4][c]}+{depth} shown
                  </span>
                </div>
                <div style={{display:"flex",gap:6,fontSize:10}}>
                  <span style={{color:"#4ade80"}}>{cc[c].live} live</span>
                  <span style={{color:"#334155"}}>/</span>
                  <span style={{color:"#f87171"}}>{cc[c].coll} coll.</span>
                </div>
              </div>
            ));
          })()}

          {/* benchmark */}
          {query && (
            <>
              <div style={{fontSize:10,color:"#475569",letterSpacing:"0.1em",
                           marginBottom:6,marginTop:10}}>
                BENCHMARK — DEPTH {depth}
              </div>
              <div style={{background:"#0f172a",border:"1px solid #1e293b",
                           borderRadius:6,padding:"11px 11px 8px"}}>
                {[["viewport",`${Math.round(query.viewport_bbox[2]-query.viewport_bbox[0])}×${Math.round(query.viewport_bbox[3]-query.viewport_bbox[1])}px`],
                  ["hilbert found",query.hilbert_result.count],
                  ["naive found",query.naive_result.count],
                ].map(([k,v])=>(
                  <div key={k} style={{display:"flex",justifyContent:"space-between",
                                       padding:"2px 0",borderBottom:"1px solid #1e293b",
                                       fontSize:11}}>
                    <span style={{color:"#475569"}}>{k}</span>
                    <span style={{color:"#94a3b8"}}>{v}</span>
                  </div>
                ))}
                <div style={{marginTop:8}}>
                  <SpeedupBar
                    hms={query.hilbert_result.time_ms}
                    nms={query.naive_result.time_ms}
                    speedup={query.speedup} />
                </div>
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:5,marginTop:8}}>
                  {[
                    {v:query.tiles_saved.toLocaleString(), l:"entries skipped"},
                    {v:`${query.pct_skipped}%`, l:"index skipped"},
                  ].map(s=>(
                    <div key={s.l} style={{background:"#0a0f1a",border:"1px solid #1e293b",
                                           borderRadius:5,padding:"6px 8px",textAlign:"center"}}>
                      <div style={{fontSize:15,fontWeight:700,
                                   color: query.speedup>=1 ? "#fbbf24":"#94a3b8"}}>{s.v}</div>
                      <div style={{fontSize:9,color:"#475569",marginTop:2}}>{s.l}</div>
                    </div>
                  ))}
                </div>
                {query.speedup < 1 && (
                  <div style={{marginTop:8,padding:"5px 8px",background:"#1c1205",
                               border:"1px solid #78350f",borderRadius:4,
                               fontSize:10,color:"#fcd34d"}}>
                    dense region — viewport covers most of one class.
                    hilbert overhead exceeds savings here.
                  </div>
                )}
              </div>
            </>
          )}

          {/* hovered */}
          {hovered && (
            <>
              <div style={{fontSize:10,color:"#475569",letterSpacing:"0.1em",
                           marginBottom:6,marginTop:10}}>
                HOVERED
              </div>
              <div style={{background:"#0f172a",border:"1px solid #1e293b",
                           borderRadius:5,padding:"9px 10px",fontSize:10}}>
                {[["class",  hovered.class_name],
                  ["order",  `base o${hovered.base_order??hovered.hilbert_order} → showing o${hovered.visible_order??hovered.hilbert_order}`],
                  ["entropy",hovered.entropy?.toFixed(3)],
                  ["status", hovered.status],
                ].map(([k,v])=>(
                  <div key={k} style={{display:"flex",justifyContent:"space-between",
                                       padding:"2px 0",borderBottom:"1px solid #1e293b"}}>
                    <span style={{color:"#475569"}}>{k}</span>
                    <span style={{color:hovered.status==="live"?"#4ade80":"#f87171"}}>{v}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* legend */}
          <div style={{marginTop:"auto",paddingTop:12,borderTop:"1px solid #1e293b"}}>
            {Object.entries(CLASS_CFG).map(([c,cfg])=>(
              <div key={c} style={{display:"flex",alignItems:"center",gap:6,marginBottom:3}}>
                <div style={{width:8,height:8,borderRadius:2,background:cfg.hilbert}}/>
                <span style={{fontSize:9,color:"#475569"}}>
                  {cfg.label} · hilbert curve
                </span>
              </div>
            ))}
            <div style={{fontSize:9,color:"#334155",marginTop:6}}>
              curve density increases with each zoom level
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}