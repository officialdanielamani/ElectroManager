#pragma once
/*
 * PROGMEM page content for rack_locator.ino
 *
 * Kept in a separate header so the Arduino sketch preprocessor
 * (which injects #line directives for function-prototype generation)
 * never touches these raw string literals.
 */

#include <pgmspace.h>

static const char PAGE_HEAD[] PROGMEM = R"HTML(<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rack Locator</title>
<style>
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;margin:0;padding:14px;background:#f8f9fa}
h2{margin:0 0 4px;font-size:1.2rem}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.1);padding:14px;margin-bottom:14px}
.card-header{border-radius:6px 6px 0 0;padding:10px 14px;margin:-14px -14px 12px;color:#fff;font-weight:600;display:flex;align-items:center;justify-content:space-between}
.rack-status{font-size:.75rem;font-weight:400;opacity:.85}
.row{display:flex;gap:8px;flex-wrap:wrap}
input[type=text]{flex:1;min-width:180px;padding:7px 11px;border:1px solid #ced4da;border-radius:6px;font-size:.95rem}
button{padding:7px 18px;background:#0d6efd;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.95rem}
button:hover{background:#0b5ed7}
.btn-sm{padding:4px 12px;font-size:.8rem}
.btn-sec{background:#6c757d}
.btn-sec:hover{background:#5c636a}
.info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;margin-top:10px}
.info-item{background:#f1f3f5;border-radius:6px;padding:7px 10px}
.lbl{font-size:.68rem;color:#6c757d;text-transform:uppercase;letter-spacing:.04em}
.val{font-size:.92rem;font-weight:600;margin-top:2px;word-break:break-all}
.rack-scroll{overflow-x:auto;padding-bottom:4px}
.rack-grid{display:grid;gap:4px;width:max-content}
.cell{border:2px solid #dee2e6;border-radius:6px;padding:4px 3px;min-width:68px;min-height:62px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:11px;cursor:pointer}
.cell:hover{filter:brightness(.93)}
.cid{font-weight:700;font-size:10px;color:#495057}
.si{font-size:9px;color:#6c757d;margin-top:1px;max-width:64px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cnt{margin-top:3px}
.empty{background:#f8f9fa}
.has-items{background:#cfe2ff;border-color:#9ec5fe}
.merged{background:#cfe2ff;border-style:dashed;border-color:#0d6efd}
.grouped{background:#d1e7dd;border-color:#a3cfbb}
.unavail{background:#6c757d;border-color:#495057;color:#fff;cursor:default}
.unavail:hover{filter:none}
.unavail .cid,.unavail .si{color:#ddd}
.highlight{background:#ffc107!important;border:3px solid #fd7e14!important;animation:pulse 1.1s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
.badge{display:inline-block;padding:1px 6px;border-radius:10px;font-size:10px;font-weight:700}
.bp{background:#0d6efd;color:#fff}
.bs{background:#198754;color:#fff}
.bm{background:#6c757d;color:#fff}
.arrow{font-size:9px;color:#adb5bd}
.dim{font-size:9px;color:#adb5bd}
.legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.leg{display:flex;align-items:center;gap:5px;font-size:11px}
.lb{width:14px;height:14px;border-radius:3px;border:1px solid rgba(0,0,0,.2)}
.alert{padding:11px 14px;border-radius:6px;margin-top:8px;font-size:.88rem}
.aw{background:#fff3cd;border:1px solid #ffc107;color:#664d03}
.ae{background:#f8d7da;border:1px solid #f5c2c7;color:#842029}
.ai{background:#cff4fc;border:1px solid #9eeaf9;color:#055160}
.muted{color:#6c757d;font-size:.82rem}
.spin{display:inline-block;width:14px;height:14px;border:2px solid #dee2e6;border-top-color:#0d6efd;border-radius:50%;animation:spin .7s linear infinite;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
.res-item{padding:9px 14px;border-bottom:1px solid #f0f0f0;cursor:pointer;display:flex;align-items:center;gap:10px}
.res-item:last-child{border-bottom:none}
.res-item:hover{background:#f8f9fa}
.res-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.res-body{flex:1;min-width:0}
.res-name{font-weight:600;font-size:.92rem}
.res-sku{font-size:.74rem;color:#6c757d}
.res-loc{font-size:.78rem;color:#495057;margin-top:2px}
.back-bar{display:flex;align-items:center;gap:8px;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #f0f0f0}
.popup-overlay{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.45);display:none;z-index:200;align-items:flex-start;justify-content:center;padding-top:48px}
.popup{background:#fff;border-radius:10px;padding:16px 18px;max-width:460px;width:93%;max-height:78vh;overflow-y:auto;position:relative;box-shadow:0 8px 32px rgba(0,0,0,.18)}
.popup-close{position:absolute;top:10px;right:14px;font-size:1.4rem;cursor:pointer;color:#6c757d;line-height:1;font-weight:300}
.popup-close:hover{color:#333}
.ditem{border:1px solid #dee2e6;border-radius:6px;padding:8px 10px;margin-bottom:8px}
.dname{font-weight:600;font-size:.9rem}
.dsku{font-size:.75rem;color:#6c757d}
.dinfo{font-size:.8rem;color:#495057;margin-top:2px}
.dbatch{margin-top:5px;padding-top:5px;border-top:1px solid #f0f0f0;font-size:.8rem}
.dqty{color:#198754;font-weight:600}
.dqtylbl{color:#6c757d}
</style>
</head>
<body>
<div class="card">
<h2>Rack Locator</h2>
<p class="muted" style="margin:3px 0 10px">Enter item name, UUID, batch UID (e.g. ABC-B01), or ISN</p>
<form onsubmit="find(event)">
<div class="row">
<input id="q" type="text" placeholder="OLED, ABC-B01, ISN-0042..." autocomplete="off" autofocus>
<button type="submit">Find</button>
</div>
</form>
</div>
<div id="result"></div>
<div id="racks"></div>
<div id="drawer-popup" class="popup-overlay" onclick="closePopup(event)">
  <div class="popup">
    <span class="popup-close" onclick="document.getElementById('drawer-popup').style.display='none'">&times;</span>
    <div id="popup-content"></div>
  </div>
</div>
<script>
)HTML";

static const char PAGE_JS[] PROGMEM = R"JS(
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

// layouts[uuid] = layout response; highlights[uuid] = {row,col} or null
var layouts={}, highlights={};

// Stored search results so list items can reference by index
var _results=[];

// ── Init: load all configured racks ──────────────────────────────────────
window.onload=function(){
  if(!RACKS||!RACKS.length){
    document.getElementById('racks').innerHTML='<div class="alert aw">No rack UUIDs configured in firmware.</div>';
    return;
  }
  RACKS.forEach(function(uuid){loadRack(uuid);});
};

function loadRack(uuid){
  setRackLoading(uuid);
  fetch(EM+'/api/v1/rack/'+uuid+'/layout',{headers:{Authorization:'Bearer '+K}})
  .then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
  .then(function(d){
    if(!d.success)throw new Error('Bad response');
    layouts[uuid]=d;
    highlights[uuid]=null;
    renderRack(uuid);
  })
  .catch(function(ex){setRackError(uuid,ex.message);});
}

// ── Rack container helpers ────────────────────────────────────────────────
function rackDivId(uuid){return 'rack-'+uuid.replace(/[^a-zA-Z0-9]/g,'-');}

function setRackLoading(uuid){
  var id=rackDivId(uuid);
  var el=document.getElementById(id);
  if(!el){
    el=document.createElement('div');
    el.id=id;
    document.getElementById('racks').appendChild(el);
  }
  el.innerHTML="<div class='card'><div class='card-header' style='background:#6c757d'>Loading rack…</div>"
    +"<div style='padding:14px 0 4px'><span class='spin'></span> <span class='muted'>Fetching layout…</span></div></div>";
}

function setRackError(uuid,msg){
  var el=document.getElementById(rackDivId(uuid));
  if(el)el.innerHTML="<div class='alert ae'><strong>"+esc(uuid)+"</strong> — "+esc(msg)+"</div>";
}

// ── Search entry point ────────────────────────────────────────────────────
function find(e){
  e.preventDefault();
  var q=document.getElementById('q').value.trim();
  if(!q)return;
  document.getElementById('result').innerHTML='<p class="muted" style="padding:8px 0"><span class="spin"></span> Searching…</p>';
  _results=[];
  Object.keys(highlights).forEach(function(u){highlights[u]=null;});
  redrawAllRacks();
  fetch(EM+'/api/v1/location/search?q='+encodeURIComponent(q),{headers:{Authorization:'Bearer '+K}})
  .then(function(r){if(!r.ok)throw new Error('Search HTTP '+r.status);return r.json();})
  .then(function(d){
    if(!d.success||!d.results||!d.results.length){
      document.getElementById('result').innerHTML='<div class="alert aw">No items found for “'+esc(q)+'”.</div>';
      return;
    }
    _results=d.results;
    if(_results.length===1){
      // Only one match — go straight to detail
      selectItem(0);
    } else {
      renderResultList();
    }
  })
  .catch(function(ex){document.getElementById('result').innerHTML='<div class="alert ae">'+esc(ex.message)+'</div>';});
}

// ── Results list (multiple matches) ──────────────────────────────────────
function renderResultList(){
  var h="<div class='card'><div class='card-header' style='background:#495057'>"
    +_results.length+" results — tap to locate</div><div style='padding:2px 0'>";
  _results.forEach(function(item,i){
    var locs=item.locations||[];
    var inRacks=locs.filter(function(l){return l.location_type==='rack'&&RACKS.indexOf(l.rack_uuid)>=0;});
    var locText,dotColor;
    if(inRacks.length>0){
      dotColor='#198754';
      locText=inRacks.map(function(l){return esc(l.rack_name)+' → '+esc(l.drawer_cell);}).join(' &amp; ');
    } else {
      var g=locs.find(function(l){return l.location_type==='location';});
      var r=locs.find(function(l){return l.location_type==='rack';});
      if(g){locText=esc(g.location_name);dotColor='#6c757d';}
      else if(r){locText=esc(r.rack_name)+' (not configured)';dotColor='#fd7e14';}
      else{locText='No location assigned';dotColor='#adb5bd';}
    }
    h+="<div class='res-item' onclick='selectItem("+i+")'>"
      +"<span class='res-dot' style='background:"+dotColor+"'></span>"
      +"<div class='res-body'>"
      +"<div class='res-name'>"+esc(item.name)+"</div>";
    if(item.sku)h+="<div class='res-sku'>"+esc(item.sku)+"</div>";
    h+="<div class='res-loc'>"+locText+"</div>";
    h+="</div></div>";
  });
  h+="</div></div>";
  document.getElementById('result').innerHTML=h;
}

// ── Select an item from results ───────────────────────────────────────────
function selectItem(idx){
  var item=_results[idx];
  if(!item)return;

  Object.keys(highlights).forEach(function(u){highlights[u]=null;});

  var locs=item.locations||[];
  var matchedRackLocs=locs.filter(function(l){
    return l.location_type==='rack'&&RACKS.indexOf(l.rack_uuid)>=0;
  });
  var anyRackLoc=locs.find(function(l){return l.location_type==='rack';});
  var genLoc=locs.find(function(l){return l.location_type==='location';});

  if(matchedRackLocs.length>0){
    matchedRackLocs.forEach(function(loc){
      highlights[loc.rack_uuid]={row:loc.drawer_row,col:loc.drawer_col};
    });
    redrawAllRacks();
    var first=matchedRackLocs[0];
    fetch('/led?row='+first.drawer_row+'&col='+first.drawer_col
      +'&cols='+(layouts[first.rack_uuid]?layouts[first.rack_uuid].cols:1)).catch(function(){});
    renderItemDetail(item,matchedRackLocs[0],null,false);
  } else {
    renderItemDetail(item,anyRackLoc,genLoc,true);
  }
}

// ── Item detail card ──────────────────────────────────────────────────────
function renderItemDetail(item,rackLoc,genLoc,notInRacks){
  var col=rackLoc?rackLoc.rack_color||'#3a86ff':genLoc?genLoc.location_color||'#6c757d':'#6c757d';
  var h="<div class='card'>";
  // Back button when there were multiple results
  if(_results.length>1){
    h+="<div class='back-bar' style='padding:10px 14px 0'>"
      +"<button class='btn-sm btn-sec' onclick='renderResultList()' style='padding:4px 12px;font-size:.8rem;background:#6c757d;color:#fff;border:none;border-radius:5px;cursor:pointer'>"
      +"← Back</button>"
      +"<span class='muted' style='font-size:.8rem'>"+_results.length+" results</span>"
      +"</div>";
  }
  h+="<div class='card-header' style='background:"+col+"'>"+esc(item.name)+"</div><div class='info-grid'>";
  if(item.sku)        h+="<div class='info-item'><div class='lbl'>SKU</div><div class='val'>"+esc(item.sku)+"</div></div>";
  if(item.short_info) h+="<div class='info-item'><div class='lbl'>Info</div><div class='val'>"+esc(item.short_info)+"</div></div>";
  if(item.isn)        h+="<div class='info-item'><div class='lbl'>ISN</div><div class='val'>"+esc(item.isn)+"</div></div>";
  if(rackLoc){
    if(rackLoc.batch_label) h+="<div class='info-item'><div class='lbl'>Batch</div><div class='val'>"+esc(rackLoc.batch_label)+"</div></div>";
    if(rackLoc.quantity>0)  h+="<div class='info-item'><div class='lbl'>Total Qty</div><div class='val'>"+rackLoc.quantity+"</div></div>"
                            +"<div class='info-item'><div class='lbl'>Available</div><div class='val'>"+rackLoc.available+"</div></div>";
    h+="<div class='info-item'><div class='lbl'>Rack</div><div class='val'>"+esc(rackLoc.rack_name)+"</div></div>";
    h+="<div class='info-item'><div class='lbl'>Drawer</div><div class='val' style='color:#fd7e14'>"+esc(rackLoc.drawer_cell)+"</div></div>";
  } else if(genLoc){
    if(genLoc.batch_label) h+="<div class='info-item'><div class='lbl'>Batch</div><div class='val'>"+esc(genLoc.batch_label)+"</div></div>";
    if(genLoc.quantity>0)  h+="<div class='info-item'><div class='lbl'>Total Qty</div><div class='val'>"+genLoc.quantity+"</div></div>"
                           +"<div class='info-item'><div class='lbl'>Available</div><div class='val'>"+genLoc.available+"</div></div>";
    h+="<div class='info-item'><div class='lbl'>Location</div><div class='val'>"+esc(genLoc.location_name)+"</div></div>";
  }
  if(item.isn&&item.lent_out) h+="<div class='info-item'><div class='lbl'>Status</div><div class='val' style='color:#dc3545'>Lent out</div></div>";
  h+="</div>";
  if(notInRacks){
    var where=rackLoc?'in rack <strong>'+esc(rackLoc.rack_name)+'</strong>'
             :genLoc?'in location <strong>'+esc(genLoc.location_name)+'</strong>'
             :'with no location assigned';
    h+="<div class='alert ai' style='margin-top:8px'>Not in any configured rack — item is "+where+".</div>";
  }
  h+="</div>";
  document.getElementById('result').innerHTML=h;
}

// ── Render all racks (re-applies current highlights) ─────────────────────
function redrawAllRacks(){
  RACKS.forEach(function(uuid){if(layouts[uuid])renderRack(uuid);});
}

function renderRack(uuid){
  var layout=layouts[uuid];
  if(!layout)return;
  var hl=highlights[uuid]||null;
  var tRow=hl?hl.row:null, tCol=hl?hl.col:null;
  var color=layout.rack_color||'#3a86ff';
  var cols=layout.cols||1;

  var h="<div class='card'>"
    +"<div class='card-header' style='background:"+esc(color)+"'>"+esc(layout.rack_name)
    +(hl?"<span class='rack-status'>&#9654; R"+tRow+"-C"+tCol+"</span>":"")
    +"</div>"
    +"<div class='rack-scroll'><div class='rack-grid' style='grid-template-columns:repeat("+cols+",minmax(68px,1fr))'>";

  (layout.cells||[]).forEach(function(cell){
    if(cell.state==='merged_away')return;
    var hit=cell.row===tRow&&cell.col===tCol;
    var isUnavail=cell.state==='unavailable';
    var cls=hit?'cell highlight':
            cell.state==='has_items'?'cell has-items':
            cell.state==='merged_master'?'cell merged has-items':
            (cell.state==='group_master'||cell.state==='group_slave')?'cell grouped':
            isUnavail?'cell unavail':'cell empty';
    var rs=cell.row_span||1, cs=cell.col_span||1;
    var sp=(rs>1||cs>1)?" style='grid-row:span "+rs+";grid-column:span "+cs+"'":'';
    var click=isUnavail?'':' onclick="showDrawer(\''+uuid+'\','+cell.row+','+cell.col+')"';
    h+="<div class='"+cls+"'"+sp+click+">";
    h+="<span class='cid'>"+esc(cell.cell_id)+"</span>";
    if(cell.short_info)h+="<span class='si'>"+esc(cell.short_info)+"</span>";
    h+="<span class='cnt'>";
    if(hit)                                                h+="<span class='badge bp'>HERE</span>";
    else if(isUnavail)                                     h+="<span class='badge bm'>N/A</span>";
    else if(cell.state==='group_slave'&&cell.group_master) h+="<span class='arrow'>->"+esc(cell.group_master)+"</span>";
    else if((cell.item_count||0)>0)                        h+="<span class='badge bs'>"+cell.item_count+"</span>";
    else                                                   h+="<span class='dim'>Empty</span>";
    h+="</span></div>";
  });

  h+="</div></div>";
  h+="<div class='legend'>"
    +"<span class='leg'><span class='lb' style='background:#ffc107;border-color:#fd7e14'></span>Target</span>"
    +"<span class='leg'><span class='lb' style='background:#cfe2ff;border-color:#9ec5fe'></span>Has items</span>"
    +"<span class='leg'><span class='lb'></span>Empty</span>"
    +"<span class='leg'><span class='lb' style='background:#d1e7dd;border-color:#a3cfbb'></span>Group</span>"
    +"<span class='leg'><span class='lb' style='background:#cfe2ff;border-style:dashed;border-color:#0d6efd'></span>Merged</span>"
    +"<span class='leg'><span class='lb' style='background:#6c757d'></span>Unavail</span>"
    +"</div></div>";

  var el=document.getElementById(rackDivId(uuid));
  if(el)el.innerHTML=h;
}

// ── Drawer popup ──────────────────────────────────────────────────────────
function showDrawer(uuid,row,col){
  var overlay=document.getElementById('drawer-popup');
  document.getElementById('popup-content').innerHTML='<p class="muted">Loading…</p>';
  overlay.style.display='flex';
  fetch(EM+'/api/v1/rack/'+uuid+'/drawer/'+row+'/'+col,{headers:{Authorization:'Bearer '+K}})
  .then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
  .then(function(d){if(!d.success)throw new Error('Error');renderDrawerPopup(d);})
  .catch(function(ex){document.getElementById('popup-content').innerHTML='<div class="alert ae">'+esc(ex.message)+'</div>';});
}
function renderDrawerPopup(d){
  var h="<div style='margin-bottom:12px'><strong style='font-size:1rem'>"+esc(d.cell_id)+"</strong>";
  if(d.short_info)h+=" <span style='color:#6c757d'>— "+esc(d.short_info)+"</span>";
  h+="<div style='font-size:.75rem;color:#6c757d;margin-top:2px'>"+esc(d.rack_name)+"</div></div>";
  if(!d.items||!d.items.length){
    h+="<div class='muted'>No items in this drawer.</div>";
  } else {
    d.items.forEach(function(item){
      h+="<div class='ditem'><div class='dname'>"+esc(item.name)+"</div>";
      if(item.sku)       h+="<div class='dsku'>"+esc(item.sku)+"</div>";
      if(item.short_info)h+="<div class='dinfo'>"+esc(item.short_info)+"</div>";
      if(item.type==='batch_override'){
        h+="<div class='dbatch'><span style='color:#6c757d'>"+esc(item.batch_label||item.batch_uid||'')+"</span>"
          +" &nbsp;<span class='dqty'>"+item.available+"</span><span class='dqtylbl'>/"+item.quantity+" avail</span></div>";
      } else if(item.batches&&item.batches.length){
        item.batches.forEach(function(b){
          h+="<div class='dbatch'><span style='color:#6c757d'>"+esc(b.batch_label||b.batch_uid||'')+"</span>"
            +" &nbsp;<span class='dqty'>"+b.available+"</span><span class='dqtylbl'>/"+b.quantity+" avail</span></div>";
        });
      }
      h+="</div>";
    });
  }
  document.getElementById('popup-content').innerHTML=h;
}
function closePopup(e){
  if(e.target===document.getElementById('drawer-popup'))
    document.getElementById('drawer-popup').style.display='none';
}
)JS";

static const char PAGE_TAIL[] PROGMEM = R"HTML(</script>
</body>
</html>
)HTML";
