// The view from the spacecraft behind the overview: a sparse two-speed starfield, a close planetary
// limb and a soft edge light, chosen by the active scenario's gravity context. The planet is
// illustrative context only: it follows the explicit gravity setting and is never inferred from
// oxygen or pressure. Everything is drawn procedurally into small cached canvases, offline.
//
// Contexts: earth (1 g), orbit (ISS, microgravity), moon, mars, none (a neutral starfield).
// set(ctx, framing) travels between bodies in about a second (outgoing and incoming bodies in
// separate layers, stars at two speeds) and makes a quick framing change when only the habitat
// atmosphere changed on the same body. The latest call always wins; animations restart from the
// current on-screen state. Reduced motion swaps with a short fade.
window.Voyage = (() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const TILE = 512;
  // cap: visible height of the limb as a share of the viewport; R: radius in viewport widths;
  // cx: where the disc's centre sits across the screen; rim: edge-light colour; stars: layer opacity.
  const CTX = {
    earth: { cap: 0.3, R: 1.55, cx: 0.6, rim: [120, 205, 255], rimA: 0.55, haze: 0.06, amb: "rgba(70, 170, 235, .20)", stars: [0.55, 0.45] },
    orbit: { cap: 0.17, R: 0.95, cx: 0.5, rim: [95, 150, 255], rimA: 0.5, haze: 0.07, amb: "rgba(60, 105, 220, .16)", stars: [1, 0.95] },
    moon: { cap: 0.26, R: 1.25, cx: 0.4, rim: [225, 230, 238], rimA: 0.42, haze: 0.012, amb: "rgba(205, 212, 224, .10)", stars: [0.9, 0.8] },
    mars: { cap: 0.22, R: 1.9, cx: 0.62, rim: [214, 140, 92], rimA: 0.38, haze: 0.07, amb: "rgba(196, 112, 64, .14)", stars: [0.7, 0.55] },
    none: { stars: [1, 0.85] },
  };
  const BODIES = ["earth", "orbit", "moon", "mars"];
  let root, bodiesBox, farEl, nearEl;
  const els = {}, amb = {}, sprite = {}, frame = {};
  let W = 0, H = 0, cur = null, curFrame = "", farOff = 0, nearOff = 0, scrollY = 0, starAnim = 0;

  // ------------------------------------------------------------- noise (seeded, 3D value noise)
  function hash(x, y, z) {
    let h = (x * 374761393 + y * 668265263 + z * 2147483647) | 0;
    h = (h ^ (h >>> 13)) * 1274126177;
    return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
  }
  const fade = (t) => t * t * (3 - 2 * t);
  function noise(x, y, z) {
    const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
    const xf = fade(x - xi), yf = fade(y - yi), zf = fade(z - zi);
    const L = (a, b, t) => a + (b - a) * t;
    const c = (dx, dy, dz) => hash(xi + dx, yi + dy, zi + dz);
    return L(L(L(c(0, 0, 0), c(1, 0, 0), xf), L(c(0, 1, 0), c(1, 1, 0), xf), yf),
      L(L(c(0, 0, 1), c(1, 0, 1), xf), L(c(0, 1, 1), c(1, 1, 1), xf), yf), zf);
  }
  function fbm(x, y, z, oct) {
    let a = 0.5, f = 1, s = 0, n = 0;
    for (let i = 0; i < oct; i++) { s += a * noise(x * f, y * f, z * f); n += a; a *= 0.5; f *= 2.03; }
    return s / n;
  }
  const mix = (a, b, t) => a + (b - a) * t;
  const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

  // ------------------------------------------------------------- one body, drawn once per size
  function geom(name) {
    const c = CTX[name];
    const R = c.R * W, cap = c.cap * H, pad = Math.round(H * 0.16);
    return { R, cap, pad, h: Math.round(cap + pad), cx: c.cx * W, cy: pad + R };
  }
  function shade(name, nx, ny, nz, lit) {
    // nx, ny, nz: unit surface normal (ny < 0 is up); returns [r, g, b] before lighting
    if (name === "earth" || name === "orbit") {
      const p = 2.6;
      const w = fbm(nx * p + 3.1, ny * p, nz * p, 3) * 1.6;
      const land = fbm(nx * p + w, ny * p + 7.7, nz * p, 5);
      let col = land > 0.56
        ? [mix(46, 112, smooth(0.56, 0.75, land)), mix(70, 104, smooth(0.56, 0.75, land)), mix(48, 70, smooth(0.56, 0.75, land))]
        : [mix(8, 24, land), mix(34, 82, land), mix(78, 150, land)];
      const cl = smooth(0.5, 0.74, fbm(nx * 4.4 + w * 0.8, ny * 6.2, nz * 4.4 + 11, 5));
      col = col.map((v) => mix(v, 236, cl * 0.92));
      return col;
    }
    if (name === "moon") {
      const m = fbm(nx * 1.6, ny * 1.6 + 4, nz * 1.6, 3);         // maria: large dark plains
      const g = fbm(nx * 9, ny * 9, nz * 9, 4);                    // regolith grain
      const v = mix(150, 196, g) * (m < 0.45 ? 0.68 : 1);
      return [v, v, v * 1.02];
    }
    // mars: rust plains, darker albedo features, a little dust
    const d = fbm(nx * 2.2 + 9, ny * 2.2, nz * 2.2, 3);
    const g = fbm(nx * 7, ny * 7, nz * 7 + 3, 4);
    const k = d < 0.42 ? 0.62 : 1;
    return [mix(150, 206, g) * k, mix(66, 104, g) * k, mix(38, 62, g) * k];
  }
  function draw(name) {
    const G = geom(name), c = CTX[name];
    const cv = document.createElement("canvas");
    cv.width = Math.max(1, Math.round(W)); cv.height = Math.max(1, G.h);
    cv.className = "v-body"; cv.dataset.ctx = name;
    const x = cv.getContext("2d");
    // the disc, shaded at half resolution (the surface is soft at this scale) and scaled up
    const s = 0.5, w = Math.max(1, Math.round(cv.width * s)), h = Math.max(1, Math.round(cv.height * s));
    const lo = document.createElement("canvas"); lo.width = w; lo.height = h;
    const lx = lo.getContext("2d"), img = lx.createImageData(w, h), D = img.data;
    const L = [-0.62, -0.55, 0.56], ll = Math.hypot(...L); L[0] /= ll; L[1] /= ll; L[2] /= ll;
    for (let j = 0; j < h; j++) {
      const py = j / s;
      for (let i = 0; i < w; i++) {
        const px = i / s, dx = (px - G.cx) / G.R, dy = (py - G.cy) / G.R, r2 = dx * dx + dy * dy;
        if (r2 > 1) continue;
        const nz = Math.sqrt(1 - r2);
        const lam = Math.max(0, dx * L[0] + dy * L[1] + nz * L[2]);
        const limb = 0.35 + 0.65 * Math.pow(nz, 0.35);
        const col = shade(name, dx, dy, nz);
        const k = (0.16 + 0.84 * lam) * limb, o = (j * w + i) * 4;
        D[o] = Math.min(255, col[0] * k); D[o + 1] = Math.min(255, col[1] * k); D[o + 2] = Math.min(255, col[2] * k);
        // feather the very edge so the limb is not stair-stepped
        D[o + 3] = Math.round(255 * Math.min(1, (1 - Math.sqrt(r2)) * G.R * 0.9));
      }
    }
    lx.putImageData(img, 0, 0);
    x.imageSmoothingQuality = "high";
    x.drawImage(lo, 0, 0, cv.width, cv.height);
    if (name === "moon") craters(x, G);
    // edge light: a soft glow above the limb, brightest on the lit side, and a thin bright edge
    const [r, g, b] = c.rim;
    x.globalCompositeOperation = "lighter";
    const inner = G.R * (1 - c.haze * 0.25), outer = G.R + G.pad * (name === "moon" ? 0.35 : 0.95);
    const rg = x.createRadialGradient(G.cx, G.cy, inner, G.cx, G.cy, outer);
    const tR = (G.R - inner) / (outer - inner);
    rg.addColorStop(0, `rgba(${r},${g},${b},0)`);
    rg.addColorStop(Math.max(0.001, tR * 0.7), `rgba(${r},${g},${b},${c.rimA * 0.35})`);
    rg.addColorStop(tR, `rgba(${r},${g},${b},${c.rimA})`);
    rg.addColorStop(Math.min(0.999, tR + (1 - tR) * 0.18), `rgba(${r},${g},${b},${c.rimA * 0.32})`);
    rg.addColorStop(1, `rgba(${r},${g},${b},0)`);
    x.fillStyle = rg;
    x.fillRect(0, 0, cv.width, cv.height);
    // shade the glow toward the night side
    x.globalCompositeOperation = "destination-out";
    const side = x.createLinearGradient(0, 0, cv.width, 0);
    side.addColorStop(0, "rgba(0,0,0,0)"); side.addColorStop(0.55, "rgba(0,0,0,0)"); side.addColorStop(1, "rgba(0,0,0,.55)");
    x.fillStyle = side;
    x.beginPath(); x.rect(0, 0, cv.width, cv.height); x.arc(G.cx, G.cy, G.R - 1, 0, Math.PI * 2, true); x.fill("evenodd");
    x.globalCompositeOperation = "source-over";
    return cv;
  }
  function craters(x, G) {
    let seed = 11;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const n = Math.round(160 * W / 1440);
    for (let i = 0; i < n; i++) {
      const px = rnd() * W, depth = Math.pow(rnd(), 1.6);              // more craters near the limb
      const py = G.pad + depth * G.cap;
      const dx = (px - G.cx) / G.R, dy = (py - G.cy) / G.R, r2 = dx * dx + dy * dy;
      if (r2 > 0.995) continue;
      const nz = Math.sqrt(1 - r2);
      const rx = (2 + Math.pow(rnd(), 3) * 26) * (W / 1440), ry = rx * Math.max(0.12, nz * 1.1);
      x.save(); x.translate(px, py); x.scale(1, ry / rx);
      const g = x.createRadialGradient(-rx * 0.15, -rx * 0.15, 0, 0, 0, rx);
      g.addColorStop(0, "rgba(20,20,22,.34)"); g.addColorStop(0.75, "rgba(20,20,22,.18)");
      g.addColorStop(0.86, "rgba(235,236,240,.22)"); g.addColorStop(1, "rgba(235,236,240,0)");
      x.fillStyle = g; x.beginPath(); x.arc(0, 0, rx, 0, Math.PI * 2); x.fill();
      x.restore();
    }
  }

  // ------------------------------------------------------------- stars
  function starTile(n, rmin, rmax, amin, amax, seed0) {
    const c = document.createElement("canvas"); c.width = c.height = TILE;
    const x = c.getContext("2d");
    let seed = seed0;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < n; i++) {
      const px = rnd() * TILE, py = rnd() * TILE, r = mix(rmin, rmax, rnd()), a = mix(amin, amax, rnd());
      const warm = rnd() < 0.18;
      x.fillStyle = warm ? `rgba(255,232,205,${a})` : `rgba(226,234,250,${a})`;
      for (const [ox, oy] of [[0, 0], [TILE, 0], [-TILE, 0], [0, TILE], [0, -TILE]]) { x.beginPath(); x.arc(px + ox, py + oy, r, 0, 6.2832); x.fill(); }
    }
    return c.toDataURL("image/png");
  }
  const wrap = (v) => ((v % TILE) + TILE) % TILE;
  function placeStars() {
    farEl.style.transform = `translate3d(0, ${wrap(farOff - scrollY * 0.02).toFixed(1)}px, 0)`;
    nearEl.style.transform = `translate3d(0, ${wrap(nearOff - scrollY * 0.07).toFixed(1)}px, 0)`;
  }
  function moveStars(dFar, dNear, dur) {
    cancelAnimationFrame(starAnim);
    const f0 = farOff, n0 = nearOff, f1 = farOff + dFar, n1 = nearOff + dNear;
    if (reduce || !dur) { farOff = f1; nearOff = n1; placeStars(); return; }
    const t0 = performance.now();
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / dur), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      farOff = f0 + (f1 - f0) * e; nearOff = n0 + (n1 - n0) * e; placeStars();
      if (k < 1) starAnim = requestAnimationFrame(tick);
    };
    starAnim = requestAnimationFrame(tick);
  }

  // ------------------------------------------------------------- framing
  function framingOf(name, key) {
    // a small, repeatable change in framing and light per habitat atmosphere on the same body
    let h = 0;
    for (const ch of String(key || "")) h = (h * 31 + ch.charCodeAt(0)) | 0;
    const u = ((h >>> 0) % 1000) / 1000, v = (((h >>> 0) / 1000 | 0) % 1000) / 1000;
    const cap = (CTX[name] ? CTX[name].cap : 0.2) * H;
    return { dy: (u - 0.5) * cap * 0.28, rot: (v - 0.5) * 2.2, light: 0.85 + 0.3 * v };
  }
  const tf = (f) => `translate3d(0, ${f.dy.toFixed(1)}px, 0) rotate(${f.rot.toFixed(2)}deg)`;
  function ensure(name) {
    if (!BODIES.includes(name)) return null;
    if (!sprite[name]) {
      const cv = draw(name);
      sprite[name] = cv;
      const el = els[name];
      el.innerHTML = ""; el.appendChild(cv);
      el.style.height = `${cv.height}px`;
    }
    return els[name];
  }
  function animate(el, to, opts) {
    const cs = getComputedStyle(el), from = { transform: cs.transform === "none" ? "translate3d(0,0,0)" : cs.transform, opacity: cs.opacity };
    el.getAnimations().forEach((a) => a.cancel());
    el.style.transform = to.transform; el.style.opacity = to.opacity;
    if (opts && opts.duration) el.animate([from, to], Object.assign({ fill: "backwards" }, opts));
  }
  function setStarsFor(name, dur) {
    const s = CTX[name].stars;
    for (const [el, a] of [[farEl, s[0]], [nearEl, s[1]]]) animate(el.parentElement, { transform: "none", opacity: String(a) }, dur ? { duration: dur, easing: "ease" } : null);
  }

  // ------------------------------------------------------------- public
  function set(name, key, opt = {}) {
    if (!root) return;
    if (!CTX[name]) name = "none";
    const instant = opt.instant || cur === null;
    if (name === cur && key === curFrame) return;
    const travel = name !== cur;
    const prev = cur;
    cur = name; curFrame = key;
    const f = framingOf(name, key);
    frame[name] = f;
    const incoming = ensure(name);
    // bodies
    for (const b of BODIES) {
      const el = els[b];
      if (b === name) {
        const show = { transform: tf(f), opacity: "1" };
        if (instant) { animate(el, show); continue; }
        if (reduce) { animate(el, show, { duration: 220, easing: "ease" }); continue; }
        if (travel) {
          // rise into frame from below, after the outgoing body has started to leave
          if (+getComputedStyle(el).opacity < 0.05) { el.getAnimations().forEach((a) => a.cancel()); el.style.transform = `translate3d(0, ${(el.offsetHeight * 0.92).toFixed(0)}px, 0)`; el.style.opacity = "0"; }
          animate(el, show, { duration: 820, delay: prev && prev !== "none" ? 170 : 0, easing: "cubic-bezier(0.16, 0.84, 0.3, 1)" });
        } else {
          animate(el, show, { duration: 420, easing: "cubic-bezier(0.23, 1, 0.32, 1)" });
        }
      } else if (+getComputedStyle(el).opacity > 0.001 || el.getAnimations().length) {
        // the outgoing body drifts away: it sinks and recedes in its own layer
        const gone = { transform: `translate3d(0, ${(el.offsetHeight * 0.55).toFixed(0)}px, 0) scale(0.9)`, opacity: "0" };
        if (instant) animate(el, gone);
        else animate(el, gone, { duration: reduce ? 220 : 700, easing: reduce ? "ease" : "cubic-bezier(0.55, 0, 0.75, 0.3)" });
      }
    }
    // edge light
    for (const b of BODIES) {
      const on = b === name, el = amb[b];
      const to = { transform: "none", opacity: on ? String(Math.min(1, f.light)) : "0" };
      animate(el, to, instant ? null : { duration: reduce ? 220 : travel ? 900 : 380, easing: "ease" });
    }
    // stars: the far field drifts a little, the near field more, so depth reads during the trip
    setStarsFor(name, instant ? 0 : reduce ? 220 : 900);
    if (!instant) { if (travel) moveStars(34, 120, 980); else moveStars(5, 18, 420); }
    root.dataset.ctx = name;
    if (incoming && !instant) incoming.dataset.arrive = String(Date.now());
    // draw the other bodies while the browser is idle, so the next trip starts without a stall
    idle(() => BODIES.forEach((b) => ensure(b)));
  }
  const idle = (fn) => (window.requestIdleCallback ? requestIdleCallback(fn, { timeout: 1500 }) : setTimeout(fn, 400));

  function resize() {
    const w = window.innerWidth, h = window.innerHeight;
    if (Math.abs(w - W) < 2 && Math.abs(h - H) < 60 && W) return;   // ignore mobile toolbar wobble
    W = w; H = h;
    for (const b of BODIES) { delete sprite[b]; els[b].innerHTML = ""; }
    for (const b of BODIES) {
      const c = CTX[b], el = amb[b];
      el.style.background = `radial-gradient(${Math.round(110 * c.R)}% ${Math.round(c.cap * 190)}% at ${Math.round(c.cx * 100)}% 100%, ${c.amb}, transparent 70%)`;
    }
    if (cur) {
      const f = framingOf(cur, curFrame);
      ensure(cur);
      if (els[cur]) { els[cur].getAnimations().forEach((a) => a.cancel()); els[cur].style.transform = tf(f); els[cur].style.opacity = "1"; }
      idle(() => BODIES.forEach((b) => ensure(b)));
    }
  }

  return {
    init(el) {
      root = el;
      root.innerHTML = `<div class="v-stars-wrap"><div class="v-stars far"></div></div><div class="v-stars-wrap"><div class="v-stars near"></div></div><div class="v-bodies"></div>`;
      farEl = root.querySelector(".far"); nearEl = root.querySelector(".near");
      bodiesBox = root.querySelector(".v-bodies");
      for (const b of BODIES) {
        const a = document.createElement("div"); a.className = "v-amb"; a.dataset.ctx = b; a.style.opacity = "0"; bodiesBox.appendChild(a); amb[b] = a;
      }
      for (const b of BODIES) {
        const d = document.createElement("div"); d.className = "v-layer"; d.dataset.ctx = b; d.style.opacity = "0"; bodiesBox.appendChild(d); els[b] = d;
      }
      farEl.style.backgroundImage = `url(${starTile(150, 0.35, 0.8, 0.18, 0.55, 3)})`;
      nearEl.style.backgroundImage = `url(${starTile(26, 0.75, 1.35, 0.45, 0.9, 17)})`;
      resize();
      placeStars();
      let rt = 0;
      window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(resize, 160); });
    },
    set,
    scroll(y, dim) {
      scrollY = y;
      placeStars();
      if (bodiesBox) bodiesBox.style.opacity = dim.toFixed(3);
    },
    current() { return { ctx: cur, framing: curFrame }; },
  };
})();
