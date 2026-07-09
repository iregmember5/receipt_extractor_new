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
.result{width:100%;max-width:1100px}
.result h2{font-size:1.1rem;margin-bottom:.5rem}
.hint{font-size:.75rem;color:#9ca3af;text-align:center;margin-top:.25rem}
#dbg{font-size:11px;color:#666;margin-top:4px}
#canvasWrap{overflow-x:auto}

#tagPalette{display:flex;gap:10px;margin-bottom:12px}
.tag-pill{cursor:grab;padding:6px 14px;border-radius:6px;font-size:13px;font-weight:bold;border:2px dashed;user-select:none}
.tag-pill:active{cursor:grabbing}
.tag-pill[data-label="amount"]{background:#dbeafe;border-color:#2563eb;color:#1e3a8a}
.tag-pill[data-label="description"]{background:#dcfce7;border-color:#16a34a;color:#14532d}
.tag-pill[data-label="date"]{background:#fef3c7;border-color:#d97706;color:#78350f}

.tagged-amount{background:#dbeafe!important;outline:2px solid #2563eb!important}
.tagged-description{background:#dcfce7!important;outline:2px solid #16a34a!important}
.tagged-date{background:#fef3c7!important;outline:2px solid #d97706!important}

/* Low-confidence flag: dashed underline, doesn't fix anything, just draws the eye */
.low-conf{border-bottom:2px dashed #dc2626!important}

/* Editable spans get a focus ring so it's clear they're editable/being edited */
.ocr-span{cursor:text}
.ocr-span:hover{outline:1px dashed #9ca3af}
.ocr-span:focus{outline:2px solid #9333ea!important;background:rgba(147,51,234,0.08)!important}
.ocr-span.edited{box-shadow:0 0 0 1px #9333ea inset}

/* Side-by-side layout: original photo | reconstructed receipt */
.mainRow{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}
#imgPanel{flex:0 0 auto}
#imgPanel h3{font-size:.85rem;color:#6b7280;margin-bottom:.4rem;font-weight:normal}
#origImg{max-width:320px;max-height:600px;border:1px solid #d1d5db;display:block;background:#e5e7eb}

#submitTagsBtn{margin-top:14px}
#tagsOutput{margin-top:10px;background:#111827;color:#d1fae5;padding:.75rem;border-radius:6px;font-size:12px;white-space:pre-wrap;display:none;max-width:1100px}
#saveStatus{font-size:.8rem;margin-top:6px;display:none}
#saveStatus.ok{color:#15803d}
#saveStatus.fail{color:#b91c1c}

.legend{font-size:11px;color:#6b7280;margin-top:6px;display:flex;gap:14px;flex-wrap:wrap}
.legend span{display:inline-flex;align-items:center;gap:4px}
.legend .sw{width:10px;height:10px;border-radius:2px;display:inline-block}
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

  <div id="tagPalette">
    <div class="tag-pill" draggable="true" data-label="amount">Amount</div>
    <div class="tag-pill" draggable="true" data-label="description">Description</div>
    <div class="tag-pill" draggable="true" data-label="date">Date</div>
  </div>

  <div class="mainRow">
    <div id="imgPanel">
      <h3>Original photo</h3>
      <img id="origImg" alt="Original uploaded receipt">
    </div>

    <div>
      <div id="canvasWrap">
        <div id="canvas" style="position:relative;border:1px solid #d1d5db;background:#fff"></div>
      </div>
      <p id="dbg"></p>
      <p class="hint">Drag a label onto the matching text. Click any text to edit it directly.</p>
      <div class="legend">
        <span><span class="sw" style="background:rgba(255,0,0,0.15);border:1px solid rgba(255,0,0,0.4)"></span>Debug border</span>
        <span><span class="sw" style="border-bottom:2px dashed #dc2626;background:none"></span>Low OCR confidence &mdash; double check</span>
        <span><span class="sw" style="box-shadow:0 0 0 1px #9333ea inset;background:#fff;border:1px solid #ddd"></span>Edited by you</span>
      </div>
      <label style="font-size:12px;margin-top:4px;display:flex;align-items:center;gap:4px">
        <input type="checkbox" id="debugToggle" checked> Debug borders
      </label>
    </div>
  </div>

  <button id="submitTagsBtn" type="button">Submit tags</button>
  <p id="saveStatus"></p>
  <pre id="tagsOutput"></pre>
</div>


<script>
const form=document.getElementById('form'), input=document.getElementById('fileInput');
const btn=document.getElementById('btn'), errDiv=document.getElementById('error');
const loadP=document.getElementById('loading'), resultDiv=document.getElementById('result');
const canvas=document.getElementById('canvas'), dbg=document.getElementById('dbg');
const debugToggle=document.getElementById('debugToggle');
const submitTagsBtn=document.getElementById('submitTagsBtn'), tagsOutput=document.getElementById('tagsOutput');
const origImg=document.getElementById('origImg');
const saveStatus=document.getElementById('saveStatus');

const BACKEND='http://127.0.0.1:8000';

// Tagging feature: stores the current amount/description/date selections.
// Reset every time a new receipt is processed. Now also carries the
// original rec_texts array index, so edits can be sent back unambiguously.
let tags={amount:null,description:null,date:null};

// Tracks every user edit as index -> newText. Only entries the user
// actually typed into end up here (nothing is added just from rendering).
let editsMap=new Map();

// The json_url returned by the backend for the receipt currently on
// screen — needed so Submit knows which saved file to update.
let currentJsonUrl=null;

const LOW_CONF_THRESHOLD=0.90;

// Wire up drag start on each label pill — this only needs to happen once,
// the pills always exist in the DOM (they don't get recreated per upload).
document.querySelectorAll('.tag-pill').forEach(pill=>{
  pill.addEventListener('dragstart', e=>{
    e.dataTransfer.setData('text/plain', pill.dataset.label);
  });
});

// Applies a tag to a dropped-on span: clears any other span that
// previously held this same label (only one span per label at a time),
// highlights the new one, and records it in the tags object along with
// the span's original rec_texts index.
function applyTag(label, el){
  const cls='tagged-'+label;
  canvas.querySelectorAll('.'+cls).forEach(prev=>prev.classList.remove(cls));
  el.classList.add(cls);
  tags[label]={text:el.textContent, index:parseInt(el.dataset.index,10)};
}

// Whenever the user edits a span's text in place:
//  1) record it in editsMap so Submit can send it to the backend
//  2) if that span currently holds a tag, keep the tags object in sync
//     too, so the correction flows straight into the tagged output
function onSpanEdited(el){
  const idx=parseInt(el.dataset.index,10);
  if(!Number.isNaN(idx)){
    editsMap.set(idx, el.textContent);
  }
  el.classList.add('edited');
  ['amount','description','date'].forEach(label=>{
    if(el.classList.contains('tagged-'+label)){
      tags[label]={text:el.textContent, index:idx};
    }
  });
}

submitTagsBtn.addEventListener('click', async ()=>{
  const edits=Array.from(editsMap.entries()).map(([index,newText])=>({index,newText}));

  tagsOutput.style.display='block';
  tagsOutput.textContent=JSON.stringify({tags, edits}, null, 2);

  if(!currentJsonUrl){
    saveStatus.style.display='block';
    saveStatus.className='fail';
    saveStatus.textContent='No processed receipt to save yet — upload one first.';
    return;
  }

  saveStatus.style.display='block';
  saveStatus.className='';
  saveStatus.textContent='Saving corrections...';
  submitTagsBtn.disabled=true;

  try{
    const r=await fetch(BACKEND+'/api/update-receipt/', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ json_url: currentJsonUrl, edits, tags })
    });
    const d=await r.json();
    if(!r.ok){
      saveStatus.className='fail';
      saveStatus.textContent='Save failed: '+(d.error||r.status);
    }else{
      saveStatus.className='ok';
      saveStatus.textContent='Saved '+(d.applied_indices ? d.applied_indices.length : 0)+' correction(s) to the original JSON on disk.';
    }
    tagsOutput.textContent=JSON.stringify({tags, edits, backend_response:d}, null, 2);
  }catch(e){
    saveStatus.className='fail';
    saveStatus.textContent='Save failed: '+e.message;
  }finally{
    submitTagsBtn.disabled=false;
  }
});

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
  tags={amount:null,description:null,date:null};
  editsMap=new Map();
  currentJsonUrl=null;
  tagsOutput.style.display='none';
  saveStatus.style.display='none';

  const file=input.files[0];
  if(!file){showErr('Select a file');return}

  // Show the original uploaded photo immediately (client-side preview,
  // no server round trip needed) so the user has ground truth to compare
  // the reconstruction against.
  origImg.src=URL.createObjectURL(file);

  btn.disabled=true;
  loadP.style.display='block';

  let jsonUrl;
  try{
    const fd=new FormData();fd.append('receipt_image',file);
    const r=await fetch(BACKEND+'/api/process-receipt/',{method:'POST',body:fd});
    const d=await r.json();
    if(!r.ok){showErr(d.error||'Failed');return}
    jsonUrl=d.json_url;
    currentJsonUrl=jsonUrl;
  }catch(e){showErr(e.message.includes('fetch')?'CORS error - check Django CORS settings':e.message);return}

  try{
    const r=await fetch(BACKEND+jsonUrl);
    if(!r.ok){showErr('Fetch OCR failed status '+r.status);return}
    const data=await r.json();
    const texts=data.rec_texts||[],polys=data.rec_polys||[],scores=data.rec_scores||[];
    if(!texts.length){showErr('No text detected');return}

    // Build items with bbox, score, and the ORIGINAL index into rec_texts.
    // origIndex is what lets a correction be written back to the exact
    // same position later, no matter how items get merged/reordered
    // during dedup/clustering below.
    let items=texts.map((t,i)=>{
      if(!polys[i]||polys[i].length!==4)return null;
      const xs=polys[i].map(p=>p[0]),ys=polys[i].map(p=>p[1]);
      return{
        text:t,score:scores[i]||0,
        x_min:Math.min(...xs),x_max:Math.max(...xs),
        y_min:Math.min(...ys),y_max:Math.max(...ys),
        origIndex:i
      };
    }).filter(x=>x);

    if(!items.length){showErr('No valid polygons');return}

    items=deduplicate(items);

    items.forEach(it=>{it.h=it.y_max-it.y_min});

    const sorted=[...items].sort((a,b)=> a.y_min-b.y_min || a.x_min-b.x_min);

    const HEIGHT_RATIO_MAX=1.8;

    let rows=clusterRows(sorted, LINE_GAP_FACTOR, HEIGHT_RATIO_MAX);

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

    rows.sort((a,b)=>a.y0-b.y0);

    itemsPerRow=rows.map(r=>r.items.length);
    medPerRow=median(itemsPerRow);

    rows.forEach(r=>r.items.sort((a,b)=>a.x_min-b.x_min));

    rows.forEach(r=>{ r.medianH=median(r.items.map(x=>x.h)); });

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

    let totalSpans=0,removedDups=texts.length-items.length,lowConfCount=0;

    const meas=document.createElement('canvas').getContext('2d');

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
        spans.push({ text:it.text,left:(it.x_min-x0)*s,top,fz,targetW,naturalW,scaleX,item:it });
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
        el.className='ocr-span';
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

        // Original rec_texts index — required for saving corrections
        // back to the exact right position later.
        el.dataset.index=sp.item.origIndex;

        // Low-confidence flag: purely visual, doesn't change any data,
        // just tells the user "OCR wasn't very sure about this one".
        if(sp.item.score < LOW_CONF_THRESHOLD){
          el.classList.add('low-conf');
          el.title='Low OCR confidence ('+Math.round(sp.item.score*100)+'%) — please verify against the original photo';
          lowConfCount++;
        }

        // Make the span directly editable in place, like a Google Doc.
        el.contentEditable='true';
        el.spellcheck=false;
        el.addEventListener('input', ()=>onSpanEdited(el));

        // Drop target: accepts a label dragged from the tag palette.
        el.addEventListener('dragover', ev=>{ ev.preventDefault(); });
        el.addEventListener('drop', ev=>{
          ev.preventDefault();
          const label=ev.dataTransfer.getData('text/plain');
          if(label) applyTag(label, el);
        });

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
      (removedDups?' | Dups: '+removedDups:'')+
      (lowConfCount?' | Low-confidence: '+lowConfCount:'');
    resultDiv.style.display='block';
  }catch(e){showErr(e.message.includes('fetch')?'CORS error - check Django CORS settings':e.message)}
  finally{btn.disabled=false;loadP.style.display='none'}
});
</script>
</body>
</html>