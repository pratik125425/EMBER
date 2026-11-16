// The star-atlas plate: stars, constellations, targets, the draggable reticle and the one vector.
// It only draws and reports where the reticle went; every relevance number comes from Python.
window.Plate = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (id) => document.getElementById(id);
  const svgEl = (tag, attrs = {}, parent) => {
    const el = document.createElementNS(NS, tag);
    for (const k in attrs) el.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(el);
    return el;
  };
  const fmt = (v, d = 1) => Number(v).toFixed(d);
  const psi = (kpa) => kpa / 6.894757;
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let hooks = { onMove() {}, onCommit() {} };
  let maxH = 640, revealed = false, revealWanted = false;

  let args = null, sky = null, W = 0, H = 0, M = null;
  let ret = { x: 0.34, p: 56.5 };        // reticle position (fraction, kPa)
  let trail = [];
  let pinned = null, hoverInv = null;
  try { trail = JSON.parse(sessionStorage.getItem("ember-atlas-trail") || "[]"); } catch (e) { trail = []; }

  // ---------------------------------------------------------------- scales
  const sx = (x) => M.l + (x - sky.x_range[0]) / (sky.x_range[1] - sky.x_range[0]) * (W - M.l - M.r);
  const pTop = () => sky.p_range[1] * 1.14;  // headroom: stars at the top of the range stay inside the frame
  const sy = (p) => {
    const p0 = sky.p_range[0], p1 = pTop();
    return H - M.b - Math.log(p / p0) / Math.log(p1 / p0) * (H - M.t - M.b);
  };
  const ix = (px) => sky.x_range[0] + (px - M.l) / (W - M.l - M.r) * (sky.x_range[1] - sky.x_range[0]);
  const iy = (py) => {
    const p0 = sky.p_range[0], p1 = pTop();
    return p0 * Math.pow(p1 / p0, (H - M.b - py) / (H - M.t - M.b));
  };
  const clamp = (pos) => ({
    x: Math.min(Math.max(pos.x, sky.x_range[0]), sky.x_range[1]),
    p: Math.min(Math.max(pos.p, sky.p_range[0]), sky.p_range[1]),
  });
  function applyHighlight() {
    const inv = hoverInv || pinned;
    const root = $("sky");
    if (!root) return;
    root.classList.toggle("dim", !!inv);
    root.querySelectorAll("[data-inv]").forEach((el) => el.classList.toggle("on", el.dataset.inv === inv));
  }

  // ---------------------------------------------------------------- labels
  // Plate labels never sit on a star or another label: each tries its candidate positions in
  // order and takes the first clear one (or the least-covered one).
  let occupied = [], baseOccupied = [];
  const overlap = (b) => {
    let s = 0;
    for (const o of occupied) {
      const w = Math.min(b.x + b.w, o.x + o.w) - Math.max(b.x, o.x), h = Math.min(b.y + b.h, o.y + o.h) - Math.max(b.y, o.y);
      if (w > 0 && h > 0) s += w * h;
    }
    return s;
  };
  const inFrame = (b) => b.x >= M.l + 2 && b.x + b.w <= W - M.r - 2 && b.y >= M.t + 2 && b.y + b.h <= H - M.b - 2;
  function placeLabel(t, cands, list = occupied) {
    const saved = occupied; occupied = list;
    let best = null, bs = Infinity;
    for (const [x, y, an] of cands) {
      t.setAttribute("x", x); t.setAttribute("y", y); t.setAttribute("text-anchor", an);
      const bb = t.getBBox(), b = { x: bb.x - 3, y: bb.y - 1, w: bb.width + 6, h: bb.height + 2 };
      const sc = overlap(b) + (inFrame(b) ? 0 : 1e6);
      if (sc < bs) { bs = sc; best = [x, y, an, b]; }
      if (sc === 0) break;
    }
    t.setAttribute("x", best[0]); t.setAttribute("y", best[1]); t.setAttribute("text-anchor", best[2]);
    list.push(best[3]);
    occupied = saved;
    return best[3];
  }
  const boxAt = (cx, cy, r) => ({ x: cx - r, y: cy - r, w: 2 * r, h: 2 * r });

  // ---------------------------------------------------------------- the plate
  function renderPlate() {
    const T = args.theme, svg = $("plate");
    const wrap = $("platewrap");
    W = Math.max(280, wrap.clientWidth);
    const narrow = W < 620;
    H = narrow ? Math.round(Math.min(Math.max(W * 1.05, 360), 520)) : Math.round(Math.min(Math.max(W * 0.62, 420), maxH));
    M = narrow ? { l: 40, r: 12, t: 14, b: 40 } : { l: 52, r: 52, t: 18, b: 44 };
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("height", H);
    svg.innerHTML = "";

    const defs = svgEl("defs", {}, svg);
    const f = svgEl("filter", { id: "haze", x: "-20%", y: "-20%", width: "140%", height: "140%" }, defs);
    svgEl("feGaussianBlur", { stdDeviation: narrow ? 10 : 16 }, f);
    const clip = svgEl("clipPath", { id: "inner" }, defs);
    svgEl("rect", { x: M.l, y: M.t, width: W - M.l - M.r, height: H - M.t - M.b }, clip);

    // plate frame: double rule, as on a printed plate
    svgEl("rect", { x: M.l, y: M.t, width: W - M.l - M.r, height: H - M.t - M.b, fill: "none", stroke: T.ink2, "stroke-width": 1, opacity: .55 }, svg);
    svgEl("rect", { x: M.l - 4, y: M.t - 4, width: W - M.l - M.r + 8, height: H - M.t - M.b + 8, fill: "none", stroke: T.line, "stroke-width": 1 }, svg);

    const g = svgEl("g", { "clip-path": "url(#inner)" }, svg);
    // haze: where tests exist (drawn first, beneath everything)
    const haze = svgEl("g", { filter: "url(#haze)", opacity: .2 }, g);
    for (const s of sky.stars) svgEl("circle", { cx: sx(s.x), cy: sy(s.p), r: narrow ? 14 : 22, fill: T.ink }, haze);
    for (const n of sky.nebulae) svgEl("rect", { x: sx(n.x0) - 8, y: sy(n.p1) - 8, width: sx(n.x1) - sx(n.x0) + 16, height: sy(n.p0) - sy(n.p1) + 16, fill: T.ink }, haze);

    // graticule
    const grat = svgEl("g", { stroke: T.line, "stroke-width": 1 }, g);
    for (let x = 0.15; x < 0.6; x += 0.05) svgEl("line", { x1: sx(x), x2: sx(x), y1: M.t, y2: H - M.b }, grat);
    const pt = [30, 50, 70, 100, 150];
    for (const p of pt) svgEl("line", { x1: M.l, x2: W - M.r, y1: sy(p), y2: sy(p) }, grat);

    // ppO₂ isolines: the plate's ecliptic curves (x · p = const)
    const iso = svgEl("g", { fill: "none", stroke: T.ink2, "stroke-width": .8, "stroke-dasharray": "1 4", opacity: .7 }, g);
    for (const k of sky.ppo2) {
      let d = "";
      for (let i = 0; i <= 60; i++) {
        const x = sky.x_range[0] + (sky.x_range[1] - sky.x_range[0]) * i / 60;
        const p = k / x;
        if (p < sky.p_range[0] * 0.98 || p > pTop()) continue;
        d += (d ? "L" : "M") + sx(x).toFixed(1) + " " + sy(p).toFixed(1);
      }
      if (d) svgEl("path", { d }, iso);
      const xl = Math.min(sky.x_range[1] - 0.01, k / sky.p_range[0] * 0.98);
      const pl = k / xl;
      if (pl >= sky.p_range[0] && pl <= sky.p_range[1] && !narrow) {
        const t = svgEl("text", { x: sx(xl) - 4, y: sy(pl) - 5, "text-anchor": "end", class: "iso-label" }, g);
        t.textContent = `ppO₂ ${k} kPa`;
      }
    }

    // NASA target atmospheres: designated objects in gold
    for (const t of sky.targets) {
      const cx = sx(t.x), cy = sy(t.p);
      const [tx, tp] = sky.target_tol;
      svgEl("rect", { x: sx(t.x - tx), y: sy(t.p * (1 + tp)), width: sx(t.x + tx) - sx(t.x - tx), height: sy(t.p * (1 - tp)) - sy(t.p * (1 + tp)), fill: "none", stroke: T.gold, "stroke-width": .8, "stroke-dasharray": "2 2", opacity: .9 }, g);
      svgEl("circle", { cx, cy, r: 6, fill: "none", stroke: T.gold, "stroke-width": 1 }, g);
      svgEl("path", { d: `M${cx} ${cy - 11}V${cy - 7}M${cx} ${cy + 7}V${cy + 11}M${cx - 11} ${cy}H${cx - 7}M${cx + 7} ${cy}H${cx + 11}`, stroke: T.gold, "stroke-width": 1 }, g);
    }

    // sky: constellations, nebulae, stars
    const skyG = svgEl("g", { id: "sky", class: revealed ? "" : "unrevealed" }, g);
    for (const c of sky.constellations) {
      const cg = svgEl("g", { class: "const", "data-inv": c.inv }, skyG);
      for (const [x0, p0, x1, p1] of c.lines) svgEl("line", { x1: sx(x0), y1: sy(p0), x2: sx(x1), y2: sy(p1), stroke: T.ink2, "stroke-width": .7, opacity: .55 }, cg);
    }
    for (const n of sky.nebulae) {
      const x0 = sx(n.x0), x1 = sx(n.x1), y0 = sy(n.p1), y1 = sy(n.p0);
      svgEl("ellipse", { class: "neb", "data-inv": n.inv, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, rx: Math.max(5, (x1 - x0) / 2 + 3), ry: Math.max(5, (y1 - y0) / 2 + 3), fill: T.ink, "fill-opacity": .05, stroke: T.ink2, "stroke-width": .9, "stroke-dasharray": "2 2" }, skyG);
    }
    const stars = [...sky.stars].sort((a, b) => b.n - a.n);
    for (const s of stars) {
      const r = Math.min(7, 1.5 + 1.25 * Math.log2(s.n + 0.5));
      svgEl("circle", { class: "star", "data-inv": s.inv, cx: sx(s.x), cy: sy(s.p), r: r + 1.2, fill: T.plate }, skyG);
      svgEl("circle", { class: "star", "data-inv": s.inv, cx: sx(s.x), cy: sy(s.p), r, fill: T.ink }, skyG);
    }

    // labels last, placed clear of stars, target marks, rank rings and each other
    occupied = sky.stars.map((s) => boxAt(sx(s.x), sy(s.p), Math.min(7, 1.5 + 1.25 * Math.log2(s.n + 0.5)) + 2));
    for (const t of sky.targets) occupied.push(boxAt(sx(t.x), sy(t.p), 11));
    for (const r of args.ranked.slice(1)) if (r.pos) occupied.push(boxAt(sx(r.pos[0]), sy(r.pos[1]), 10));
    const labG = svgEl("g", { id: "labels" }, skyG);
    for (const t of sky.targets) {
      const cx = sx(t.x), cy = sy(t.p);
      const lab = svgEl("text", { class: "target-label" }, labG);
      lab.textContent = t.name.replace("Exploration Atm 8.2/34", "Exploration Atmosphere").replace("ISS/Earth", "ISS / Earth air");
      placeLabel(lab, [[cx + 14, cy + 18, "start"], [cx + 14, cy - 9, "start"], [cx - 14, cy + 18, "end"], [cx - 14, cy - 9, "end"],
        [cx, cy + 30, "middle"], [cx, cy - 18, "middle"], [cx + 16, cy + 32, "start"], [cx - 16, cy - 22, "end"]]);
    }
    if (!narrow) {
      for (const c of sky.constellations) {
        const lx = sx(c.label[0]), ly = sy(c.label[1]);
        const t = svgEl("text", { class: "const-label const", "data-inv": c.inv }, labG);
        t.textContent = c.inv;
        placeLabel(t, [[lx - 2, ly - 13, "start"], [lx - 10, ly + 5, "end"], [lx - 2, ly + 22, "start"], [lx - 10, ly - 13, "end"],
          [lx - 10, ly + 22, "end"], [lx - 2, ly - 28, "start"], [lx - 2, ly + 36, "start"]]);
      }
    }
    baseOccupied = occupied.slice();

    // axes
    const ax = svgEl("g", {}, svg);
    for (let x = 0.10; x <= 0.6001; x += 0.05) {
      svgEl("line", { x1: sx(x), x2: sx(x), y1: H - M.b + 4, y2: H - M.b + 9, stroke: T.ink2 }, ax);
      if (!narrow || Math.round(x * 100) % 10 === 0) {
        const t = svgEl("text", { x: sx(x), y: H - M.b + 22, "text-anchor": "middle", class: "tick" }, ax);
        t.textContent = `${Math.round(x * 100)}%`;
      }
    }
    for (let x = 0.10; x < 0.6; x += 0.01) svgEl("line", { x1: sx(x), x2: sx(x), y1: H - M.b + 4, y2: H - M.b + 6, stroke: T.line }, ax);
    const at = svgEl("text", { x: M.l + (W - M.l - M.r) / 2, y: H - 4, "text-anchor": "middle", class: "axis-title" }, ax);
    at.textContent = "Oxygen in the atmosphere, %";
    for (const p of [20, 30, 50, 70, 101.3, 150, 210]) {
      svgEl("line", { x1: M.l - 9, x2: M.l - 4, y1: sy(p), y2: sy(p), stroke: T.ink2 }, ax);
      const t = svgEl("text", { x: M.l - 12, y: sy(p) + 4, "text-anchor": "end", class: "tick" }, ax);
      t.textContent = p === 101.3 ? "101" : String(p);
    }
    const yt = svgEl("text", { x: 12, y: M.t + (H - M.t - M.b) / 2, "text-anchor": "middle", class: "axis-title", transform: `rotate(-90 12 ${M.t + (H - M.t - M.b) / 2})` }, ax);
    yt.textContent = "Total pressure, kPa";
    if (!narrow) {
      for (const q of [3, 5, 8.2, 14.7, 30]) {
        const p = q * 6.894757;
        if (p < sky.p_range[0] || p > sky.p_range[1] + 1) continue;
        svgEl("line", { x1: W - M.r + 4, x2: W - M.r + 9, y1: sy(p), y2: sy(p), stroke: T.ink2 }, ax);
        const t = svgEl("text", { x: W - M.r + 12, y: sy(p) + 4, class: "tick" }, ax);
        t.textContent = String(q);
      }
      const rt = svgEl("text", { x: W - 8, y: M.t + (H - M.t - M.b) / 2, "text-anchor": "middle", class: "axis-title", transform: `rotate(90 ${W - 8} ${M.t + (H - M.t - M.b) / 2})` }, ax);
      rt.textContent = "psia";
    }

    // ranks 2–5: ringed and numbered where charted
    const rk = svgEl("g", { id: "ranks" }, g);
    for (const r of args.ranked.slice(1)) {
      if (!r.pos) continue;
      const cx = sx(r.pos[0]), cy = sy(r.pos[1]);
      svgEl("circle", { cx, cy, r: 9, fill: "none", stroke: T.ink, "stroke-width": 1, opacity: .8 }, rk);
      const t = svgEl("text", { x: cx + 11, y: cy - 8, class: "rank-label" }, rk);
      t.textContent = String(r.rank);
    }

    // trail of past positions, then the vector, then the reticle
    svgEl("g", { id: "trail" }, g);
    svgEl("g", { id: "vector" }, g);
    const R = svgEl("g", { id: "reticle", tabindex: 0, role: "slider", "aria-label": "Scenario reticle. Arrow keys move oxygen and pressure.", "aria-valuetext": "" }, svg);
    svgEl("circle", { r: 24, fill: "transparent" }, R);
    svgEl("circle", { class: "pulse", r: 13, fill: "none", stroke: T.accent, "stroke-width": 1.2 }, R);
    svgEl("circle", { class: "focus", r: 21, fill: "none", stroke: T.accent, "stroke-width": 1, "stroke-dasharray": "2 3", opacity: 0 }, R);
    svgEl("circle", { class: "busyring", r: 18, fill: "none", stroke: T.accent, "stroke-width": 1.2, "stroke-dasharray": "6 8", opacity: 0 }, R);
    svgEl("circle", { class: "ring", r: 13, fill: "none", stroke: T.accent, "stroke-width": 1.6 }, R);
    svgEl("path", { d: "M0 -22V-16M0 16V22M-22 0H-16M16 0H22", stroke: T.accent, "stroke-width": 1.6 }, R);
    svgEl("circle", { r: 2, fill: T.accent }, R);
    bindReticle(R, svg);
    placeReticle(false);
    drawTrail();
    drawVector(false);
    applyHighlight();
  }

  function placeReticle(glide) {
    const R = $("reticle");
    if (!R) return;
    R.classList.toggle("glide", !!glide && !reduce);
    R.style.transform = `translate(${sx(ret.x).toFixed(1)}px, ${sy(ret.p).toFixed(1)}px)`;
    R.setAttribute("aria-valuetext", `${fmt(ret.x * 100)} percent oxygen, ${fmt(ret.p)} kilopascals`);
    hooks.onMove(ret);
  }

  function drawTrail() {
    const T = args.theme, tg = $("trail");
    if (!tg) return;
    tg.innerHTML = "";
    const pts = trail.slice(-9, -1);
    if (pts.length > 1) {
      const d = pts.map((q, i) => (i ? "L" : "M") + sx(q.x).toFixed(1) + " " + sy(q.p).toFixed(1)).join("") + `L${sx(ret.x).toFixed(1)} ${sy(ret.p).toFixed(1)}`;
      svgEl("path", { d, fill: "none", stroke: T.accent, "stroke-width": .8, "stroke-dasharray": "1 3", opacity: .45 }, tg);
    }
    pts.forEach((q, i) => svgEl("circle", { cx: sx(q.x), cy: sy(q.p), r: 2.4, fill: T.accent, opacity: (0.12 + 0.5 * (i + 1) / pts.length).toFixed(2) }, tg));
  }

  // The one committed diagonal: reticle → best-ranked charted test, labelled with the engine's D.
  function drawVector(animate) {
    const T = args.theme, vg = $("vector");
    if (!vg) return;
    vg.innerHTML = "";
    vg.classList.remove("pending");
    const r = args.ranked[0];
    if (!r || (!r.pos && !r.o2)) return;
    const x1 = sx(ret.x), y1 = sy(ret.p);
    const vecOcc = baseOccupied.slice();
    let x2, y2;
    if (r.pos) {
      x2 = sx(r.pos[0]); y2 = sy(r.pos[1]);
      svgEl("circle", { cx: x2, cy: y2, r: 10, fill: "none", stroke: T.accent, "stroke-width": 1.4 }, vg);
    } else {
      // Pressure not reported: the record is a meridian (its O₂ range at every pressure), not a point.
      const a = sx(r.o2[0]), b = sx(r.o2[1]);
      if (b - a > 2) svgEl("rect", { x: a, y: M.t, width: b - a, height: H - M.t - M.b, fill: T.accent, opacity: .1 }, vg);
      for (const xx of b - a > 2 ? [a, b] : [a]) svgEl("line", { x1: xx, x2: xx, y1: M.t, y2: H - M.b, stroke: T.accent, "stroke-width": 1, "stroke-dasharray": "3 4", opacity: .8 }, vg);
      const note = svgEl("text", { class: "target-label", style: `fill:${T.accent}` }, vg);
      note.textContent = `${r.inv}: pressure not reported`;
      vecOcc.push(boxAt(x1, y1, 26));
      placeLabel(note, [[b + 6, M.t + 16, "start"], [a - 6, M.t + 16, "end"], [b + 6, H - M.b - 8, "start"], [a - 6, H - M.b - 8, "end"],
        [b + 6, M.t + 34, "start"], [a - 6, M.t + 34, "end"]], vecOcc);
      x2 = ret.x < r.o2[0] ? a : ret.x > r.o2[1] ? b : x1;
      y2 = y1;
    }
    const len = Math.hypot(x2 - x1, y2 - y1);
    if (len < 18) return;
    const ux = (x2 - x1) / len, uy = (y2 - y1) / len;
    const a = { x: x1 + ux * 16, y: y1 + uy * 16 }, b = { x: x2 - ux * 11, y: y2 - uy * 11 };
    const line = svgEl("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, stroke: T.accent, "stroke-width": 1.6 }, vg);
    const L = Math.hypot(b.x - a.x, b.y - a.y);
    const text = `D ${r.lb ? "≥ " : ""}${fmt(r.D, 2)} · ${fmt(r.expD, 2)}× · ${r.inv}`;
    const lg = svgEl("g", {}, vg);
    // An engraved note beside the line: candidates along both sides, clear of the reticle and labels.
    vecOcc.push(boxAt(x1, y1, 26));
    const t = svgEl("text", { class: "vec-label" }, lg);
    t.textContent = text;
    let nx = -uy, ny = ux;
    if (ny > 0) { nx = -nx; ny = -ny; }
    const cands = [];
    for (const f of [0.5, 0.35, 0.65, 0.2, 0.8]) {
      for (const side of [1, -1]) {
        const px = a.x + (b.x - a.x) * f + nx * 16 * side, py = a.y + (b.y - a.y) * f + ny * 16 * side + 4;
        const an = Math.abs(nx) < 0.3 ? "middle" : (nx * side > 0 ? "start" : "end");
        cands.push([px, py, an]);
      }
    }
    cands.push([x1, y1 - 34, "middle"], [x1, y1 + 44, "middle"]);
    placeLabel(t, cands, vecOcc);
    if (animate && !reduce && L > 0) {
      line.style.strokeDasharray = `${L}`;
      line.animate([{ strokeDashoffset: L }, { strokeDashoffset: 0 }], { duration: 460, easing: "cubic-bezier(0.23, 1, 0.32, 1)" });
      lg.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 220, delay: 260, easing: "ease-out", fill: "backwards" });
    }
  }

  // ---------------------------------------------------------------- interaction
  function commit() {
    const pos = clamp(ret);
    trail.push({ x: pos.x, p: pos.p });
    trail = trail.slice(-12);
    try { sessionStorage.setItem("ember-atlas-trail", JSON.stringify(trail)); } catch (e) { /* storage blocked: trail lives in memory */ }
    const vg = $("vector"); if (vg) vg.classList.add("pending");
    drawTrail();
    hooks.onCommit(pos);
  }

  function bindReticle(R, svg) {
    let drag = null, raf = 0, keyTimer = 0, moved = false;
    const toLocal = (e) => {
      const b = svg.getBoundingClientRect();
      return { x: (e.clientX - b.left) * (W / b.width), y: (e.clientY - b.top) * (H / b.height) };
    };
    const inside = (q) => q.x >= M.l && q.x <= W - M.r && q.y >= M.t && q.y <= H - M.b;
    R.addEventListener("pointerdown", (e) => {
      e.preventDefault(); e.stopPropagation();
      R.setPointerCapture(e.pointerId);
      const q = toLocal(e);
      drag = { dx: q.x - sx(ret.x), dy: q.y - sy(ret.p) };   // respect where it was grabbed
      moved = false;
      R.classList.add("dragging");
      R.classList.remove("glide");
      hideTip();
      R.focus({ preventScroll: true });
    });
    let lastQ = null;
    const follow = () => {
      if (!drag || !lastQ) return;
      ret = clamp({ x: ix(lastQ.x - drag.dx), p: iy(lastQ.y - drag.dy) });
      placeReticle(false);
      const vg = $("vector"); if (vg) vg.classList.add("pending");
    };
    R.addEventListener("pointermove", (e) => {
      if (!drag) return;
      lastQ = toLocal(e);
      moved = true;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(follow);
    });
    const end = (e) => {
      if (!drag) return;
      cancelAnimationFrame(raf);
      if (e && e.type === "pointerup" && moved) { lastQ = toLocal(e); follow(); }  // land exactly where released
      drag = null; lastQ = null;
      R.classList.remove("dragging");
      if (moved) commit();
    };
    R.addEventListener("pointerup", end);
    R.addEventListener("pointercancel", end);
    // click on open sky: the reticle glides there
    svg.addEventListener("pointerdown", (e) => {
      if (e.target.closest && e.target.closest("#reticle")) return;
      const q = toLocal(e);
      if (!inside(q)) return;
      ret = clamp({ x: ix(q.x), p: iy(q.y) });
      placeReticle(true);
      commit();
    });
    R.addEventListener("keydown", (e) => {
      const big = e.shiftKey;
      let used = true;
      if (e.key === "ArrowRight") ret.x += big ? 0.05 : 0.005;
      else if (e.key === "ArrowLeft") ret.x -= big ? 0.05 : 0.005;
      else if (e.key === "ArrowUp") ret.p *= big ? 1.15 : 1.02;
      else if (e.key === "ArrowDown") ret.p /= big ? 1.15 : 1.02;
      else used = false;
      if (!used) return;
      e.preventDefault();
      ret = clamp(ret);
      placeReticle(false);
      const vg = $("vector"); if (vg) vg.classList.add("pending");
      clearTimeout(keyTimer);
      keyTimer = setTimeout(commit, 450);
    });
    // star tooltips
    svg.addEventListener("pointermove", (e) => {
      if (drag) return;
      const q = toLocal(e);
      let best = null, bd = 14;
      for (const s of sky.stars) {
        const d = Math.hypot(sx(s.x) - q.x, sy(s.p) - q.y);
        if (d < bd) { bd = d; best = s; }
      }
      if (best) showTip(best, sx(best.x), sy(best.p)); else hideTip();
      const inv = best ? best.inv : null;
      if (inv !== hoverInv && !document.activeElement.classList.contains("cell")) { hoverInv = inv; applyHighlight(); }
    });
    svg.addEventListener("pointerleave", () => { hideTip(); hoverInv = null; applyHighlight(); });
  }

  function showTip(s, x, y) {
    const tip = $("tip"), svg = $("plate");
    const k = svg.getBoundingClientRect().width / W;
    tip.innerHTML = `<i>${esc(s.inv)}</i><br>${s.n} test${s.n === 1 ? "" : "s"} · O₂ ${fmt(s.x * 100)}% · ${fmt(s.p)} kPa (${fmt(psi(s.p), 2)} psia)`;
    tip.classList.add("show");
    const tw = tip.offsetWidth;
    let left = x * k + 14, top = y * k - 46;
    if (left + tw > svg.clientWidth) left = x * k - tw - 14;
    tip.style.left = `${Math.max(0, left)}px`;
    tip.style.top = `${Math.max(0, top)}px`;
  }
  function hideTip() { $("tip").classList.remove("show"); }
  function update(a, animateVector) {
    args = a; sky = a.sky;
    ret = { x: a.scenario.x, p: a.scenario.p };
    renderPlate();
    if (animateVector) drawVector(true);
  }
  function glideTo(x, p) {
    ret = clamp({ x, p });
    placeReticle(true);
    commit();
  }
  // Steppers and other exact inputs: the reticle moves at once, the engine is asked once input settles.
  let nudgeTimer = 0;
  function nudge(x, p) {
    ret = clamp({ x, p });
    placeReticle(false);
    const vg = $("vector"); if (vg) vg.classList.add("pending");
    clearTimeout(nudgeTimer);
    nudgeTimer = setTimeout(commit, 380);
  }
  function setBusy(on) { const R = $("reticle"); if (R) R.classList.toggle("busy", !!on); }
  function setPinned(inv) { pinned = inv; applyHighlight(); }
  function setHover(inv) { hoverInv = inv; applyHighlight(); }
  // One orchestrated entrance: the sky is charted from west to east, then the constellations join.
  function reveal() {
    revealWanted = true;
    if (revealed || !$("sky")) return;
    revealed = true;
    const root = $("sky");
    root.classList.remove("unrevealed");
    if (reduce) return;
    root.querySelectorAll(".star").forEach((el) => {
      const d = (+el.getAttribute("cx") - M.l) / (W - M.l - M.r) * 900;
      el.animate([{ opacity: 0, transform: "scale(0)" }, { opacity: 1, transform: "scale(1)" }],
        { duration: 520, delay: d, easing: "cubic-bezier(0.23, 1, 0.32, 1)", fill: "backwards" });
    });
    root.querySelectorAll(".neb, .const").forEach((el) => {
      el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 600, delay: 700, easing: "ease-out", fill: "backwards" });
    });
    const v = $("vector");
    if (v) v.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 400, delay: 1100, easing: "ease-out", fill: "backwards" });
  }
  return {
    init(h) { hooks = Object.assign(hooks, h); },
    update, glideTo, nudge, setBusy, setPinned, setHover, reveal,
    setMaxHeight(h) { maxH = h; },
    get ret() { return ret; },
    // the reticle in plate coordinates (viewBox units) plus the plate size, for the opening handoff
    retLocal() { return M && sky ? { x: sx(ret.x), y: sy(ret.p), W, H } : null; },
  };
})();
