// The overview experience: Streamlit protocol, the viewing-port opening, the live atlas instrument,
// the atmosphere comparison, the gravity gap chapter and the page tiles.
(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (id) => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const send = (type, extra) => window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type }, extra), "*");
  const value = (v) => send("streamlit:setComponentValue", { value: Object.assign(v, { t: Date.now() }), dataType: "json" });
  const fmt = (v, d = 1) => Number(v).toFixed(d);
  const psi = (kpa) => kpa / 6.894757;
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const sm = (a, b, x) => { const k = Math.min(1, Math.max(0, (x - a) / (b - a))); return k * k * (3 - 2 * k); };
  const clamp01 = (v) => Math.min(1, Math.max(0, v));
  const dtxt = (r) => (r.D === null || r.D === undefined ? "D unknown" : `D ${r.lb ? "≥" : "="} ${fmt(r.D, 2)}`);
  const svgEl = (t, a, par) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); if (par) par.appendChild(e); return e; };
  let args = null, first = true, lastKey = "";

  // ---------------------------------------------------------------- frame: one viewport tall
  function viewportH() { try { return window.parent.innerHeight; } catch (e) { return 860; } }
  let lastH = 0;
  function setHeight() {
    const h = Math.max(520, viewportH());
    if (h === lastH) return;
    lastH = h;
    send("streamlit:setFrameHeight", { height: h });
  }
  try { window.parent.addEventListener("resize", setHeight); } catch (e) { /* cross-origin: keep first height */ }

  // ---------------------------------------------------------------- cinematic mode
  // Desktop with motion allowed: the stage pins and the camera moves through the port into the live
  // instrument. Phones and reduced motion: the instrument sits in normal flow after the opening.
  let cine = false;
  const P_END = 0.8;  // the camera move ends here; the rest of the pinned range holds on the instrument
  function decideCine() {
    const on = !reduce && window.innerWidth >= 900 && window.innerHeight >= 620;
    if (on === cine) return false;
    cine = on;
    document.body.classList.toggle("cine", on);
    document.documentElement.style.setProperty("--scroll", "150vh");
    const inst = $("atlas");
    inst.style.opacity = ""; inst.style.transform = ""; inst.classList.remove("live");
    return true;
  }
  const opening = $("hero");
  function atlasTop() {
    if (!cine) return $("atlas").getBoundingClientRect().top + window.scrollY - 8;
    return opening.offsetTop + (opening.offsetHeight - window.innerHeight) * P_END + 2;
  }
  function jump(id) {
    const behavior = reduce ? "auto" : "smooth";
    if (id === "atlas") window.scrollTo({ top: atlasTop(), behavior });
    else if (id === "hero") window.scrollTo({ top: 0, behavior });
    else $(id).scrollIntoView({ behavior });
  }

  // ---------------------------------------------------------------- navigation and actions
  document.addEventListener("click", (e) => {
    const j = e.target.closest("[data-jump]");
    if (j) { e.preventDefault(); jump(j.dataset.jump); if (j.dataset.jump === "atlas") focusAtlasSoon(); return; }
    const a = e.target.closest("[data-act]");
    if (a && a.dataset.act === "lunar") { runLunar(); return; }
    const n = e.target.closest("[data-nav]");
    if (n) { n.style.opacity = ".6"; value({ nav: n.dataset.nav }); }
  });
  function focusAtlasSoon() {
    // land keyboard focus on the instrument once the camera arrives, without scrolling again
    setTimeout(() => { const r = document.querySelector("#reticle"); if (r) r.focus({ preventScroll: true }); }, reduce ? 0 : 700);
  }
  function runLunar() {
    if (!args) return;
    const b = args.pair.b;
    pending();
    sent = { x: b.x, p: b.p, t: Date.now() };
    value({ preset: "lunar" });
    jump("atlas");
    focusAtlasSoon();
  }
  // keyboard users tabbing into the instrument before the camera has arrived are carried to it
  $("atlas").addEventListener("focusin", () => {
    if (cine && !$("atlas").classList.contains("live")) window.scrollTo({ top: atlasTop(), behavior: "auto" });
  });

  // ---------------------------------------------------------------- scroll
  const links = [...document.querySelectorAll(".links a")];
  let ticking = false;
  function onScroll() {
    ticking = false;
    scene();
    const y = window.scrollY, H = document.documentElement.scrollHeight - window.innerHeight;
    try { Voyage.scroll(y, 1 - 0.62 * sm(0, window.innerHeight * 0.7, y - atlasTop() - window.innerHeight * 0.35)); } catch (e) { /* decoration */ }
    $("progress").style.transform = `scaleX(${H > 0 ? y / H : 0})`;
    let cur = "hero";
    if (y >= atlasTop() - window.innerHeight * 0.3) cur = "atlas";
    for (const s of document.querySelectorAll("main > section.band")) if (s.getBoundingClientRect().top < window.innerHeight * 0.4) cur = s.id;
    links.forEach((a) => a.classList.toggle("on", a.dataset.jump === cur));
    const st = $("steps").getBoundingClientRect();
    const p = clamp01((window.innerHeight * 0.62 - st.top) / (st.height * 0.9));
    const vertical = matchMedia("(max-width: 760px)").matches;
    $("railfill").style.transform = vertical ? `scaleY(${p})` : `scaleX(${p})`;
    document.querySelectorAll(".step").forEach((el, i) => el.classList.toggle("lit", reduce || p >= i / 4 + 0.02));
  }
  window.addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });

  // ---------------------------------------------------------------- reveals
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      e.target.classList.add("in");
      if (e.target.classList.contains("platecard")) Plate.reveal();
      io.unobserve(e.target);
    }
  }, { threshold: 0.18, rootMargin: "0px 0px -6% 0px" });
  const watch = (el) => io.observe(el);

  // ---------------------------------------------------------------- 1 · the viewing port
  function buildMarks() {
    // engraved bezel: the port edge sits at r ≈ 94 in this viewBox (the svg is 128% of the port)
    const s = $("marks");
    s.innerHTML = "";
    svgEl("circle", { r: 94, fill: "none", stroke: "rgba(196,210,232,.35)", "stroke-width": .6 }, s);
    svgEl("circle", { r: 104, fill: "none", stroke: "rgba(196,210,232,.18)", "stroke-width": .5 }, s);
    for (let a = 0; a < 360; a += 5) {
      const big = a % 30 === 0, r0 = 96, r1 = big ? 102 : 99, t = (a - 90) * Math.PI / 180;
      svgEl("line", { x1: r0 * Math.cos(t), y1: r0 * Math.sin(t), x2: r1 * Math.cos(t), y2: r1 * Math.sin(t),
        stroke: big ? "rgba(242,244,248,.55)" : "rgba(196,210,232,.3)", "stroke-width": big ? .7 : .45 }, s);
      if (big) {
        const tx = svgEl("text", { x: 111 * Math.cos(t), y: 111 * Math.sin(t) + 1.8, "text-anchor": "middle" }, s);
        tx.textContent = String(a).padStart(3, "0");
      }
    }
    // reticle ticks inside the glass
    for (const [x1, y1, x2, y2] of [[0, -94, 0, -86], [0, 94, 0, 86], [-94, 0, -86, 0], [94, 0, 86, 0]])
      svgEl("line", { x1, y1, x2, y2, stroke: "rgba(242,244,248,.4)", "stroke-width": .6 }, s);
  }
  let curS = 1;
  function offsetIn(el, root) {
    let x = 0, y = 0;
    while (el && el !== root) { x += el.offsetLeft; y += el.offsetTop; el = el.offsetParent; }
    return { x, y };
  }
  function scene() {
    const port = $("port"), copy = $("herocopy");
    if (reduce) return;  // a static opening: no camera move
    if (!cine) {
      // phones: a simplified reveal, the port opens a little as the opening scrolls away
      const r = $("scene").getBoundingClientRect(), p = clamp01(-r.top / Math.max(1, r.height));
      port.style.transform = `scale(${(1 + 1.6 * sm(0, 0.8, p)).toFixed(3)})`;
      try { Flame.setScene(p * 0.7); } catch (e) { /* optional */ }
      return;
    }
    const r = opening.getBoundingClientRect();
    const total = Math.max(1, (r.height - window.innerHeight) * P_END);
    const p = clamp01(-r.top / total);
    try { Flame.setScene(p); } catch (e) { /* the illustration is optional */ }
    // approach, then open the port to the edges
    const vw = window.innerWidth, vh = window.innerHeight, size = port.offsetWidth || 1;
    const cover = Math.hypot(vw, vh) / size * 1.08;
    const k = sm(0.04, 0.62, p);
    port.style.transform = `scale(${Math.exp(Math.log(cover) * k).toFixed(4)})`;
    $("marks").style.opacity = (1 - sm(0.18, 0.42, p)).toFixed(3);
    port.style.setProperty("--warm", (1 - sm(0.08, 0.5, p)).toFixed(3));
    const co = 1 - sm(0.02, 0.2, p);
    copy.style.opacity = co.toFixed(3);
    copy.style.transform = `translateY(${(-36 * sm(0, 0.3, p)).toFixed(1)}px)`;
    copy.style.visibility = co < 0.02 ? "hidden" : "visible";
    const late = 1 - sm(0.06, 0.24, p);
    $("illus").style.opacity = late;
    document.querySelector(".scrollcue").style.opacity = (0.6 * late).toFixed(3);
    document.querySelector(".scrollcue").style.visibility = late < 0.02 ? "hidden" : "visible";
    const sk = document.querySelector(".skip");
    sk.style.opacity = (1 - sm(0.3, 0.5, p)).toFixed(3);
    // the live instrument resolves around the reticle, which stays put on screen while it scales
    const inst = $("atlas"), rl = Plate.retLocal(), wrap = $("platewrap");
    let ox = vw / 2, oy = vh / 2;
    if (rl) {
      const o = offsetIn(wrap, inst);
      ox = o.x + rl.x * (wrap.clientWidth / rl.W);
      oy = o.y + rl.y;
    }
    const ik = sm(0.5, 0.92, p);
    curS = 1.28 - 0.28 * ik;
    inst.style.transformOrigin = `${ox.toFixed(1)}px ${oy.toFixed(1)}px`;
    inst.style.transform = ik >= 1 ? "none" : `scale(${curS.toFixed(4)})`;
    inst.style.opacity = ik.toFixed(3);
    $("scene").style.setProperty("--night", (1 - ik).toFixed(3));  // light theme: the night field gives way to the lit instrument
    inst.classList.toggle("live", p > 0.9);
    if (p > 0.6) Plate.reveal();
    // the orange focal point: born at the flame, it becomes the reticle
    const c = Flame.center(), t = sm(0.22, 0.9, p);
    const fx = c.x + (ox - c.x) * t, fy = c.y + (oy - c.y) * t;
    const f = $("focal");
    f.style.opacity = (sm(0.05, 0.18, p) * (1 - sm(0.9, 0.99, p))).toFixed(3);
    f.style.transform = `translate(${fx.toFixed(1)}px, ${fy.toFixed(1)}px) scale(${(2.2 - 1.2 * t).toFixed(3)})`;
  }

  // hero gravity switch for the illustration
  const GRAV = [["Earth", 1, "1 g"], ["Mars", 0.38, "0.38 g"], ["Moon", 0.166, "0.166 g"], ["Orbit", 0, "0 g"]];
  const NOTES = {
    Earth: "<b>Earth, 1 g.</b> Buoyancy pulls the flame up into a tall, bright teardrop.",
    Mars: "<b>Mars, 0.38 g.</b> Weaker buoyancy: a shorter, wider flame. No PSI fire test exists here.",
    Moon: "<b>Moon, 0.166 g.</b> Barely any lift. No PSI fire test exists here either.",
    Orbit: "<b>Orbit, 0 g.</b> Nothing rises. Oxygen only arrives by slow diffusion, so the flame is a dim blue sphere.",
  };
  function placeThumb(box) {
    const b = box.querySelector('[aria-checked="true"]'), th = box.querySelector(".thumb");
    if (!b || !th) return;
    th.style.width = `${b.offsetWidth}px`;
    th.style.transform = `translateX(${b.offsetLeft}px)`;
  }
  // one radiogroup helper for the pill switches: click, arrow keys, a tracking thumb
  function pills(box, items, onPick) {
    box.innerHTML = `<span class="thumb" aria-hidden="true"></span>` + items.map((it) =>
      `<button type="button" role="radio" data-k="${esc(it.k)}" aria-checked="false" tabindex="-1">${it.html}</button>`).join("");
    const pick = (k, focus) => {
      box.querySelectorAll("button").forEach((b) => { const on = b.dataset.k === String(k); b.setAttribute("aria-checked", on); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
      placeThumb(box);
      onPick(k);
    };
    box.addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) pick(b.dataset.k); });
    box.addEventListener("keydown", (e) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
      const bs = [...box.querySelectorAll("button")], i = bs.findIndex((b) => b.getAttribute("aria-checked") === "true");
      const nx = bs[(i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : bs.length - 1)) % bs.length];
      pick(nx.dataset.k, true);
      e.preventDefault();
    });
    new ResizeObserver(() => placeThumb(box)).observe(box);
    if (document.fonts) document.fonts.ready.then(() => placeThumb(box));
    return pick;
  }
  function initHero() {
    const pick = pills($("gswitch"), GRAV.map(([n, , g]) => ({ k: n, html: `${n}<span class="gv"> ${g}</span>` })), (n) => {
      const i = GRAV.findIndex((g) => g[0] === n);
      Flame.setGravity(Math.sqrt(GRAV[i][1]));  // square root so the Moon and Mars differ visibly from orbit
      $("gnote").innerHTML = NOTES[n];
      $("illus").textContent = `Illustration of a flame at ${n === "Orbit" ? "orbital" : n === "Earth" ? "Earth" : n === "Moon" ? "lunar" : "Mars"} gravity, not a model of any test.`;
    });
    buildMarks();
    try { Flame.setInitialGravity(0); Flame.init($("flame")); } catch (e) { console.error(e); }  // a drawing failure must never hide the page
    pick("Orbit");
  }

  // ---------------------------------------------------------------- 2 · the instrument
  function renderReadout(r) {
    $("coords").innerHTML = `<span>${fmt(r.x * 100, 1)}%</span> O₂ · <span>${fmt(r.p, 1)}</span> kPa`;
    $("sub").textContent = `${fmt(psi(r.p), 2)} psia · oxygen partial pressure ${fmt(r.x * r.p, 1)} kPa`;
    $("xo").textContent = `${fmt(r.x * 100, 1)}%`;
    $("po").textContent = `${fmt(r.p, 1)} kPa`;
  }
  document.querySelector(".steppers").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-st]");
    if (!b) return;
    const k = +b.dataset.d * (e.shiftKey ? 10 : 1), q = Plate.ret;
    if (b.dataset.st === "x") Plate.nudge(q.x + 0.005 * k, q.p); else Plate.nudge(q.x, q.p + 1 * k);
    pending(false);
  });
  let pickGravity = null;
  function renderGravitySeg() {
    const box = $("gseg");
    if (!box.dataset.built) {
      box.dataset.built = "1";
      box.innerHTML = `<span class="thumb" aria-hidden="true"></span>` + args.gravity_options.map((g) =>
        `<button type="button" role="radio" aria-checked="false" data-gl="${esc(g)}">${esc(g)}</button>`).join("");
      new ResizeObserver(() => placeSegThumb()).observe(box);
    }
    box.querySelectorAll("button").forEach((b) => { const on = b.dataset.gl === args.scenario.gravity; b.setAttribute("aria-checked", on); b.tabIndex = on ? 0 : -1; });
    placeSegThumb();
  }
  function placeSegThumb() {
    const box = $("gseg"), b = box.querySelector('[aria-checked="true"]'), th = box.querySelector(".thumb");
    if (!b || !th) return;
    th.style.width = `${b.offsetWidth}px`; th.style.height = `${b.offsetHeight}px`;
    th.style.transform = `translate(${b.offsetLeft}px, ${b.offsetTop}px)`;
  }
  pickGravity = (b, focus) => {
    if (!b || b.getAttribute("aria-checked") === "true") return;
    $("gseg").querySelectorAll("button").forEach((x) => { x.setAttribute("aria-checked", x === b ? "true" : "false"); x.tabIndex = x === b ? 0 : -1; });
    if (focus) b.focus();
    placeSegThumb();
    pending();
    sent = { g: b.dataset.gl, t: Date.now() };
    // start the trip now; the rerun confirms it (Python sets the preset to Custom on a gravity pick)
    try { Voyage.set(args.gravity_backdrop[b.dataset.gl] || "none", framingFor(Plate.ret.x, Plate.ret.p)); } catch (e) { /* decoration */ }
    value({ gravity: b.dataset.gl });
  };
  // mirrors ember/ui/atlas.py framing_key for a Custom scenario: the NASA target it sits on, or "custom"
  function framingFor(x, p) {
    const t = (args.sky.targets || []).find((q) => Math.abs(q.x - x) < 0.0026 && Math.abs(q.p - p) < 0.6);
    return t ? t.name : "custom";
  }
  $("gseg").addEventListener("click", (e) => pickGravity(e.target.closest("button")));
  $("gseg").addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) return;
    const bs = [...$("gseg").querySelectorAll("button")], i = bs.findIndex((b) => b.getAttribute("aria-checked") === "true");
    pickGravity(bs[(i + (e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : bs.length - 1)) % bs.length], true);
    e.preventDefault();
  });
  function renderTargets() {
    const box = $("targets");
    const nice = (n) => n.replace("Exploration Atm 8.2/34", "Exploration Atmosphere").replace("ISS/Earth", "ISS / Earth air");
    box.innerHTML = `<button class="chip lunar" type="button" data-act="lunar" title="The guided demo's lunar habitat question">Lunar habitat</button>` +
      args.sky.targets.map((t, i) => `<button class="chip" type="button" data-i="${i}">${esc(nice(t.name))}</button>`).join("");
  }
  $("targets").addEventListener("click", (e) => {
    const b = e.target.closest(".chip[data-i]");
    if (!b) return;
    const t = args.sky.targets[+b.dataset.i];
    Plate.glideTo(t.x, t.p);
  });
  // While the engine recalculates, the previous results stay visible but dimmed, and the reticle wears a ring.
  let sent = null;
  function pending(busy = true) {
    $("ranklist").classList.add("pending");
    $("rankstate").textContent = busy ? "ranking…" : "release to rank";
    if (busy) Plate.setBusy(true);
  }
  // A rerun can answer an older request; ignore it until the answer for the latest one arrives.
  function stale(s) {
    if (!sent) return false;
    if (Date.now() - sent.t > 6000) { sent = null; return false; }
    const old = sent.g !== undefined ? s.gravity !== sent.g : Math.abs(s.x - sent.x) > 0.003 || Math.abs(s.p - sent.p) > 0.3;
    if (!old) sent = null;
    return old;
  }

  // Live ranking in the strip, with FLIP: cards that change place slide to their new slot.
  function renderRanks() {
    const ol = $("ranklist");
    const before = new Map([...ol.children].map((li) => { const b = li.getBoundingClientRect(); return [li.dataset.inv, [b.left, b.top]]; }));
    ol.classList.remove("pending");
    $("rankstate").textContent = "";
    ol.innerHTML = args.ranked.map((r) => `
      <li class="rk" data-inv="${esc(r.inv)}" data-id="${esc(r.id)}" tabindex="0" role="option" aria-selected="${r.inv === selected}" aria-label="Rank ${r.rank}, ${esc(r.inv)}, ${esc(dtxt(r).replace("≥", "at least"))}. Open its evidence.">
        <span class="n">${r.rank}</span>
        <span class="inv">${esc(r.inv)}</span>
        <span class="d">${dtxt(r)}</span>
        <span class="bar" title="Relevance R = ${fmt(r.R, 3)}"><i style="transform:scaleX(${before.size ? 0 : Math.max(0.02, r.R)})" data-r="${Math.max(0.02, r.R)}"></i></span>
      </li>`).join("");
    if (!reduce) {
      [...ol.children].forEach((li) => {
        const old = before.get(li.dataset.inv), b = li.getBoundingClientRect();
        if (old && (old[0] !== b.left || old[1] !== b.top)) li.animate([{ transform: `translate(${old[0] - b.left}px, ${old[1] - b.top}px)` }, { transform: "none" }], { duration: 520, easing: "cubic-bezier(0.23,1,0.32,1)" });
        else if (!old && before.size) li.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: 360, easing: "ease-out" });
      });
    }
    requestAnimationFrame(() => ol.querySelectorAll(".bar i").forEach((i) => { i.style.transform = `scaleX(${i.dataset.r})`; }));
    ol.querySelectorAll(".rk").forEach((li) => {
      li.addEventListener("mouseenter", () => Plate.setHover(li.dataset.inv));
      li.addEventListener("mouseleave", () => Plate.setHover(null));
      li.addEventListener("click", () => select(li.dataset.inv));
      li.addEventListener("keydown", (e) => {
        const nx = li.nextElementSibling, pv = li.previousElementSibling;
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(li.dataset.inv, true); }
        else if ((e.key === "ArrowRight" || e.key === "ArrowDown") && nx) { e.preventDefault(); nx.focus(); }
        else if ((e.key === "ArrowLeft" || e.key === "ArrowUp") && pv) { e.preventDefault(); pv.focus(); }
      });
    });
    if (!args.ranked.some((x) => x.inv === selected)) { selected = null; Plate.setPinned(null); }
    renderDetail(false);
    const r = args.ranked[0], best = $("best");
    if (!r) { best.textContent = "No evidence ranks for this scenario."; return; }
    let html = `Closest: <b>${esc(r.inv)}</b>. exp(D) = <b>${fmt(r.expD, 2)}×</b>: a response could differ by up to that factor from what this test saw`;
    html += r.lb ? ", or more, because some of its conditions are unknown." : ".";
    if (!r.pos && r.o2) html += " Its pressure was not reported, so it appears as a band at its oxygen level, not a point.";
    if (!r.pos && !r.o2) html += " It cannot be placed on this chart; its evidence opens below.";
    if (r.D > args.envelope) html += ` <span class="warn">This is beyond the tested envelope.</span>`;
    if (args.scenario.partial_g) html += ` <span class="warn">No PSI test exists at this gravity; EMBER brackets it from orbit and Earth tests.</span>`;
    best.innerHTML = html;
  }

  // ---------------------------------------------------------------- the evidence drawer
  let selected = null, opener = null;
  const DIM = { x_o2: "oxygen", p_kpa: "pressure", u_cms: "flow" };
  const FLAG = {
    GRAVITY_EXTRAPOLATION: "gravity differs from your scenario",
    INCOMPLETE_CONDITIONS: "some conditions not reported",
    NO_PARTIAL_G_DATA_IN_PSI: "no partial-gravity data in PSI",
  };
  function select(inv, fromKey) {
    selected = selected === inv ? null : inv;
    opener = selected ? $("ranklist").querySelector(`[data-inv="${CSS.escape(inv)}"]`) : opener;
    $("ranklist").querySelectorAll(".rk").forEach((li) => li.setAttribute("aria-selected", li.dataset.inv === selected ? "true" : "false"));
    Plate.setPinned(selected);
    renderDetail(true);
    if (selected && fromKey) { const x = $("detail").querySelector(".x"); if (x) x.focus({ preventScroll: true }); }
    // phones: the evidence opens inline under the chart, so bring it into view
    if (selected && matchMedia("(max-width: 760px)").matches) $("detail").scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }
  function closeDrawer() {
    if (!selected) return;
    const back = opener;
    select(selected);
    if (back && back.isConnected) back.focus({ preventScroll: true });
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && selected) closeDrawer(); });
  function renderDetail(enter) {
    const box = $("detail"), r = args.ranked.find((x) => x.inv === selected);
    if (!r || !r.detail) {
      if (box.hidden) return;
      if (enter && !reduce) {
        box.classList.remove("enter"); box.classList.add("leave");
        setTimeout(() => { if (!selected) { box.hidden = true; box.innerHTML = ""; box.classList.remove("leave"); } }, 220);
      } else { box.hidden = true; box.innerHTML = ""; }
      return;
    }
    const d = r.detail;
    const known = Object.entries(d.parts).filter(([, v]) => v !== null);
    const missing = Object.entries(d.parts).filter(([, v]) => v === null).map(([k]) => DIM[k] || k);
    const sum = known.reduce((a, [, v]) => a + v, 0) || 1;
    const bars = known.map(([k, v]) => `<i style="width:${(v / sum * 100).toFixed(1)}%" title="${DIM[k] || k}: ${fmt(v, 3)}"></i>`).join("");
    const parts = known.map(([k, v]) => `${DIM[k] || k} ${fmt(v, 2)}`).join(" + ");
    const gtxt = { microgravity: "orbit (microgravity), as tested", "1g": "Earth (1 g), as tested", simulated_partial: "simulated partial gravity, outside PSI" }[d.gravity] || d.gravity;
    const src = d.sources.slice(0, 3).map((x) => {
      const ref = x.doi ? `DOI ${esc(x.doi)}` : x.url ? "link" : "no DOI";
      const href = x.doi ? `https://doi.org/${encodeURI(x.doi)}` : x.url;
      return `<b>${esc(x.id)}</b> · ${esc(x.title)}${x.psi ? " · in PSI" : ""} · ${href ? `<a href="${esc(href)}" target="_blank" rel="noopener">${ref}</a>` : ref}`;
    }).join("<br>");
    const loc = (l) => `<span class="loc${l === "not reported" ? " none" : ""}">${esc(l)}</span>`;
    box.innerHTML = `
      <header><div><h4>${esc(r.inv)}</h4><p class="id">Rank ${r.rank} · best record ${esc(r.id)} · ${r.n} record${r.n === 1 ? "" : "s"} in this investigation · ${esc(d.fuel)}</p></div>
        <button type="button" class="x" aria-label="Close the evidence for ${esc(r.inv)}">×</button></header>
      <h5>Reported values</h5>
      <table><tbody>
        ${d.conds.map(([k, v, l]) => `<tr><td>${esc(k)}</td><td>${esc(v)}${v === "unknown" ? " (stays unknown)" : ""}${loc(l)}</td></tr>`).join("")}
        <tr><td>Gravity</td><td>${esc(gtxt)}<span class="loc none">A separate flag, never interpolated to your gravity.</span></td></tr>
        ${d.o2_context === "burner_oxidizer_flow" ? `<tr><td>Note</td><td>Oxygen is burner-side, not cabin air.</td></tr>` : ""}
      </tbody></table>
      <h5>Why it ranks here</h5>
      <p class="why">Transfer distance <b>${dtxt(r)}</b>${parts ? ` (${parts})` : ""}. exp(D) = ${fmt(r.expD, 2)}×: how far a response could differ from what this test saw. Not a probability of fire.${missing.length ? ` ${esc(missing.join(" and "))} not reported, so D is a lower bound.` : ""}</p>
      ${known.length ? `<div class="parts" aria-hidden="true">${bars}</div><div class="pkey">${esc(parts)}</div>` : ""}
      ${d.flags.length ? `<h5>Flags</h5><div class="flags">${d.flags.map((f) => `<span title="${esc(f)}">${esc(FLAG[f] || f.toLowerCase().replace(/_/g, " "))}</span>`).join("")}</div>` : ""}
      <h5>Provenance</h5>
      <p class="src">${src || "No source listed."}</p>`;
    box.querySelector(".x").addEventListener("click", closeDrawer);
    box.hidden = false;
    box.classList.remove("leave");
    if (enter && !reduce) { box.classList.remove("enter"); void box.offsetWidth; box.classList.add("enter"); }
  }

  function renderLegend() {
    const T = args.theme;
    const items = [
      [`<circle cx="13" cy="0" r="2.2" fill="${T.ink}"/><circle cx="22" cy="0" r="4.6" fill="${T.ink}"/>`, "Tests. Bigger star, more tests."],
      [`<ellipse cx="17" cy="0" rx="11" ry="5" fill="none" stroke="${T.ink2}" stroke-dasharray="2 2"/>`, "A range reported as one record."],
      [`<line x1="4" y1="3" x2="13" y2="-3" stroke="${T.ink2}" stroke-width=".8"/><line x1="13" y1="-3" x2="24" y2="1" stroke="${T.ink2}" stroke-width=".8"/>`, "One investigation, joined up."],
      [`<circle cx="17" cy="0" r="5" fill="none" stroke="${T.gold}"/><path d="M17 -8V8M9 0H25" stroke="${T.gold}" stroke-width=".8"/>`, "NASA target atmosphere."],
      [`<circle cx="17" cy="0" r="5" fill="none" stroke="${T.accent}" stroke-width="1.5"/>`, "Your scenario."],
    ];
    $("legend").innerHTML = items.map(([g, t]) => `<li><svg width="26" height="14" viewBox="0 -7 26 14" aria-hidden="true">${g}</svg><span>${t}</span></li>`).join("");
  }
  // fit the chart to the window in cinematic mode, so the whole instrument is on one screen
  function fitPlate() {
    if (!cine) { Plate.setMaxHeight(Math.round(Math.min(720, Math.max(440, viewportH() * 0.7)))); return false; }
    const inst = $("atlas"), svgH = +$("plate").getAttribute("height") || 0;
    const chrome = inst.scrollHeight - svgH;
    const want = Math.round(Math.max(300, window.innerHeight - chrome - 4));
    if (Math.abs(want - (fitPlate.last || 0)) < 6) return false;
    fitPlate.last = want;
    Plate.setMaxHeight(want);
    return true;
  }

  // ---------------------------------------------------------------- investigations index
  let pinned = null;
  function renderIndex() {
    const T = args.theme, sky = args.sky, box = $("index");
    box.innerHTML = "";
    $("invh").textContent = `Every investigation, one sky: ${sky.index.length} of them.`;
    const rel = (v) => (v - sky.x_range[0]) / (sky.x_range[1] - sky.x_range[0]) * 100;
    for (const row of sky.index) {
      const b = document.createElement("button");
      b.className = "cell"; b.type = "button";
      b.setAttribute("aria-pressed", pinned === row.inv ? "true" : "false");
      b.setAttribute("aria-label", `${row.inv}: ${row.total} records, ${row.charted} charted, ${row.o2_only} oxygen only, ${row.uncharted} uncharted. Highlight on the atlas.`);
      const segs = row.o2.map(([a, z]) => rel(z) - rel(a) < 0.6
        ? `<line x1="${rel(a)}%" x2="${rel(a)}%" y1="2" y2="10" stroke="${T.ink}" stroke-width="1"/>`
        : `<line x1="${rel(a)}%" x2="${rel(z)}%" y1="6" y2="6" stroke="${T.ink}" stroke-width="3" opacity=".75"/>`).join("");
      const sxp = rel(args.scenario.x).toFixed(2);
      b.innerHTML = `<span class="name">${esc(row.inv)}</span><span class="n">${row.total} records · ${row.charted} charted</span>` +
        `<svg aria-hidden="true"><line x1="0" x2="100%" y1="6" y2="6" stroke="${T.line}"/>${segs}<line x1="${sxp}%" x2="${sxp}%" y1="0" y2="12" stroke="${T.accent}" stroke-width="1.5"/></svg>`;
      b.addEventListener("mouseenter", () => Plate.setHover(row.inv));
      b.addEventListener("mouseleave", () => Plate.setHover(null));
      b.addEventListener("click", () => {
        pinned = pinned === row.inv ? null : row.inv;
        box.querySelectorAll(".cell").forEach((c) => c.setAttribute("aria-pressed", "false"));
        b.setAttribute("aria-pressed", pinned ? "true" : "false");
        Plate.setPinned(pinned);
        jump("atlas");
      });
      box.appendChild(b);
    }
  }

  // ---------------------------------------------------------------- 3 · atmosphere comparison
  // Only the two endpoints are real engine results. Positions in between are an animation of the
  // marker; nothing is ranked or reported there.
  let atm = null, atmT = 0;
  function buildAtmos() {
    const pr = args.pair, A = pr.a, B = pr.b, T = args.theme;
    const ppA = A.x * A.p, ppB = B.x * B.p;
    $("endA").innerHTML = `<b>${esc(A.name)}</b><span>${fmt(A.x * 100, 0)}% O₂ · ${fmt(A.p, 1)} kPa</span>`;
    $("endB").innerHTML = `<b>${esc(B.name)}</b><span>${fmt(B.x * 100, 0)}% O₂ · ${fmt(B.p, 1)} kPa</span>`;
    $("gfixed").innerHTML = `<span class="pin">Gravity fixed: ${esc(pr.g_label)}</span>Both ends are ranked at this gravity for ${esc(pr.phenomenon.toLowerCase())}, ${esc(pr.fuel)}. Here “Earth-normal air” is an atmosphere setting only; the gravity stays lunar.`;
    // the figure: oxygen share against total pressure, log scale
    const s = $("atmsvg");
    s.innerHTML = "";
    const L = 58, R = 500, Tp = 22, Bt = 322;
    const x0 = 0.15, x1 = 0.45, p0 = 40, p1 = 125;
    const sx = (x) => L + (x - x0) / (x1 - x0) * (R - L);
    const sy = (p) => Bt - Math.log(p / p0) / Math.log(p1 / p0) * (Bt - Tp);
    for (const x of [0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45]) {
      svgEl("line", { x1: sx(x), x2: sx(x), y1: Tp, y2: Bt, stroke: T.line, "stroke-width": .6 }, s);
      svgEl("text", { x: sx(x), y: Bt + 20, "text-anchor": "middle", class: "tick" }, s).textContent = `${Math.round(x * 100)}%`;
    }
    for (const p of [40, 50, 60, 70, 80, 100, 120]) {
      svgEl("line", { x1: L, x2: R, y1: sy(p), y2: sy(p), stroke: T.line, "stroke-width": .6 }, s);
      svgEl("text", { x: L - 10, y: sy(p) + 4, "text-anchor": "end", class: "tick" }, s).textContent = p;
    }
    svgEl("text", { x: (L + R) / 2, y: Bt + 46, "text-anchor": "middle", class: "axis-title" }, s).textContent = "Oxygen in the atmosphere";
    svgEl("text", { x: 14, y: (Tp + Bt) / 2, "text-anchor": "middle", class: "axis-title", transform: `rotate(-90 14 ${(Tp + Bt) / 2})` }, s).textContent = "Total pressure, kPa (log)";
    // oxygen partial pressure through each endpoint, computed from the actual values
    const iso = (pp, lab, lx, dy) => {
      let d = "";
      for (let i = 0; i <= 60; i++) { const x = x0 + i * (x1 - x0) / 60, p = pp / x; if (p >= p0 && p <= p1) d += (d ? "L" : "M") + sx(x).toFixed(1) + " " + sy(p).toFixed(1); }
      svgEl("path", { d, fill: "none", stroke: T.muted, "stroke-width": 1, "stroke-dasharray": "2 5" }, s);
      const t = svgEl("text", { x: sx(lx), y: sy(pp / lx) + dy, "text-anchor": "start", class: "iso-label halo" }, s);
      t.textContent = lab;
    };
    // the higher-ppO₂ curve is labelled above its line, the lower one below
    iso(Math.max(ppA, ppB), `ppO₂ ${fmt(Math.max(ppA, ppB), 1)} kPa`, 0.385, -8);
    iso(Math.min(ppA, ppB), `ppO₂ ${fmt(Math.min(ppA, ppB), 1)} kPa`, 0.385, 16);
    const ax = sx(A.x), ay = sy(A.p), bx = sx(B.x), by = sy(B.p);
    svgEl("path", { d: `M${ax} ${ay}L${bx} ${by}`, stroke: T.ink2, "stroke-width": 1, "stroke-dasharray": "1 4", fill: "none" }, s);
    svgEl("circle", { cx: ax, cy: ay, r: 6, fill: T.ink }, s);
    svgEl("text", { x: ax + 12, y: ay - 10, class: "target-label", fill: T.ink, style: `fill:${T.ink}` }, s).textContent = A.name;
    svgEl("circle", { cx: bx, cy: by, r: 6, fill: "none", stroke: T.ink, "stroke-width": 1.4 }, s);
    svgEl("text", { x: bx + 12, y: by + 22, class: "target-label", style: `fill:${T.ink}` }, s).textContent = B.name;
    const m = svgEl("g", { id: "atmmark" }, s);
    svgEl("circle", { r: 13, fill: "none", stroke: T.accent, "stroke-width": 1.6 }, m);
    svgEl("circle", { r: 3, fill: T.accent }, m);
    atm = { ax, ay, bx, by, A, B, ppA, ppB };
    buildSlope();
    setAtm(0, true);
  }
  function buildSlope() {
    const pr = args.pair, T = args.theme, s = $("slope");
    const A = pr.a.ranked, B = pr.b.ranked;
    const invs = [...new Set([...A.map((r) => r.inv), ...B.map((r) => r.inv)])];
    const rowH = 34, top = 40, W = 660, n = Math.max(A.length, B.length);
    const H = top + n * rowH + 10;
    const cl = 260, cr = 400;
    s.setAttribute("viewBox", `0 0 ${W} ${H}`);
    s.innerHTML = "";
    svgEl("text", { x: cl, y: 18, "text-anchor": "end", class: "axis-title", id: "slA" }, s).textContent = pr.a.name;
    svgEl("text", { x: cr, y: 18, "text-anchor": "start", class: "axis-title", id: "slB" }, s).textContent = pr.b.name;
    const y = (rank) => top + (rank - 1) * rowH + 10;
    const lines = svgEl("g", { id: "sllines" }, s);
    const colA = svgEl("g", { id: "slcolA" }, s), colB = svgEl("g", { id: "slcolB" }, s);
    const onlyA = [], onlyB = [];
    for (const inv of invs) {
      const a = A.find((r) => r.inv === inv), b = B.find((r) => r.inv === inv);
      if (a && b) {
        const lead = b.rank === 1;
        const ln = svgEl("path", { d: `M${cl + 10} ${y(a.rank)}L${cr - 10} ${y(b.rank)}`, stroke: lead ? T.accent : T.ink2, "stroke-width": lead ? 2 : 1.1, fill: "none", opacity: lead ? 1 : .6, class: "sl" }, lines);
        const tt = svgEl("title", {}, ln); tt.textContent = `${inv}: rank ${a.rank} → ${b.rank}`;
      }
      if (a) {
        const g = svgEl("g", { class: "slope-row" }, colA);
        svgEl("text", { x: cl - 2, y: y(a.rank) + 5, "text-anchor": "end", class: "lab", fill: T.ink }, g).textContent = `${inv}${b ? "" : " (only here)"}`;
        svgEl("text", { x: cl - 2, y: y(a.rank) + 19, "text-anchor": "end", class: "tick" }, g).textContent = dtxt(a);
        svgEl("text", { x: 14, y: y(a.rank) + 7, class: "rn", fill: T.muted }, g).textContent = a.rank;
        svgEl("circle", { cx: cl + 10, cy: y(a.rank), r: 3.2, fill: T.ink }, g);
        if (!b) onlyA.push(inv);
      }
      if (b) {
        const g = svgEl("g", { class: "slope-row" }, colB);
        svgEl("circle", { cx: cr - 10, cy: y(b.rank), r: 3.2, fill: b.rank === 1 ? T.accent : T.ink }, g);
        svgEl("text", { x: cr + 2, y: y(b.rank) + 5, class: "lab", fill: b.rank === 1 ? T.accent : T.ink }, g).textContent = `${inv}${a ? "" : " (only here)"}`;
        svgEl("text", { x: cr + 2, y: y(b.rank) + 19, class: "tick" }, g).textContent = dtxt(b);
        svgEl("text", { x: W - 14, y: y(b.rank) + 7, "text-anchor": "end", class: "rn", fill: T.muted }, g).textContent = b.rank;
        if (!a) onlyB.push(inv);
      }
    }
    lines.querySelectorAll(".sl").forEach((p) => { const len = p.getTotalLength(); p.style.strokeDasharray = len; p.dataset.len = len; });
    const moved = invs.filter((i) => { const a = A.find((r) => r.inv === i), b = B.find((r) => r.inv === i); return a && b && a.rank !== b.rank; }).length;
    let cap = `Top ${n} for each atmosphere, matched by investigation. ${moved} of them change rank. “≥” marks a lower bound: some of that test's conditions were never reported.`;
    if (onlyA.length) cap += ` Only in the ${pr.a.name} ranking: ${onlyA.join(", ")}.`;
    if (onlyB.length) cap += ` Only in the ${pr.b.name} ranking: ${onlyB.join(", ")}.`;
    $("slopecap").textContent = cap;
  }
  function setAtm(t, initial) {
    if (!atm) return;
    atmT = t;
    const e = t;  // linear along the drawn path; the marker is an animation only
    const x = atm.ax + (atm.bx - atm.ax) * e, y = atm.ay + (atm.by - atm.ay) * e;
    $("atmmark").setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
    $("slope").querySelectorAll(".sl").forEach((p) => { p.style.strokeDashoffset = (+p.dataset.len * (1 - t)).toFixed(1); });
    $("slcolA").style.opacity = (1 - 0.55 * t).toFixed(3);
    $("slcolB").style.opacity = (0.35 + 0.65 * t).toFixed(3);
    $("endA").setAttribute("aria-pressed", t === 0);
    $("endB").setAttribute("aria-pressed", t === 1);
    const rd = $("atmread"), A = atm.A, B = atm.B;
    const line = (S, pp) => `<b>${esc(S.name)}</b>: ${fmt(S.x * 100, 1)}% O₂ at ${fmt(S.p, 1)} kPa (${fmt(psi(S.p), 1)} psia). Oxygen partial pressure ${fmt(pp, 1)} kPa. Closest test: <b>${esc(S.ranked[0].inv)}</b>, ${dtxt(S.ranked[0])}.`;
    const diff = `The habitat atmosphere has a higher oxygen share but ${atm.ppB < atm.ppA ? "a slightly lower" : "a higher"} oxygen partial pressure: ${fmt(atm.ppB, 1)} kPa against ${fmt(atm.ppA, 1)} kPa.`;
    if (t === 0) rd.innerHTML = `${line(A, atm.ppA)} ${diff}`;
    else if (t === 1) rd.innerHTML = `${line(B, atm.ppB)} ${diff}`;
    else rd.innerHTML = `<span class="anim">Between the endpoints: animation only. EMBER ranks just the two real atmospheres, so no values are shown here.</span>`;
    if (!initial) $("scrub").value = Math.round(t * 1000);
  }
  let atmAnim = 0;
  function glideAtm(to) {
    cancelAnimationFrame(atmAnim);
    if (reduce) { setAtm(to); return; }
    const from = atmT, t0 = performance.now(), dur = 900;
    const tick = (now) => {
      const k = Math.min(1, (now - t0) / dur), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
      setAtm(k >= 1 ? to : from + (to - from) * e);
      if (k < 1) atmAnim = requestAnimationFrame(tick);
    };
    atmAnim = requestAnimationFrame(tick);
  }
  $("scrub").addEventListener("input", (e) => { cancelAnimationFrame(atmAnim); const v = +e.target.value / 1000; setAtm(v <= 0.001 ? 0 : v >= 0.999 ? 1 : v, true); });
  // release between the ends settles on the nearer real endpoint
  $("scrub").addEventListener("change", (e) => { const v = +e.target.value / 1000; if (v > 0 && v < 1) glideAtm(v < 0.5 ? 0 : 1); });
  $("endA").addEventListener("click", () => glideAtm(0));
  $("endB").addEventListener("click", () => glideAtm(1));

  // ---------------------------------------------------------------- 4 · missing evidence
  const GIDX = { 0: 0, 0.166: 1, 0.38: 2, 1: 3 };
  let gapSel = 0;
  function buildGap() {
    const gp = args.gaps, T = args.theme, sky = args.sky;
    pills($("gpick"), gp.regimes.map((r) => ({ k: r.g, html: esc(r.label) })), (k) => { gapSel = +k; renderGap(); });
    const s = $("gapsvg");
    const W = 600, H = 380, L = 50, R = W - 16, Tp = 14, Bt = H - 40;
    s.setAttribute("viewBox", `0 0 ${W} ${H}`);
    s.innerHTML = "";
    const [x0, x1] = sky.x_range, p0 = sky.p_range[0], p1 = sky.p_range[1] * 1.14;
    const sx = (x) => L + (x - x0) / (x1 - x0) * (R - L);
    const sy = (p) => Bt - Math.log(p / p0) / Math.log(p1 / p0) * (Bt - Tp);
    const defs = svgEl("defs", {}, s);
    const pat = svgEl("pattern", { id: "hatch", width: 8, height: 8, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    svgEl("line", { x1: 0, y1: 0, x2: 0, y2: 8, stroke: T.line, "stroke-width": 2 }, pat);
    for (let x = Math.ceil(x0 * 20) / 20; x <= x1 + 1e-9; x += 0.05) {
      svgEl("line", { x1: sx(x), x2: sx(x), y1: Tp, y2: Bt, stroke: T.line, "stroke-width": .5 }, s);
      if (Math.round(x * 100) % 10 === 0) svgEl("text", { x: sx(x), y: Bt + 18, "text-anchor": "middle", class: "tick" }, s).textContent = `${Math.round(x * 100)}%`;
    }
    for (const p of [10, 20, 50, 100, 200].filter((q) => q >= p0 && q <= p1)) {
      svgEl("line", { x1: L, x2: R, y1: sy(p), y2: sy(p), stroke: T.line, "stroke-width": .5 }, s);
      svgEl("text", { x: L - 8, y: sy(p) + 4, "text-anchor": "end", class: "tick" }, s).textContent = p;
    }
    svgEl("rect", { x: L, y: Tp, width: R - L, height: Bt - Tp, fill: "none", stroke: T.ink2, opacity: .5 }, s);
    svgEl("text", { x: (L + R) / 2, y: Bt + 34, "text-anchor": "middle", class: "axis-title" }, s).textContent = "Oxygen in the atmosphere, %  ·  total pressure, kPa (log)";
    const stars = svgEl("g", {}, s);
    for (const st of gp.stars.filter((q) => q.p <= p1)) {
      svgEl("circle", { class: "gs off", "data-g": st.g, cx: sx(st.x), cy: sy(st.p), r: Math.min(6.5, 1.6 + 1.2 * Math.log2(st.n + 0.5)), fill: T.ink }, stars);
    }
    const dark = svgEl("g", { id: "gapdark", class: "dark", opacity: 0 }, s);
    svgEl("rect", { x: L, y: Tp, width: R - L, height: Bt - Tp, fill: "url(#hatch)", opacity: .7 }, dark);
    // the message sits low on the plate, below the NASA targets, so their labels stay readable
    const my = Math.min(Bt - 40, sy(32));
    svgEl("text", { x: (L + R) / 2, y: my, "text-anchor": "middle", class: "const-label", id: "gapdarkt" }, dark).textContent = "No PSI fire test in this regime";
    svgEl("text", { x: (L + R) / 2, y: my + 20, "text-anchor": "middle", class: "iso-label halo" }, dark).textContent = "The gap stays visible. Nothing is interpolated from orbit or Earth.";
    const tg = svgEl("g", {}, s);
    for (const t of sky.targets) {
      const cx = sx(t.x), cy = sy(t.p);
      const g = svgEl("g", { class: "gt", "data-t": t.name }, tg);
      svgEl("circle", { cx, cy, r: 7, fill: "none", stroke: T.gold, "stroke-width": 1.2 }, g);
      svgEl("path", { d: `M${cx} ${cy - 12}V${cy + 12}M${cx - 12} ${cy}H${cx + 12}`, stroke: T.gold, "stroke-width": .8 }, g);
      svgEl("text", { x: cx + 12, y: cy - 10, class: "target-label gtl" }, g);
    }
    const sc = args.scenario;
    const ys = svgEl("g", {}, s);
    svgEl("circle", { cx: sx(sc.x), cy: sy(Math.min(p1, sc.p)), r: 9, fill: "none", stroke: T.accent, "stroke-width": 1.6 }, ys);
    s._scales = { sx, sy };
    renderUncharted();
    const start = gp.regimes.find((r) => r.g === 0) ? 0 : gp.regimes[0].g;
    $("gpick").querySelector(`[data-k="${start}"]`).click();
  }
  function renderGap() {
    const gp = args.gaps, sky = args.sky, s = $("gapsvg");
    const reg = gp.regimes.find((r) => r.g === gapSel);
    if (!reg || !s._scales) return;
    s.querySelectorAll(".gs").forEach((c) => c.classList.toggle("off", +c.dataset.g !== gapSel));
    const lit = gp.stars.filter((q) => q.g === gapSel);
    const tested = lit.length > 0;
    s.querySelector("#gapdark").setAttribute("opacity", tested ? 0 : 1);
    const nice = (n) => n.replace("Exploration Atm 8.2/34", "Exploration Atmosphere").replace("ISS/Earth", "ISS / Earth air");
    s.querySelectorAll(".gt").forEach((g) => {
      const row = reg.rows.find((r) => r.target === g.dataset.t);
      g.querySelector(".gtl").textContent = row ? `${nice(row.target)} · C ${fmt(row.C, 2)}` : nice(g.dataset.t);
    });
    // the finding: real GapScope rows for this regime
    const gi = GIDX[gapSel], gc = sky.gravity[gi] || { n: 0, note: "" };
    const pool = reg.rows[0] ? reg.rows[0].n_pool : 0, partial = reg.rows[0] ? reg.rows[0].n_partial : 0;
    const untested = !reg.bracket || (reg.rows[0] && reg.rows[0].flags.includes("NO_PARTIAL_G_DATA_IN_PSI"));
    let kind;
    if (untested) kind = `<p><b>Untested regime.</b> PSI holds no fire test at this gravity, so every target has zero coverage. ${esc(gc.note)}</p>`;
    else if (pool === 0) kind = `<p><b>Missing conditions, not a missing regime.</b> ${gc.n} records were run at this gravity, but none match ${esc(gp.phenomenon.toLowerCase())} on ${esc(gp.fuel)}${partial ? `; ${partial} more lack a condition the match needs` : ""}.</p>`;
    else kind = `<p><b>${pool}</b> record${pool === 1 ? "" : "s"} match ${esc(gp.phenomenon.toLowerCase())} on ${esc(gp.fuel)} here${partial ? `, and ${partial} more lack a condition the match needs` : ""}. Coverage C runs from 0 (no nearby evidence) to 1; it is not a safety rating.</p>`;
    const zero = reg.rows.filter((r) => r.C === 0);
    const sc = args.scenario;
    const near = zero.slice().sort((a, b) => Math.hypot(a.x_o2 - sc.x, Math.log(a.p_kpa / sc.p)) - Math.hypot(b.x_o2 - sc.x, Math.log(b.p_kpa / sc.p)))[0];
    const next = near
      ? `<p class="next"><b>Next experiment:</b> ${esc(gp.phenomenon.toLowerCase())} on ${esc(gp.fuel)} at ${esc(nice(near.target))} (${fmt(near.x_o2 * 100, 1)}% O₂, ${fmt(near.p_kpa, 1)} kPa), ${esc(reg.label)}.</p>`
      : `<p>Every NASA target has some coverage in this regime. Lower C means thinner evidence.</p>`;
    $("finding").innerHTML = `<div class="chg">
      <h3>${esc(reg.label)}</h3>
      <div class="big${gc.n === 0 ? " zero" : ""}">${gc.n}</div>
      <p>records in the registry at this gravity, across all phenomena.</p>
      ${kind}
      <table><thead><tr><th>Target</th><th>C</th><th>Nearest record</th></tr></thead><tbody>
        ${reg.rows.map((r) => `<tr><td>${esc(nice(r.target))}</td><td>${fmt(r.C, 2)}</td><td>${r.nearest ? esc(r.nearest) : "none"}</td></tr>`).join("")}
      </tbody></table>
      ${next}</div>`;
  }
  function renderUncharted() {
    const c = args.sky.counts;
    $("unchN").textContent = c.uncharted.toLocaleString();
    const cols = ["#a8b4c7", "#7f8ba0", "#56627a"];
    $("stack").innerHTML = c.reasons.map(([r, n]) => `<div style="flex:${n}" title="${n} ${esc(r)}">${n}</div>`).join("");
    const old = document.querySelector(".stacklegend"); if (old) old.remove();
    $("stack").insertAdjacentHTML("afterend", `<div class="stacklegend">${c.reasons.map(([r, n], i) => `<span style="--c:${cols[i % 3]}">${n} ${esc(r)}</span>`).join("")}</div>`);
    new IntersectionObserver(([e], o) => { if (e.isIntersecting) { $("stack").classList.add("in"); o.disconnect(); } }, { threshold: 0.4 }).observe($("stack"));
  }

  // ---------------------------------------------------------------- explore tiles
  function renderTiles() {
    const arrow = `<svg viewBox="0 0 12 12"><path d="M2 6h8M6.5 2.5 10 6l-3.5 3.5"/></svg>`;
    $("tiles").innerHTML = args.pages.map((p, i) => `
      <button class="tile reveal" type="button" data-nav="${p.key}" style="--d:${(i % 4) * 70}ms">
        <span class="t">${esc(p.title)}</span><span class="q">${esc(p.question)}</span><span class="x">${esc(p.text)}</span>
        <span class="go" aria-hidden="true">${arrow}</span>
      </button>`).join("");
    $("tiles").querySelectorAll(".tile").forEach((t) => {
      watch(t);
      t.addEventListener("pointermove", (e) => {
        const b = t.getBoundingClientRect();
        t.style.setProperty("--mx", `${e.clientX - b.left}px`);
        t.style.setProperty("--my", `${e.clientY - b.top}px`);
      });
    });
  }

  // ---------------------------------------------------------------- Streamlit protocol
  function applyTheme(T) {
    const r = document.documentElement.style;
    const map = { ink: T.ink, ink2: T.ink2, muted: T.muted, line: T.line, plate: T.plate, accent: T.accent, gold: T.gold, "accent-ink": T.accent_ink,
      deep: T.canvas, surface: T.surface, "surface-2": T.surface2, glass: T.glass, "glass-solid": T.glass_solid, "glass-edge": T.glass_edge, hair: T.hair };
    for (const [k, v] of Object.entries(map)) if (v) r.setProperty(`--${k}`, v);
    document.documentElement.dataset.theme = T.base === "light" ? "light" : "dark";
  }

  document.querySelectorAll(".reveal").forEach(watch);
  try { Voyage.init($("voyage")); } catch (e) { console.error(e); }
  decideCine();

  Plate.init({
    onMove: (r) => { renderReadout(r); },
    onCommit: (pos) => { pending(); sent = { x: pos.x, p: pos.p, t: Date.now() }; value({ x_o2: pos.x, p_kpa: pos.p }); },
  });

  window.addEventListener("message", (ev) => {
    const d = ev.data;
    if (!d || d.type !== "streamlit:render") return;
    args = d.args;
    applyTheme(args.theme);
    const s = args.scenario;
    if (!first && stale(s)) return;  // keep the newer reticle and the pending state
    Plate.setBusy(false);
    try { Voyage.set(s.backdrop, s.framing, { instant: first }); } catch (e) { console.error(e); }  // decoration must never block the page
    const key = `${s.x}|${s.p}|${s.gravity}|${args.ranked.map((r) => r.id).join(",")}`;
    const changed = key !== lastKey;
    lastKey = key;
    if (first) {
      initHero(); renderLegend(); renderTargets(); renderTiles();
      if (!cine) watch($("platecard"));
    }
    fitPlate();
    renderGravitySeg();
    renderIndex();
    Plate.update(args, changed && !first);
    renderReadout(Plate.ret);
    if (changed || first) renderRanks();
    if (fitPlate()) Plate.update(args, false);
    if (first) { buildAtmos(); buildGap(); }
    setHeight();
    onScroll();
    first = false;
  });

  let rt = 0, lastW = 0, lastVH = 0;
  new ResizeObserver(() => {
    const w = document.body.clientWidth, vh = window.innerHeight;
    if (w === lastW && vh === lastVH) return;
    lastW = w; lastVH = vh;
    clearTimeout(rt);
    rt = setTimeout(() => {
      const switched = decideCine();
      if (!args) return;
      if (switched && !cine) watch($("platecard"));
      fitPlate.last = 0;
      fitPlate();
      Plate.update(args, false);
      if (fitPlate()) Plate.update(args, false);
      placeSegThumb();
      onScroll();
    }, 90);
  }).observe(document.body);
  send("streamlit:componentReady", { apiVersion: 1 });
})();
