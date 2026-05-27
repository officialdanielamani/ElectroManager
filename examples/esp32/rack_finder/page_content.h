#pragma once
/*
 * PROGMEM page content for rack_finder.ino
 *
 * Kept in a separate header so the Arduino sketch preprocessor
 * (which injects #line directives for function-prototype generation)
 * never touches these raw string literals.  If it did, the #line text
 * would end up as literal JavaScript and the browser would throw
 * "SyntaxError: Private field '#line' must be declared in an enclosing class".
 */

#include <pgmspace.h>

static const char PAGE_HEAD[] PROGMEM = R"HTML(<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rack Finder</title>
<style>
*{box-sizing:border-box}
body{font-family:system-ui,sans-serif;margin:0;padding:14px;background:#f8f9fa}
h2{margin:0 0 4px;font-size:1.2rem}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.1);padding:14px;margin-bottom:14px}
.card-header{border-radius:6px 6px 0 0;padding:10px 14px;margin:-14px -14px 12px;color:#fff;font-weight:600}
.row{display:flex;gap:8px;flex-wrap:wrap}
input[type=text]{flex:1;min-width:180px;padding:7px 11px;border:1px solid #ced4da;border-radius:6px;font-size:.95rem}
button{padding:7px 18px;background:#0d6efd;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:.95rem}
button:hover{background:#0b5ed7}
.info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;margin-top:10px}
.info-item{background:#f1f3f5;border-radius:6px;padding:7px 10px}
.lbl{font-size:.68rem;color:#6c757d;text-transform:uppercase;letter-spacing:.04em}
.val{font-size:.92rem;font-weight:600;margin-top:2px;word-break:break-all}
.rack-scroll{overflow-x:auto;padding-bottom:4px}
.rack-grid{display:grid;gap:4px;width:max-content}
.cell{border:2px solid #dee2e6;border-radius:6px;padding:4px 3px;min-width:68px;min-height:62px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:11px}
.cid{font-weight:700;font-size:10px;color:#495057}
.si{font-size:9px;color:#6c757d;margin-top:1px;max-width:64px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cnt{margin-top:3px}
.empty{background:#f8f9fa}
.has-items{background:#cfe2ff;border-color:#9ec5fe}
.merged{background:#cfe2ff;border-style:dashed;border-color:#0d6efd}
.grouped{background:#d1e7dd;border-color:#a3cfbb}
.unavail{background:#6c757d;border-color:#495057;color:#fff}
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
.muted{color:#6c757d;font-size:.82rem}
</style>
</head>
<body>
<div class="card">
<h2>Rack Finder</h2>
<p class="muted" style="margin:3px 0 10px">Enter item name, UUID, batch UID (e.g. ABC-B01), or ISN</p>
<form onsubmit="find(event)">
<div class="row">
<input id="q" type="text" placeholder="Arduino, ABC-B01, ISN-0042..." autocomplete="off" autofocus>
<button type="submit">Find</button>
</div>
</form>
</div>
<div id="info"></div>
<div id="rack"></div>
<script>
)HTML";

static const char PAGE_JS[] PROGMEM = R"JS(
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
function find(e){
  e.preventDefault();
  var q=document.getElementById('q').value.trim();
  if(!q)return;
  document.getElementById('info').innerHTML='<p class="muted" style="padding:8px 0">Searching...</p>';
  document.getElementById('rack').innerHTML='';
  doSearch(q);
}
function doSearch(q){
  fetch(EM+'/api/v1/location/search?q='+encodeURIComponent(q),{headers:{Authorization:'Bearer '+K}})
  .then(function(r){if(!r.ok)throw new Error('Search HTTP '+r.status);return r.json();})
  .then(function(d){
    if(!d.success||!d.results||!d.results.length){
      document.getElementById('info').innerHTML='<div class="alert aw">No items found.</div>';
      return;
    }
    var item=d.results[0];
    var loc=(item.locations||[]).find(function(l){return l.location_type==='rack';});
    renderInfo(item,loc);
    if(!loc)return;
    fetch(EM+'/api/v1/rack/'+loc.rack_uuid+'/layout',{headers:{Authorization:'Bearer '+K}})
    .then(function(r2){if(!r2.ok)throw new Error('Layout HTTP '+r2.status);return r2.json();})
    .then(function(layout){
      if(!layout.success)throw new Error('Bad layout');
      renderRack(layout,loc.drawer_row,loc.drawer_col,loc.rack_color||'#3a86ff');
      fetch('/led?row='+loc.drawer_row+'&col='+loc.drawer_col+'&cols='+layout.cols).catch(function(){});
    })
    .catch(function(ex){document.getElementById('rack').innerHTML='<div class="alert ae">'+esc(ex.message)+'</div>';});
  })
  .catch(function(ex){document.getElementById('info').innerHTML='<div class="alert ae">'+esc(ex.message)+'</div>';});
}
function renderInfo(item,loc){
  var col=loc?loc.rack_color||'#3a86ff':'#6c757d';
  var h="<div class='card'><div class='card-header' style='background:"+esc(col)+"'>"+esc(item.name)+"</div><div class='info-grid'>";
  if(item.sku)        h+="<div class='info-item'><div class='lbl'>SKU</div><div class='val'>"+esc(item.sku)+"</div></div>";
  if(item.short_info) h+="<div class='info-item'><div class='lbl'>Info</div><div class='val'>"+esc(item.short_info)+"</div></div>";
  if(item.isn)        h+="<div class='info-item'><div class='lbl'>ISN</div><div class='val'>"+esc(item.isn)+"</div></div>";
  if(loc){
    if(loc.batch_label)  h+="<div class='info-item'><div class='lbl'>Batch</div><div class='val'>"+esc(loc.batch_label)+"</div></div>";
    if(loc.quantity>0)   h+="<div class='info-item'><div class='lbl'>Total Qty</div><div class='val'>"+loc.quantity+"</div></div>"
                          +"<div class='info-item'><div class='lbl'>Available</div><div class='val'>"+loc.available+"</div></div>";
    h+="<div class='info-item'><div class='lbl'>Rack</div><div class='val'>"+esc(loc.rack_name)+"</div></div>";
    h+="<div class='info-item'><div class='lbl'>Drawer</div><div class='val' style='color:#fd7e14'>"+esc(loc.drawer_cell)+"</div></div>";
  }
  if(item.isn&&item.lent_out) h+="<div class='info-item'><div class='lbl'>Status</div><div class='val' style='color:#dc3545'>Lent out</div></div>";
  h+="</div>";
  if(!loc)h+="<div class='alert aw' style='margin-top:8px'>Item found but has no rack location.</div>";
  h+="</div>";
  document.getElementById('info').innerHTML=h;
}
function renderRack(layout,tRow,tCol,color){
  var cols=layout.cols||1;
  var h="<div class='card'><div class='card-header' style='background:"+esc(color)+"'>"+esc(layout.rack_name)+"</div>"
       +"<div class='rack-scroll'><div class='rack-grid' style='grid-template-columns:repeat("+cols+",minmax(68px,1fr))'>";
  (layout.cells||[]).forEach(function(cell){
    if(cell.state==='merged_away')return;
    var hit=cell.row===tRow&&cell.col===tCol;
    var cls=hit?'cell highlight':
            cell.state==='has_items'?'cell has-items':
            cell.state==='merged_master'?'cell merged has-items':
            (cell.state==='group_master'||cell.state==='group_slave')?'cell grouped':
            cell.state==='unavailable'?'cell unavail':'cell empty';
    var rs=cell.row_span||1, cs=cell.col_span||1;
    var sp=(rs>1||cs>1)?" style='grid-row:span "+rs+";grid-column:span "+cs+"'":'';
    h+="<div class='"+cls+"'"+sp+">";
    h+="<span class='cid'>"+esc(cell.cell_id)+"</span>";
    if(cell.short_info)h+="<span class='si'>"+esc(cell.short_info)+"</span>";
    h+="<span class='cnt'>";
    if(hit)                                           h+="<span class='badge bp'>HERE</span>";
    else if(cell.state==='unavailable')               h+="<span class='badge bm'>N/A</span>";
    else if(cell.state==='group_slave'&&cell.group_master) h+="<span class='arrow'>->"+esc(cell.group_master)+"</span>";
    else if((cell.item_count||0)>0)                   h+="<span class='badge bs'>"+cell.item_count+"</span>";
    else                                              h+="<span class='dim'>Empty</span>";
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
  document.getElementById('rack').innerHTML=h;
}
)JS";

static const char PAGE_TAIL[] PROGMEM = R"HTML(</script>
</body>
</html>
)HTML";
