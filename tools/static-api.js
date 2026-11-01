/* واجهة API وهمية تعمل داخل المتصفح فوق لقطة JSON ثابتة (لنسخة GitHub Pages) */
(function () {
  window.__STATIC = true;
  const realFetch = window.fetch.bind(window);
  const cache = {};
  const load = n => cache[n] || (cache[n] = realFetch("data/" + n + "?t=" + Math.floor(Date.now() / 120000)).then(r => r.json()));
  const norm = s => (s || "").toLowerCase().replace(/[ً-ْـ]/g, "").replace(/[إأآ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه");
  const hay = s => norm([s.title, s.title_orig, s.summary, s.source_ar, s.source].join(" ") + " " + (s.items || []).map(i => i.title).join(" "));
  function parseQ(q) {
    q = norm(q); const neg = [], pos = [];
    q = q.replace(/[«"]([^»"]+)[»"]/g, (m, p) => { pos.push([[p.trim()]]); return " "; });
    const groups = []; let cur = [];
    q.split(/\s+/).filter(Boolean).forEach(w => {
      if (/^(or|او)$/.test(w)) { groups.push(cur); cur = []; return; }
      if (/^(and)$/.test(w)) return;
      if (/^-/.test(w) && w.length > 1) { neg.push(w.slice(1)); return; }
      cur.push(w);
    });
    groups.push(cur);
    return { pos, groups: groups.filter(g => g.length), neg };
  }
  function match(h, pq) {
    for (const p of pq.pos) if (!h.includes(p[0][0])) return false;
    for (const n of pq.neg) if (h.includes(n)) return false;
    if (!pq.groups.length) return true;
    return pq.groups.some(g => g.every(w => h.includes(w)));
  }
  async function stories(q) {
    const d = await load("stories.json"), now = Math.floor(Date.now() / 1000);
    const minRel = 0, lang = q.get("lang") ? q.get("lang").split(",") : null, cat = q.get("cat") ? q.get("cat").split(",") : null;
    const hours = parseFloat(q.get("hours") || 0), minU = parseInt(q.get("min_urgency") || 0), auth = q.get("auth") === "1";
    const known = q.get("known") === "1", qq = (q.get("q") || "").trim(), pq = qq ? parseQ(qq) : null;
    let list = d.stories.filter(s => {
      if (hours > 0 && s.last_pub < now - hours * 3600) return false;
      if (lang && !(s.langs || []).some(l => lang.includes(l)) && !lang.includes(s.lang)) return false;
      if (cat && !cat.includes(s.category)) return false;
      if (minU && s.urgency < minU) return false;
      if (auth && !s.auth) return false;
      if (known && !s.last_known) return false;
      if (pq && !match(s._h || (s._h = hay(s)), pq)) return false;
      return true;
    });
    const sort = q.get("sort") || "latest";
    if (sort === "top") list.sort((a, b) => b.score - a.score);
    else if (sort === "urgent") list.sort((a, b) => b.urgency - a.urgency || b.last_pub - a.last_pub);
    else list.sort((a, b) => b.last_pub - a.last_pub);
    const lim = Math.min(parseInt(q.get("limit") || 40), 200), off = parseInt(q.get("offset") || 0);
    return { total: list.length, stories: list.slice(off, off + lim) };
  }
  async function route(path, q) {
    switch (path) {
      case "/api/stories": return stories(q);
      case "/api/stats": return load("stats.json");
      case "/api/meta": return load("meta.json");
      case "/api/health": return load("health.json");
      case "/api/feeds": return load("feeds.json");
      case "/api/status": { const m = await load("meta.json"); return { running: false, last_end: m.generated, now: Math.floor(Date.now() / 1000), cycle_minutes: 20, translation: { pending: 0 } }; }
      case "/api/discovery": { const f = await load("feeds.json"); const a = (f.mine || []).filter(x => x.auto); return { stats: { last_run: null, next_run: null }, auto: a, count: a.length }; }
      case "/api/rules": return { rules: [], saved: [] };
      case "/api/watches": return { watches: [] };
      case "/api/alerts": return { items: [], alerts: [] };
      case "/api/tracked": return { tracked: [] };
      case "/api/reader": return { ok: false, error: "القارئ غير متاح في نسخة الهاتف، افتح الرابط الأصلي" };
      case "/api/phone": return { error: 1 };
      default: return { ok: true, note: "غير متاح في النسخة الثابتة" };
    }
  }
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : input.url;
    if (url.startsWith("/api/") || url.startsWith("api/")) {
      const u = new URL(url.replace(/^\/?/, "/"), "http://x");
      return route(u.pathname, u.searchParams).then(o => new Response(JSON.stringify(o), { headers: { "Content-Type": "application/json" } }));
    }
    return realFetch(input, init);
  };
})();
