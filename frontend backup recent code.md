<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Receipt Extractor</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Courier New",monospace;background:#f5f5f5;color:#333;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:2rem 1rem}
h1{font-size:1.75rem;margin-bottom:1.5rem}
form{display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem}
input[type="file"]::file-selector-button{margin-right:.75rem;padding:.5rem 1rem;border:none;border-radius:4px;background:#1f2937;color:#fff;cursor:pointer}
button{background:#2563eb;color:#fff;border:none;padding:.5rem 1.25rem;border-radius:4px;cursor:pointer;font-size:.95rem}
button:disabled{opacity:.5}
#error{max-width:500px;background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;padding:.75rem 1rem;border-radius:4px;font-size:.875rem;margin-bottom:1rem;display:none}
#loading{color:#6b7280;margin-bottom:1rem;display:none}
.result{width:100%;max-width:900px}
.result h2{font-size:1.1rem;margin-bottom:.5rem}
.hint{font-size:.75rem;color:#9ca3af;text-align:center;margin-top:.25rem}
#dbg{font-size:11px;color:#666;margin-top:4px}
#canvasWrap{overflow-x:auto}
</style>
</head>
<body>

<h1>Receipt Extractor</h1>

<form id="form">
<input type="file" id="fileInput" accept="image/*">
<button type="submit" id="btn">Upload & Process</button>
</form>

<div id="error"></div>
<p id="loading">Processing...</p>

<div id="result" class="result" style="display:none">
  <h2>Reconstructed Receipt</h2>
  <div id="canvasWrap">
    <div id="canvas" style="position:relative;border:1px solid #d1d5db;background:#fff"></div>
  </div>
  <p id="dbg"></p>
  <p class="hint">Text is selectable</p>
  <label style="font-size:12px;margin-top:4px;display:flex;align-items:center;gap:4px">
    <input type="checkbox" id="debugToggle" checked> Debug borders
  </label>
</div>

<script>
const form=document.getElementById('form'), input=document.getElementById('fileInput');
const btn=document.getElementById('btn'), errDiv=document.getElementById('error');
const loadP=document.getElementById('loading'), resultDiv=document.getElementById('result');
const canvas=document.getElementById('canvas'), dbg=document.getElementById('dbg');
const debugToggle=document.getElementById('debugToggle');

function showErr(m){errDiv.style.display='block';errDiv.textContent=m;btn.disabled=false;loadP.style.display='none'}

function computeIoU(a,b){
  const xOvl=Math.max(0,Math.min(a.x_max,b.x_max)-Math.max(a.x_min,b.x_min));
  const yOvl=Math.max(0,Math.min(a.y_max,b.y_max)-Math.max(a.y_min,b.y_min));
  const inter=xOvl*yOvl;
  const areaA=(a.x_max-a.x_min)*(a.y_max-a.y_min);
  const areaB=(b.x_max-b.x_min)*(b.y_max-b.y_min);
  const union=areaA+areaB-inter;
  return union>0?inter/union:0;
}

function median(arr){
  const s=[...arr].sort((a,b)=>a-b);
  const mid=Math.floor(s.length/2);
  return s.length%2?s[mid]:(s[mid-1]+s[mid])/2;
}

function deduplicate(items){
  const kept=[];
  for(let i=0;i<items.length;i++){
    let dup=false;
    for(let j=0;j<kept.length;j++){
      if(computeIoU(items[i],kept[j])>0.7&&items[i].text.trim().toLowerCase()===kept[j].text.trim().toLowerCase()){
        if(items[i].score>kept[j].score) kept[j]=items[i];
        dup=true;break;
      }
    }
    if(!dup) kept.push(items[i]);
  }
  return kept;
}

/*
  ROW CLUSTERING — CENTER-DISTANCE APPROACH
  -------------------------------------------
  Two structural fixes are combined here:

  1) LAST-ROW-ONLY COMPARISON. Items are processed in y_min sorted order,
     so the only row a new item can legitimately belong to is the most
     recently created one. Comparing against all previous rows (the old
     bug) let an item jump backward into an earlier row whose boundary had
     drifted downward from prior merges. We never do that here.

  2) CENTER-DISTANCE instead of EDGE-OVERLAP. The previous version decided
     "same line?" by measuring how much two bounding boxes overlap at the
     edges. That is fragile: OCR polygons are noisy at the edges (a word
     with a descender like "y" or "g", or a slightly tilted glyph, can
     produce a taller box that eats into the next line's space) even when
     the true text lines don't overlap at all. The VERTICAL CENTER of a
     bounding box is far more stable than its edges, so we cluster using
     center-to-center distance instead:

       centerDist = |item.centerY - row.centerY|
       threshold  = LINE_GAP_FACTOR * min(item.h, row.avgH)

     If centerDist is small relative to the text height, the item is on
     the same physical line. If it's close to a full line-height or more,
     it's the next line — this matches how lines are actually laid out
     (line spacing is normally close to the font's own height), and it
     isn't fooled by a stray tall bounding box the way edge-overlap was.

  LINE_GAP_FACTOR is the one knob that matters. 0.6 means: an item is
  considered part of the current row only if its center is within 60% of
  a text-height of the row's center. This is intentionally receipt-
  agnostic — it doesn't hardcode any particular font size, layout, or
  receipt type, only a ratio relative to each document's own text size.
*/
const LINE_GAP_FACTOR = 0.6;

function clusterRows(sortedItems, LINE_GAP_FACTOR, HEIGHT_RATIO_MAX){
  const rows=[];
  for(const item of sortedItems){
    const itemCenterY = (item.y_min + item.y_max) / 2;
    const row = rows.length ? rows[rows.length-1] : null;
    let merged=false;

    if(row){
      const heightRatio = Math.max(item.h, row.avgH) / Math.min(item.h, row.avgH);
      const centerDist = Math.abs(itemCenterY - row.centerY);
      const threshold = LINE_GAP_FACTOR * Math.min(item.h, row.avgH);

      if(centerDist <= threshold && heightRatio <= HEIGHT_RATIO_MAX){
        row.items.push(item);
        row.y0=Math.min(row.y0,item.y_min);
        row.y1=Math.max(row.y1,item.y_max);
        row.avgH=row.items.reduce((s,x)=>s+x.h,0)/row.items.length;
        // Recompute row center as the average center of its members —
        // stays stable even as more items are added, no drift toward
        // one outlier edge.
        row.centerY=row.items.reduce((s,x)=>s+(x.y_min+x.y_max)/2,0)/row.items.length;
        merged=true;
      }
    }

    if(!merged){
      rows.push({items:[item], y0:item.y_min, y1:item.y_max, avgH:item.h, centerY:itemCenterY});
    }
  }
  return rows;
}

form.addEventListener('submit', async e=>{
  e.preventDefault();
  errDiv.style.display='none';
  resultDiv.style.display='none';

  const file=input.files[0];
  if(!file){showErr('Select a file');return}

  btn.disabled=true;
  loadP.style.display='block';

  let jsonUrl;
  try{
    const fd=new FormData();fd.append('receipt_image',file);
    const r=await fetch('http://127.0.0.1:8000/api/process-receipt/',{method:'POST',body:fd});
    const d=await r.json();
    if(!r.ok){showErr(d.error||'Failed');return}
    jsonUrl=d.json_url;
  }catch(e){showErr(e.message.includes('fetch')?'CORS error - check Django CORS settings':e.message);return}

  try{
    const r=await fetch('http://127.0.0.1:8000/'+jsonUrl);
    if(!r.ok){showErr('Fetch OCR failed status '+r.status);return}
    const data=await r.json();
    const texts=data.rec_texts||[],polys=data.rec_polys||[],scores=data.rec_scores||[];
    if(!texts.length){showErr('No text detected');return}

    // Build items with bbox and inline score
    let items=texts.map((t,i)=>{
      if(!polys[i]||polys[i].length!==4)return null;
      const xs=polys[i].map(p=>p[0]),ys=polys[i].map(p=>p[1]);
      return{
        text:t,score:scores[i]||0,
        x_min:Math.min(...xs),x_max:Math.max(...xs),
        y_min:Math.min(...ys),y_max:Math.max(...ys)
      };
    }).filter(x=>x);

    if(!items.length){showErr('No valid polygons');return}

    // Deduplicate
    items=deduplicate(items);

    // Per-item height
    items.forEach(it=>{it.h=it.y_max-it.y_min});

    // Sort by y_min (then x_min as tiebreaker) before clustering
    const sorted=[...items].sort((a,b)=> a.y_min-b.y_min || a.x_min-b.x_min);

    const HEIGHT_RATIO_MAX=1.8;

    let rows=clusterRows(sorted, LINE_GAP_FACTOR, HEIGHT_RATIO_MAX);

    // Safety-net splitting pass: if any row still ends up abnormally large
    // (e.g. > 2x the median items-per-row), re-cluster just that row's
    // items with a stricter overlap threshold. With the last-row-only
    // approach above this should rarely trigger, but it's kept as a
    // second line of defense for unusual layouts.
    let itemsPerRow=rows.map(r=>r.items.length);
    let medPerRow=median(itemsPerRow);
    let splitCount=0;

    for(let ri=0;ri<rows.length;ri++){
      const row=rows[ri];
      if(row.items.length<=Math.max(3,medPerRow*2)) continue;
      const subSorted=[...row.items].sort((a,b)=>a.y_min-b.y_min || a.x_min-b.x_min);
      const subRows=clusterRows(subSorted, LINE_GAP_FACTOR*0.65, HEIGHT_RATIO_MAX);
      if(subRows.length>1){
        rows.splice(ri,1,...subRows);
        ri+=subRows.length-1;
        splitCount++;
      }
    }

    // Final sort (rows were built in order, this is a safety no-op)
    rows.sort((a,b)=>a.y0-b.y0);

    // Recompute stats after any splitting
    itemsPerRow=rows.map(r=>r.items.length);
    medPerRow=median(itemsPerRow);

    // Within each row, sort items left-to-right
    rows.forEach(r=>r.items.sort((a,b)=>a.x_min-b.x_min));

    // Median item height per row -> font size basis
    rows.forEach(r=>{ r.medianH=median(r.items.map(x=>x.h)); });

    // Global horizontal bounds
    let x0=Infinity,x1=-Infinity;
    for(const r of rows) for(const it of r.items){
      if(it.x_min<x0)x0=it.x_min;
      if(it.x_max>x1)x1=it.x_max;
    }
    const yGlob0=rows[0].y0;
    const yGlob1=rows[rows.length-1].y1;

    const W=500,s=W/(x1-x0||1),H=(yGlob1-yGlob0)*s;

    canvas.style.width=W+'px';
    canvas.style.height=H+'px';
    canvas.style.maxHeight='none';
    canvas.style.overflow='visible';
    canvas.innerHTML='';

    let totalSpans=0,removedDups=texts.length-items.length;

    const meas=document.createElement('canvas').getContext('2d');

    // Build span geometry per row, with min-gap enforcement
    const rowSpanData=[];
    for(const row of rows){
      const fz=Math.max(10,row.medianH*s*0.85);
      const top=(row.y0-yGlob0)*s;
      meas.font=fz+'px monospace';
      const spans=[];

      for(const it of row.items){
        const targetW=(it.x_max-it.x_min)*s;
        const naturalW=meas.measureText(it.text).width;
        let scaleX=naturalW>0&&targetW>0?targetW/naturalW:1;
        spans.push({ text:it.text,left:(it.x_min-x0)*s,top,fz,targetW,naturalW,scaleX });
      }

      const MIN_GAP_PX=Math.max(3,fz*0.25);
      for(let i=0;i<spans.length-1;i++){
        const cur=spans[i];
        const next=spans[i+1];
        if(cur.left+cur.targetW+MIN_GAP_PX>next.left){
          cur.scaleX=1;
        }
        const naturalRight=cur.left+cur.naturalW;
        if(naturalRight+MIN_GAP_PX>next.left){
          next.left=naturalRight+MIN_GAP_PX;
        }
      }

      rowSpanData.push(spans);
    }

    // Render
    for(const spans of rowSpanData){
      for(const sp of spans){
        const el=document.createElement('span');
        el.textContent=sp.text;
        el.style.position='absolute';
        el.style.left=sp.left+'px';
        el.style.top=sp.top+'px';
        el.style.fontSize=sp.fz+'px';
        el.style.fontFamily='monospace';
        el.style.whiteSpace='pre';
        el.style.lineHeight='1.2';

        if(sp.scaleX!==1){
          el.style.display='inline-block';
          el.style.transformOrigin='0 0';
          el.style.transform='scaleX('+sp.scaleX+')';
        }

        el.style.outline='1px solid rgba(255,0,0,0.4)';
        el.style.background='rgba(255,0,0,0.06)';

        canvas.appendChild(el);
        totalSpans++;
      }
    }

    // Recompute canvas width to fit any nudged text
    const allSpans=rowSpanData.flat();
    const renderedW=allSpans.length?Math.max(0,...allSpans.map(sp=>sp.left+(sp.scaleX===1?sp.naturalW:sp.targetW)))+10:W;
    const finalW=Math.max(W,renderedW);
    canvas.style.width=finalW+'px';

    debugToggle.onclick=()=>{
      const show=debugToggle.checked;
      canvas.querySelectorAll('span').forEach(el=>{
        el.style.outline=show?'1px solid rgba(255,0,0,0.4)':'none';
        el.style.background=show?'rgba(255,0,0,0.06)':'transparent';
      });
    };

    dbg.textContent='Items: '+items.length+' | Rows: '+rows.length+' | Spans: '+totalSpans+
      ' | Med/row: '+medPerRow.toFixed(1)+' | Auto-split rows: '+splitCount+
      (removedDups?' | Dups: '+removedDups:'');
    resultDiv.style.display='block';
  }catch(e){showErr(e.message.includes('fetch')?'CORS error - check Django CORS settings':e.message)}
  finally{btn.disabled=false;loadP.style.display='none'}
});
</script>
</body>
</html>