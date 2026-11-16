// Hero illustration: a burning fuel droplet whose flame changes shape with gravity.
// On Earth hot gas rises, so the flame stretches into a tall yellow teardrop; with no gravity nothing
// rises and the flame settles into a dim blue sphere around the droplet. This is a drawing of the
// physics, not a model of any test record.
window.Flame = (() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let cv, ctx, W = 0, H = 0, dpr = 1, cx = 0, cy = 0, scale = 1;
  let g = 1, gTarget = 1, running = false, visible = true, raf = 0, last = 0;
  let px = 0, py = 0, ptx = 0, pty = 0;  // pointer parallax, eased
  let zoom = 1, glowK = 1, fade = 1;     // scroll scene: move closer, dim the outer glow, hand off to the atlas
  const parts = [];
  const stars = [];
  const MAX = 700;

  // Colour ramps by flame age: buoyant (yellow core to red) and diffusion-limited (blue to violet).
  const HOT = [[255, 248, 214], [255, 214, 120], [255, 150, 60], [222, 82, 34], [120, 30, 20]];
  const COLD = [[214, 236, 255], [120, 178, 255], [78, 112, 236], [92, 64, 190], [40, 24, 90]];
  const mix = (a, b, t) => a + (b - a) * t;
  function ramp(R, t) {
    const f = Math.min(0.999, Math.max(0, t)) * (R.length - 1), i = Math.floor(f), k = f - i;
    return [mix(R[i][0], R[i + 1][0], k), mix(R[i][1], R[i + 1][1], k), mix(R[i][2], R[i + 1][2], k)];
  }
  // Pre-rendered soft sprites: 12 ages × 6 gravity steps, so drawing never builds gradients per frame.
  const sprites = [];
  function buildSprites() {
    sprites.length = 0;
    for (let gi = 0; gi < 6; gi++) {
      const row = [];
      for (let ai = 0; ai < 12; ai++) {
        // Every flame starts blue at its base; with more gravity a longer yellow-orange tail follows.
        const t = ai / 11, gw = gi / 5, thr = mix(1, 0.16, gw);
        const col = (t < thr || thr > 0.999 ? ramp(COLD, Math.min(1, t / thr) * 0.62) : ramp(HOT, 0.08 + ((t - thr) / (1 - thr)) * 0.9)).map(Math.round);
        const s = document.createElement("canvas");
        s.width = s.height = 64;
        const x = s.getContext("2d");
        const gr = x.createRadialGradient(32, 32, 0, 32, 32, 32);
        gr.addColorStop(0, `rgba(${col},1)`);
        gr.addColorStop(0.35, `rgba(${col},.55)`);
        gr.addColorStop(1, `rgba(${col},0)`);
        x.fillStyle = gr;
        x.fillRect(0, 0, 64, 64);
        row.push(s);
      }
      sprites.push(row);
    }
  }

  function resize() {
    const r = cv.getBoundingClientRect();
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = r.width; H = r.height;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // the flame sits at the centre of the viewing port (style.css .port: left 50%, top 41% / 34% on phones)
    const narrow = W < 760;
    cx = W * 0.5;
    cy = H * (narrow ? 0.34 : 0.41);
    scale = Math.min(1.7, Math.max(0.72, Math.min(W, H) / 560));
    stars.length = 0;
    const n = Math.round(W * H / 5200);
    let seed = 7;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < n; i++) stars.push({ x: rnd() * W, y: rnd() * H, r: rnd() * 1.1 + 0.2, a: rnd() * 0.6 + 0.15, d: rnd() * 0.8 + 0.2, ph: rnd() * 6.28 });
  }

  function spawn() {
    const a = Math.random() * Math.PI * 2;
    const r0 = 7 * scale;
    parts.push({
      x: cx + Math.cos(a) * r0, y: cy + Math.sin(a) * r0,
      vx: Math.cos(a) * 18 * scale, vy: Math.sin(a) * 18 * scale,
      age: 0, life: mix(1.7, 1.05, g) * (0.75 + Math.random() * 0.5),
      size: (11 + Math.random() * 11) * scale,
    });
  }

  function step(dt) {
    g += (gTarget - g) * Math.min(1, dt * 2.4);   // the morph eases, so the shape changes continuously
    const rate = Math.round(mix(4, 12, g));
    for (let i = 0; i < rate && parts.length < MAX; i++) spawn();
    const buoy = 290 * scale * g;
    const diff = 40 * scale * (1 - g * 0.55);
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i];
      p.age += dt;
      if (p.age > p.life) { parts.splice(i, 1); continue; }
      const dx = p.x - cx, dy = p.y - cy, d = Math.hypot(dx, dy) || 1;
      p.vx += (dx / d) * diff * dt + (Math.random() - 0.5) * 60 * scale * dt;
      p.vy += (dy / d) * diff * dt - buoy * dt + (Math.random() - 0.5) * 60 * scale * dt;
      // buoyant flow pulls fresh air in at the base: particles narrow toward the axis as they rise
      p.vx -= dx * g * 2.2 * dt;
      p.vx *= 1 - 1.8 * dt; p.vy *= 1 - 1.8 * dt;
      p.x += p.vx * dt; p.y += p.vy * dt;
    }
  }

  function draw(t) {
    ctx.clearRect(0, 0, W, H);
    if (fade <= 0.001) return;
    // starfield with a slow parallax
    px += (ptx - px) * 0.04; py += (pty - py) * 0.04;
    for (const s of stars) {
      const tw = reduce ? 1 : 0.75 + 0.25 * Math.sin(t * 0.0006 + s.ph);
      ctx.globalAlpha = s.a * tw;
      ctx.fillStyle = "#f2f4f8";
      ctx.beginPath();
      ctx.arc(s.x + px * s.d * 14, s.y + py * s.d * 10, s.r, 0, 6.283);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.save();
    ctx.translate(cx, cy); ctx.scale(zoom, zoom); ctx.translate(-cx, -cy);
    // ambient glow
    const gw = Math.round(g * 5);
    const glowR = mix(150, 230, g) * scale;
    const gy = cy - g * 60 * scale;
    const gr = ctx.createRadialGradient(cx, gy, 0, cx, gy, glowR);
    gr.addColorStop(0, g > 0.5 ? `rgba(255,150,60,${(0.1 + 0.12 * g) * glowK})` : `rgba(90,130,255,${(0.16 - 0.06 * g) * glowK})`);
    gr.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = gr;
    ctx.fillRect(cx - glowR, gy - glowR, glowR * 2, glowR * 2);
    // flame
    ctx.globalCompositeOperation = "lighter";
    const dim = mix(0.09, 0.42, g);
    for (const p of parts) {
      const a = p.age / p.life;
      const sp = sprites[gw][Math.min(11, Math.floor(a * 12))];
      const s = p.size * (0.6 + a * mix(1.6, 1.1, g));
      ctx.globalAlpha = fade * dim * (a < 0.12 ? a / 0.12 : 1 - (a - 0.12) / 0.88);
      ctx.drawImage(sp, p.x - s, p.y - s, s * 2, s * 2);
    }
    // a bright, slowly breathing core: in orbit the flame is a rounded shell around the droplet
    const br = (reduce ? 1 : 0.9 + 0.1 * Math.sin(t * 0.0011)) * (1 - g * 0.55) * (0.25 + 0.75 * glowK) / Math.sqrt(zoom);
    const cr = 38 * scale;
    const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, cr);
    cg.addColorStop(0, `rgba(236,244,255,${0.62 * br * fade})`);
    cg.addColorStop(0.32, `rgba(140,184,255,${0.26 * br * fade})`);
    cg.addColorStop(1, "rgba(60,90,220,0)");
    ctx.globalAlpha = 1;
    ctx.fillStyle = cg;
    ctx.fillRect(cx - cr, cy - cr, cr * 2, cr * 2);
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = fade;
    // the fuel droplet
    ctx.fillStyle = "#1b1410";
    ctx.beginPath(); ctx.arc(cx, cy, 6 * scale, 0, 6.283); ctx.fill();
    ctx.strokeStyle = "rgba(255,200,140,.35)"; ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();
    ctx.globalAlpha = 1;
  }

  function loop(t) {
    if (!running) return;
    const dt = Math.min(0.033, (t - (last || t)) / 1000);
    last = t;
    step(dt);
    draw(t);
    raf = requestAnimationFrame(loop);
  }
  function settle() {
    // reduced motion: simulate to a steady state and draw one still frame
    g = gTarget; parts.length = 0;
    for (let i = 0; i < 160; i++) step(1 / 60);
    draw(0);
  }
  function setRunning(on) {
    if (reduce) { settle(); return; }
    if (on === running) return;
    running = on; last = 0;
    if (on) raf = requestAnimationFrame(loop); else cancelAnimationFrame(raf);
  }

  return {
    init(canvas) {
      cv = canvas; ctx = cv.getContext("2d");
      buildSprites(); resize();
      // a still frame at once, so the first paint is never an empty field
      g = gTarget; for (let i = 0; i < 120; i++) step(1 / 60); draw(0);
      new ResizeObserver(() => { resize(); if (reduce) { settle(); return; } parts.length = 0; for (let i = 0; i < 120; i++) step(1 / 60); draw(performance.now()); }).observe(cv);
      new IntersectionObserver(([e]) => { visible = e.isIntersecting; setRunning(visible && !document.hidden && fade > 0.001); }, { threshold: 0 }).observe(cv);
      document.addEventListener("visibilitychange", () => setRunning(visible && !document.hidden && fade > 0.001));
      window.addEventListener("pointermove", (e) => {
        ptx = (e.clientX / window.innerWidth - 0.5) * 2;
        pty = (e.clientY / window.innerHeight - 0.5) * 2;
      }, { passive: true });
      setRunning(true);
    },
    setGravity(v) { gTarget = Math.max(0, Math.min(1, v)); if (reduce) settle(); },
    setInitialGravity(v) { g = gTarget = Math.max(0, Math.min(1, v)); },
    // p in [0, 1]: the scroll position inside the opening scene. Reversible by construction.
    setScene(p) {
      const sm = (a, b, x) => { const k = Math.min(1, Math.max(0, (x - a) / (b - a))); return k * k * (3 - 2 * k); };
      zoom = 1 + 1.7 * sm(0, 1, p);
      glowK = 1 - 0.85 * sm(0, 0.6, p);
      fade = 1 - sm(0.5, 0.92, p);
      if (reduce) { draw(0); return; }
      setRunning(fade > 0.001 && visible && !document.hidden);
      if (fade <= 0.001) ctx.clearRect(0, 0, W, H);
    },
    center() { return { x: cx, y: cy }; },
  };
})();
