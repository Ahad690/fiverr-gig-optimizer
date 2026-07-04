#!/usr/bin/env python3
"""build_catalog.py — render gig-config.json to a self-contained HTML. FR14.

Reads a gig-config.json (§7.2) and writes a single fiverr-catalog.html with:
  - canvas thumbnails (1280x769) drawn from each gig's img block
  - a copy-ready AI image-generation prompt per gig, for users who prefer
    ChatGPT/DALL-E/Midjourney over the built-in PNG. Primary source is the
    model-authored ``img.ai_prompt`` (written with the rest of the gig copy —
    it can describe scenes/compositions the canvas can't draw); when absent,
    a deterministic composer mirrors the canvas design as a fallback.
  - copy-to-clipboard buttons for title / description / tags
  - per-gig PNG download (from the canvas)
  - a cross-sell map and a phase-based action plan
  - a provenance banner

This is the ONLY presentation component. It performs NO scoring: competition,
scores, and pricing are read as authoritative precomputed inputs.

CLI:
    build_catalog.py gig-config.json [--out fiverr-catalog.html]
"""
import argparse
import json
import sys

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fiverr Gig Catalog</title>
<style>
  :root { --bg:#0b0f14; --card:#141b24; --ink:#e6edf3; --mut:#8b98a5; --line:#222d3a; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  header { padding:28px 24px; border-bottom:1px solid var(--line); }
  h1 { margin:0 0 6px; font-size:22px; }
  .prov { color:var(--mut); font-size:13px; }
  .wrap { max-width:1100px; margin:0 auto; padding:24px; }
  .gig { background:var(--card); border:1px solid var(--line); border-radius:12px;
         padding:20px; margin:0 0 22px; }
  .gig h2 { margin:0 0 4px; font-size:18px; }
  .meta { color:var(--mut); font-size:13px; margin-bottom:14px; }
  .pill { display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px;
          border:1px solid var(--line); margin-right:6px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
  @media (max-width:760px){ .grid { grid-template-columns:1fr; } }
  canvas { width:100%; height:auto; border-radius:10px; border:1px solid var(--line); }
  .tiers { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:14px 0; }
  .tier { border:1px solid var(--line); border-radius:10px; padding:12px; }
  .tier .price { font-size:22px; font-weight:700; }
  .tier ul { padding-left:16px; margin:8px 0 0; color:var(--mut); font-size:13px; }
  .desc { white-space:pre-wrap; color:#cdd7e1; font-size:14px; }
  button { cursor:pointer; background:#1f6feb; color:#fff; border:0; border-radius:8px;
           padding:7px 12px; font-size:13px; margin:4px 6px 0 0; }
  button.alt { background:#21303f; }
  .xsell { color:var(--mut); font-size:13px; margin-top:10px; }
  .plan { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px; }
  .plan h3 { margin:0 0 10px; }
  .phase { margin:0 0 10px; }
  .flag { color:#f0883e; font-size:12px; }
  code { background:#0d1117; padding:1px 5px; border-radius:5px; }
  .contrib { margin-top:12px; padding:10px 14px; border:1px solid #2d6; border-left:4px solid #2d6;
             border-radius:8px; background:#0e1a12; color:#bdf5cf; font-size:14px; }
  .contrib a { color:#5ee08a; font-weight:600; }
  .contrib-off { color:var(--mut); font-size:12px; }
  details.aiprompt { margin-top:8px; }
  details.aiprompt summary { cursor:pointer; color:var(--mut); font-size:13px; }
  details.aiprompt pre { white-space:pre-wrap; background:#0d1117; border:1px solid var(--line);
    border-radius:8px; padding:12px; font-size:12.5px; line-height:1.5; color:#cdd7e1; }
</style>
</head>
<body>
<header>
  <h1>Fiverr Gig Catalog __SELLER__</h1>
  <div class="prov">__PROVENANCE__</div>
  __CONTRIB__
</header>
<div class="wrap" id="app"></div>
<script>
const CONFIG = __CONFIG_JSON__;

function draw(canvas, img){
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const g = ctx.createLinearGradient(0,0,W,H);
  g.addColorStop(0, img.bg1 || '#0b0f14');
  g.addColorStop(1, img.bg2 || '#141b24');
  ctx.fillStyle = g; ctx.fillRect(0,0,W,H);
  ctx.fillStyle = img.accent || '#06b6d4';
  ctx.fillRect(0, 0, 14, H);
  ctx.fillStyle = '#ffffff';
  ctx.font = '700 86px system-ui, sans-serif';
  wrapText(ctx, (img.headline||'').toUpperCase(), 60, 200, W-120, 92);
  ctx.fillStyle = img.accent || '#06b6d4';
  ctx.font = '600 36px system-ui, sans-serif';
  ctx.fillText(img.sub||'', 60, 330);
  if (img.badge){
    ctx.font = '700 26px system-ui, sans-serif';
    const bw = ctx.measureText(img.badge).width + 40;
    ctx.fillStyle = img.accent || '#06b6d4';
    roundRect(ctx, 60, 380, bw, 50, 10); ctx.fill();
    ctx.fillStyle = '#0b0f14'; ctx.fillText(img.badge, 80, 414);
  }
  if (img.tools && img.tools.length){
    ctx.fillStyle = '#cdd7e1'; ctx.font = '400 28px system-ui, sans-serif';
    ctx.fillText(img.tools.join('  •  '), 60, H-70);
  }
}
function roundRect(ctx,x,y,w,h,r){ ctx.beginPath(); ctx.moveTo(x+r,y);
  ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }
function wrapText(ctx,text,x,y,maxW,lh){
  const words=(text||'').split(' '); let line=''; let yy=y;
  for(const w of words){ const t=line?line+' '+w:w;
    if(ctx.measureText(t).width>maxW && line){ ctx.fillText(line,x,yy); line=w; yy+=lh; }
    else line=t; }
  if(line) ctx.fillText(line,x,yy);
}
function copy(text,btn){ navigator.clipboard.writeText(text).then(()=>{
  const o=btn.textContent; btn.textContent='Copied!'; setTimeout(()=>btn.textContent=o,1200); }); }

// FALLBACK image prompt: mirrors the flat canvas design, built only from the
// gig's own img block. The PRIMARY path is gig.img.ai_prompt — authored by the
// model while assembling gig-config.json (thumbnail design is offer design,
// so creative freedom is allowed there; an image model can render scenes the
// canvas can't). This composer covers configs that lack ai_prompt.
function aiPrompt(gig){
  const img = gig.img || {};
  const accent = img.accent || '#06b6d4';
  const bg1 = img.bg1 || '#0b0f14', bg2 = img.bg2 || '#141b24';
  const lines = [
    'Design a professional Fiverr gig thumbnail, exactly 1280x769 pixels (landscape).',
    `Service: "${gig.title || ''}"${gig.cat ? ' (category: ' + gig.cat + ')' : ''}.`,
    `Dominant element: the headline "${(img.headline || gig.title || '').toUpperCase()}" in very large, bold, white uppercase sans-serif type, left-aligned with generous margins.`,
  ];
  if (img.sub) lines.push(`Below it, a smaller secondary line in the accent color: "${img.sub}".`);
  if (img.badge) lines.push(`A small rounded pill badge in the accent color with dark text reading "${img.badge}".`);
  if (img.tools && img.tools.length) lines.push(`A footer row of tool names in small muted text: ${img.tools.join(' • ')}.`);
  lines.push(
    `Background: a dark, subtle diagonal gradient from ${bg1} to ${bg2}. Single accent color ${accent}, used for a thin bar above the headline, the badge, and one or two simple geometric shapes.`,
    'Style: flat, modern, minimal tech aesthetic; strong contrast; crisp typography; plenty of negative space.',
    'Do NOT include: photos of people, stock-photo textures, watermarks, logos, or any text other than the strings quoted above. All quoted text must be spelled exactly as written.'
  );
  return lines.join('\n');
}

const app = document.getElementById('app');
CONFIG.gigs.forEach(gig=>{
  const el=document.createElement('div'); el.className='gig';
  const tags=(gig.tags||[]).join(', ');
  const flags=(gig.scores&&gig.scores.flags&&gig.scores.flags.length)?
    `<span class="flag">flags: ${gig.scores.flags.join(', ')}</span>`:'';
  el.innerHTML=`
    <h2>${gig.title||''}</h2>
    <div class="meta">
      <span class="pill">Phase ${gig.phase}</span>
      <span class="pill">${gig.cat||''}</span>
      <span class="pill">${(gig.competition&&gig.competition.tier)||''} · ${(gig.competition&&gig.competition.count)??'?'} gigs</span>
      <span class="pill">opp ${(gig.scores&&gig.scores.opportunity)??'n/a'}</span>
      ${flags}
    </div>
    <div class="grid">
      <div>
        <canvas width="1280" height="769" id="cv${gig.id}"></canvas>
        <div>
          <button class="alt" id="dl${gig.id}">Download PNG</button>
          <button class="alt" id="cp${gig.id}">Copy AI image prompt</button>
        </div>
        <details class="aiprompt">
          <summary>AI image prompt — paste into ChatGPT / DALL·E / Midjourney instead of using the PNG</summary>
          <pre id="pp${gig.id}"></pre>
        </details>
      </div>
      <div>
        <div class="tiers">
          ${['basic','standard','premium'].map(t=>{
            const p=gig.pricing&&gig.pricing[t]; if(!p) return '';
            return `<div class="tier"><div>${p.name||t}</div>
              <div class="price">${p.price!=null?'$'+p.price:'—'}</div>
              <div style="color:var(--mut);font-size:12px">${p.del||''} · ${p.rev||''} rev</div>
              <ul>${(p.items||[]).map(i=>`<li>${i}</li>`).join('')}</ul></div>`;
          }).join('')}
        </div>
        <button id="ct${gig.id}">Copy title</button>
        <button id="cd${gig.id}">Copy description</button>
        <button id="cg${gig.id}">Copy tags</button>
        <div class="xsell">${gig.xsell||''}</div>
      </div>
    </div>
    <p class="desc">${(gig.desc||'').replace(/</g,'&lt;')}</p>`;
  app.appendChild(el);
  draw(document.getElementById('cv'+gig.id), gig.img||{});
  // Prefer the model-authored prompt (richer: scenes/metaphors an image model
  // can render); fall back to the deterministic canvas-mirror when absent.
  const prompt = (gig.img && gig.img.ai_prompt) ? gig.img.ai_prompt : aiPrompt(gig);
  document.getElementById('pp'+gig.id).textContent = prompt;
  document.getElementById('cp'+gig.id).onclick=e=>copy(prompt,e.target);
  document.getElementById('ct'+gig.id).onclick=e=>copy(gig.title||'',e.target);
  document.getElementById('cd'+gig.id).onclick=e=>copy(gig.desc||'',e.target);
  document.getElementById('cg'+gig.id).onclick=e=>copy(tags,e.target);
  document.getElementById('dl'+gig.id).onclick=()=>{
    const c=document.getElementById('cv'+gig.id);
    const a=document.createElement('a'); a.download='gig-'+gig.id+'.png';
    a.href=c.toDataURL('image/png'); a.click(); };
});

// Cross-sell map + action plan
const plan=document.createElement('div'); plan.className='plan';
const byPhase={};
CONFIG.gigs.forEach(g=>{ (byPhase[g.phase]=byPhase[g.phase]||[]).push(g); });
let planHtml='<h3>Launch plan</h3>';
Object.keys(byPhase).sort().forEach(ph=>{
  planHtml+=`<div class="phase"><strong>Phase ${ph}</strong><ul>`+
    byPhase[ph].map(g=>`<li>Gig #${g.id}: ${g.title} — <code>${g.xsell||''}</code></li>`).join('')+
    '</ul></div>';
});
plan.innerHTML=planHtml; app.appendChild(plan);
</script>
</body>
</html>
"""


def render(config):
    seller = config.get("seller", {})
    name = seller.get("name") or ""
    seller_line = f"— {name}" if name else ""
    prov = config.get("data_provenance", {})
    prov_line = (
        f"Pricing: {prov.get('pricing_source','?')} "
        f"(generated {prov.get('pricing_generated_at','?')}) · "
        f"Competition: {prov.get('competition_source','?')} · "
        f"Match confidence: {prov.get('match_confidence')}"
    )
    import reminders
    html = HTML_TEMPLATE
    html = html.replace("__SELLER__", seller_line)
    html = html.replace("__PROVENANCE__", prov_line)
    html = html.replace("__CONTRIB__", reminders.contribution_html())
    html = html.replace("__CONFIG_JSON__", json.dumps(config))
    return html


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render gig-config.json to fiverr-catalog.html.")
    ap.add_argument("config", help="Path to gig-config.json.")
    ap.add_argument("--out", default="fiverr-catalog.html")
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as fh:
        config = json.load(fh)

    html = render(config)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"Wrote {args.out} ({len(config.get('gigs', []))} gigs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
