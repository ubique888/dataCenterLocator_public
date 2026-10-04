"""Build a standalone, dependency-free two-axis screening scatter plot."""

import json
from pathlib import Path

import pandas as pd


def build_scatter(
    sites: pd.DataFrame, output: Path, inheritance_threshold: float,
    symbiosis_threshold: float,
) -> None:
    records = [
        {
            "id": int(row.site_id),
            "name": str(row.site_name) if pd.notna(row.site_name) else "Unnamed site",
            "state": str(row.state) if pd.notna(row.state) else "",
            "x": round(float(row.inheritance_score), 3),
            "y": round(float(row.symbiosis_score), 3),
            "industry": int(row.industrial_sites_5km),
            "wwtp": int(row.wwtp_count_5km),
            "power": str(row.power_identity_evidence),
        }
        for row in sites.itertuples(index=False)
    ]
    payload = json.dumps(records, ensure_ascii=False).replace("<", "\\u003c")
    page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Infrastructure Inheritance × Industrial Symbiosis</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#193043;background:#f3f6f8}
*{box-sizing:border-box}body{margin:0;padding:28px}header{max-width:1400px;margin:auto}
h1{font-size:clamp(24px,3vw,38px);margin:0 0 7px;letter-spacing:-.025em}
.lead{color:#526675;max-width:900px;line-height:1.5;margin:0 0 24px}
.layout{max-width:1400px;margin:auto;display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:18px}
.panel{background:white;border:1px solid #dbe3e8;border-radius:12px;box-shadow:0 3px 16px #17324a0b}
.chart{padding:14px;min-height:690px;position:relative}canvas{width:100%;height:650px;display:block;cursor:crosshair}
.side{padding:20px}.side h2{font-size:16px;margin:0 0 14px}.stat{border-top:1px solid #e5ecf0;padding:12px 0}
.stat strong{display:block;font-size:25px;color:#0e7490}.stat span{font-size:12px;color:#526675}
.key{margin-top:18px;font-size:13px;line-height:1.8}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}
#tooltip{position:absolute;display:none;pointer-events:none;max-width:260px;padding:10px 12px;background:#193043;color:white;border-radius:7px;font-size:12px;line-height:1.5;box-shadow:0 5px 20px #0003}
.note{font-size:12px;color:#667986;line-height:1.5;margin-top:20px}@media(max-width:900px){body{padding:14px}.layout{grid-template-columns:1fr}.chart{min-height:550px}canvas{height:510px}}
</style></head><body>
<header><h1>Infrastructure inheritance × industrial symbiosis</h1>
<p class="lead">Two independent screening axes for EPA RE-Powering candidate sites. The upper-right quadrant marks sites scoring at least 60 on inheritance and 75 on symbiosis. Hover over a point for its source record and nearby-facility counts.</p></header>
<div class="layout"><div class="panel chart"><canvas id="scatter" aria-label="Scatter plot of inheritance versus symbiosis scores"></canvas><div id="tooltip"></div></div>
<aside class="panel side"><h2>Screening view</h2><div class="stat"><strong id="siteCount"></strong><span>sites passing the initial filter</span></div><div class="stat"><strong id="quadrantCount"></strong><span>sites in the high-high quadrant</span></div><div class="stat"><strong id="thresholds"></strong><span>inheritance / symbiosis cutoff</span></div><div class="key"><div><i class="dot" style="background:#0e7490"></i>High on both axes</div><div><i class="dot" style="background:#9aaeba"></i>Other screened sites</div></div><p class="note">Scores are screening utilities, not engineering feasibility or proof of recoverable heat or water. Name and point proximity do not establish shared parcels or commercial access. No combined overall score is used.</p></aside></div>
<script>
const sites=__DATA__;
const tx=__TX__,ty=__TY__;
const canvas=document.getElementById('scatter'),tip=document.getElementById('tooltip'),ctx=canvas.getContext('2d');
const high=s=>s.x>=tx&&s.y>=ty;
document.getElementById('siteCount').textContent=sites.length.toLocaleString();
document.getElementById('quadrantCount').textContent=sites.filter(high).length.toLocaleString();
document.getElementById('thresholds').textContent=tx.toFixed(1)+' / '+ty.toFixed(1);
let plot={};
function draw(){
 const dpr=window.devicePixelRatio||1,w=canvas.clientWidth,h=canvas.clientHeight;
 canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
 const l=68,r=20,t=20,b=67,pw=w-l-r,ph=h-t-b;plot={l,r,t,b,pw,ph};
 ctx.clearRect(0,0,w,h);ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h);
 ctx.fillStyle='#e5f6f4';ctx.fillRect(l+pw*tx/100,t,pw*(1-tx/100),ph*(1-ty/100));
 ctx.strokeStyle='#e2e9ed';ctx.lineWidth=1;ctx.font='12px system-ui';ctx.fillStyle='#617483';
 for(let v=0;v<=100;v+=20){let x=l+pw*v/100,y=t+ph*(1-v/100);
 ctx.beginPath();ctx.moveTo(x,t);ctx.lineTo(x,t+ph);ctx.moveTo(l,y);ctx.lineTo(l+pw,y);ctx.stroke();
 ctx.fillText(String(v),x-8,t+ph+19);ctx.fillText(String(v),l-34,y+4)}
 ctx.strokeStyle='#0e7490';ctx.setLineDash([5,5]);ctx.beginPath();ctx.moveTo(l+pw*tx/100,t);ctx.lineTo(l+pw*tx/100,t+ph);ctx.moveTo(l,t+ph*(1-ty/100));ctx.lineTo(l+pw,t+ph*(1-ty/100));ctx.stroke();ctx.setLineDash([]);
 for(const s of sites){ctx.beginPath();ctx.arc(l+pw*s.x/100,t+ph*(1-s.y/100),high(s)?5:2.1,0,Math.PI*2);ctx.fillStyle=high(s)?'#0e7490':'#8ca0ad55';ctx.fill()}
 ctx.font='600 11px system-ui';ctx.fillStyle='#07546b';for(const s of sites.filter(high)){ctx.fillText(s.name.slice(0,28),l+pw*s.x/100+9,t+ph*(1-s.y/100)-8)}
 ctx.fillStyle='#193043';ctx.font='600 13px system-ui';ctx.textAlign='center';ctx.fillText('Infrastructure inheritance score',l+pw/2,h-14);
 ctx.save();ctx.translate(18,t+ph/2);ctx.rotate(-Math.PI/2);ctx.fillText('Industrial symbiosis score',0,0);ctx.restore();ctx.textAlign='left';
}
canvas.addEventListener('mousemove',e=>{const rect=canvas.getBoundingClientRect(),mx=e.clientX-rect.left,my=e.clientY-rect.top;
 let best=null,dd=80;for(const s of sites){const px=plot.l+plot.pw*s.x/100,py=plot.t+plot.ph*(1-s.y/100),d=(px-mx)**2+(py-my)**2;if(d<dd){dd=d;best=s}}
 if(!best){tip.style.display='none';return}tip.textContent=best.name+' ('+best.state+') · Site '+best.id+' · Inheritance '+best.x+' · Symbiosis '+best.y+' · Industrial facilities 5 km: '+best.industry+' · WWTPs 5 km: '+best.wwtp+' · Power evidence: '+best.power;
 tip.style.display='block';tip.style.left=Math.min(mx+18,rect.width-270)+'px';tip.style.top=Math.max(10,my-50)+'px';});
canvas.addEventListener('mouseleave',()=>tip.style.display='none');window.addEventListener('resize',draw);draw();
</script></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        page.replace("__DATA__", payload)
        .replace("__TX__", f"{inheritance_threshold:.8f}")
        .replace("__TY__", f"{symbiosis_threshold:.8f}"),
        encoding="utf-8",
    )
