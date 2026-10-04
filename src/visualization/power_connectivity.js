'use strict';

const UNKNOWN_COLOR = '#8a9698';
const DISTANCE_BINS = [0.5, 2, 5, 10, 25, 50];
const DISTANCE_COLORS = ['#176b73', '#3c8990', '#75a9a1', '#c8b773', '#c38a54', '#b96c43', '#944b39'];
const NETWORK_BINS = [0, 9, 49, 99, 249];
const NETWORK_COLORS = ['#8a9698', '#b4a06c', '#779d8d', '#448984', '#c0804e', '#944b39'];

function passesFilters(metric, filters) {
  const m = metric || {};
  const f = filters || {};
  const within = (value, threshold, maximum) => threshold == null ||
    (value != null && Number.isFinite(Number(value)) &&
      (maximum ? Number(value) <= threshold : Number(value) >= threshold));
  return within(m.subKm, f.maxSubKm, true) &&
    within(m.peerKm, f.maxPeerKm, true) &&
    within(m.peerNetworks, f.minPeerNetworks, false);
}

function colorForMetric(metric, colorBy) {
  const field = colorBy === 'subKm' ? 'subKm' :
    colorBy === 'peerNetworks' ? 'peerNetworks' : 'peerKm';
  const value = metric && metric[field];
  if (value == null || !Number.isFinite(Number(value)) || Number(value) < 0) return UNKNOWN_COLOR;
  const number = Number(value);
  if (field === 'peerNetworks') {
    const index = NETWORK_BINS.findIndex((upper) => number <= upper);
    return NETWORK_COLORS[index < 0 ? NETWORK_COLORS.length - 1 : index];
  }
  const index = DISTANCE_BINS.findIndex((upper) => number <= upper);
  return DISTANCE_COLORS[index < 0 ? DISTANCE_COLORS.length - 1 : index];
}

function bubbleRadius(networkCount, cap) {
  if (networkCount == null || !Number.isFinite(Number(networkCount)) || Number(networkCount) < 0) return 4;
  const safeCap = Number.isFinite(Number(cap)) && Number(cap) > 0 ? Number(cap) : 1;
  return Math.sqrt(16 + 128 * Math.min(Number(networkCount), safeCap) / safeCap);
}

function parseThreshold(raw, requireInteger=false) {
  const text=String(raw == null ? '' : raw).trim();
  if (text==='') return {valid:true,value:null};
  const value=Number(text);
  if (!Number.isFinite(value)||value<0) return {valid:false,value:null,message:'Enter a finite value of 0 or more.'};
  if (requireInteger&&!Number.isInteger(value)) return {valid:false,value:null,message:'Enter a whole number of networks.'};
  return {valid:true,value};
}

function splitAtAntimeridian(site, facility) {
  const delta=facility.lon-site.lon;
  if (Math.abs(delta)<=180) return [[[site.lat,site.lon],[facility.lat,facility.lon]]];
  const adjustedFacilityLon=delta>180?facility.lon-360:facility.lon+360;
  const boundary=delta>180?-180:180;
  const fraction=(boundary-site.lon)/(adjustedFacilityLon-site.lon);
  const crossingLat=site.lat+(facility.lat-site.lat)*fraction;
  const opposite=-boundary;
  return [
    [[site.lat,site.lon],[crossingLat,boundary]],
    [[crossingLat,opposite],[facility.lat,facility.lon]]
  ];
}

function comparisonDomains(payload) {
  const metrics=Object.values((payload&&payload.sites)||{});
  const maxFor=(field)=>{
    const values=metrics.map((metric)=>metric[field]).filter((value)=>
      value!=null&&Number.isFinite(Number(value))&&Number(value)>=0).map(Number);
    return values.length?Math.max(1,...values):1;
  };
  const counts=metrics.map((metric)=>metric.peerNetworks).filter((value)=>
    value!=null&&Number.isFinite(Number(value))&&Number(value)>=0).map(Number).sort((a,b)=>a-b);
  let p95=1;
  if (counts.length) {
    const rank=0.95*(counts.length-1);const lower=Math.floor(rank);const upper=Math.ceil(rank);
    p95=counts[lower]+(counts[upper]-counts[lower])*(rank-lower);
  }
  return {xMax:maxFor('subKm'),yMax:maxFor('peerKm'),networkCap:Math.max(1,p95)};
}

function comparisonPosition(metric, domains) {
  if (!metric||metric.subKm==null||metric.peerKm==null) return null;
  const x=Number(metric.subKm);const y=Number(metric.peerKm);
  if (!Number.isFinite(x)||!Number.isFinite(y)||x<0||y<0) return null;
  return {
    x:Math.log1p(x)/Math.log1p(Math.max(1,domains.xMax)),
    y:1-Math.log1p(y)/Math.log1p(Math.max(1,domains.yMax))
  };
}

function sortVisibleIds(ids, payload, sortKey='peerKm', direction='asc') {
  const fields=new Set(['subKm','peerKm','peerNetworks']);
  const field=fields.has(sortKey)?sortKey:'peerKm';
  const sign=direction==='desc'?-1:1;
  return [...ids].map(String).sort((left,right)=>{
    const leftValue=(payload.sites[left]||{})[field];
    const rightValue=(payload.sites[right]||{})[field];
    const leftKnown=leftValue!=null&&Number.isFinite(Number(leftValue));
    const rightKnown=rightValue!=null&&Number.isFinite(Number(rightValue));
    if (leftKnown!==rightKnown) return leftKnown?-1:1;
    if (leftKnown&&Number(leftValue)!==Number(rightValue)) return (Number(leftValue)-Number(rightValue))*sign;
    return Number(left)-Number(right);
  });
}

function networkMarkerStyle(networkCount, selected=false, cap=1) {
  const unknown=networkCount==null||!Number.isFinite(Number(networkCount))||Number(networkCount)<0;
  return {
    radius:bubbleRadius(unknown?null:Number(networkCount),cap),
    fill:unknown?'#ffffff':'#087e91',
    stroke:selected?'#be6b32':unknown?'#8a9698':'#ffffff',
    hollow:unknown
  };
}

function nearestHit(points, x, y, tolerance=6) {
  return [...points].map((point)=>({point,distance:Math.hypot(point.x-x,point.y-y)}))
    .filter((entry)=>entry.distance<=entry.point.radius+tolerance)
    .sort((a,b)=>a.distance-b.distance||Number(a.point.id)-Number(b.point.id))[0]?.point||null;
}

let mountedState=null;
function mount({sites,payload,elements,onSelect}) {
  destroy();
  const state={
    sites,payload,elements,onSelect,domains:comparisonDomains(payload),
    siteById:new Map(sites.map((site)=>[String(site.id),site])),
    visibleIds:new Set(sites.map((site)=>String(site.id))),selectedId:null,view:'map',colorBy:'peerKm',
    sortKey:'peerKm',sortDirection:'asc',tablePage:0,points:[],cleanup:[],resizeObserver:null,resizeHandler:null
  };
  const canvas=elements.compareCanvas;
  const tooltip=elements.compareContainer.querySelector('#connectivity-plot-tooltip');
  const pageSize=50;
  const formatKm=(value)=>value==null?'Unknown':`${value>0&&value<0.01?'<0.01':Number(value).toFixed(2)} km`;
  const formatCount=(value)=>value==null?'Unknown':Number(value).toLocaleString();
  function handle(target,type,listener,options) {
    target.addEventListener(type,listener,options);
    state.cleanup.push(()=>target.removeEventListener(type,listener,options));
  }
  function setSortButtons() {
    for (const button of elements.tableContainer.querySelectorAll('button[data-sort]')) {
      const key=button.dataset.sort;const th=button.closest('th');
      const active=key===state.sortKey;
      th.setAttribute('aria-sort',active?(state.sortDirection==='asc'?'ascending':'descending'):'none');
      const labels={subKm:'Substation km',peerKm:'Facility km',peerNetworks:'Networks'};
      button.textContent=`${labels[key]}${active?(state.sortDirection==='asc'?' ↑':' ↓'):''}`;
    }
  }
  function renderTable() {
    const ids=sortVisibleIds(state.visibleIds,state.payload,state.sortKey,state.sortDirection);
    const pageCount=Math.max(1,Math.ceil(ids.length/pageSize));
    state.tablePage=Math.min(state.tablePage,pageCount-1);
    const start=state.tablePage*pageSize;
    elements.tableBody.replaceChildren();
    for (const id of ids.slice(start,start+pageSize)) {
      const site=state.siteById.get(id);const metric=state.payload.sites[id]||{};
      const facility=metric.peerId==null?null:state.payload.facilities[String(metric.peerId)];
      const row=document.createElement('tr');
      row.setAttribute('aria-selected',String(String(state.selectedId)===id));
      const nameCell=document.createElement('td');const button=document.createElement('button');
      button.type='button';button.className='table-site-button';button.dataset.siteId=id;
      button.textContent=site?site.name:`Site ${id}`;button.setAttribute('aria-label',`Open details for ${button.textContent}`);
      nameCell.append(button);
      const stateCell=document.createElement('td');stateCell.textContent=site&&site.state?site.state:'Unknown';
      const subCell=document.createElement('td');subCell.textContent=formatKm(metric.subKm);
      const peerCell=document.createElement('td');peerCell.textContent=formatKm(metric.peerKm);
      const networkCell=document.createElement('td');networkCell.textContent=formatCount(metric.peerNetworks);
      const facilityCell=document.createElement('td');facilityCell.textContent=facility
        ?`${facility.name||'Unnamed facility'}${facility.city?` · ${facility.city}`:''}`:'Unknown';
      row.append(nameCell,stateCell,subCell,peerCell,networkCell,facilityCell);
      elements.tableBody.append(row);
    }
    elements.pagination.replaceChildren();
    const previous=document.createElement('button');previous.type='button';previous.dataset.page='previous';
    previous.textContent='Previous';previous.disabled=state.tablePage===0;
    const status=document.createElement('span');status.textContent=`Page ${state.tablePage+1} of ${pageCount} · ${ids.length.toLocaleString()} sites`;
    const next=document.createElement('button');next.type='button';next.dataset.page='next';
    next.textContent='Next';next.disabled=state.tablePage+1>=pageCount;
    elements.pagination.append(previous,status,next);
    setSortButtons();
  }
  function labelDistance(value) {
    if (value===0) return '0';
    if (value<0.01) return '<0.01';
    if (value>=1000) return `${(value/1000).toFixed(value>=10000?0:1)}k`;
    return Number(value.toFixed(value<10?1:0)).toString();
  }
  function renderPlot() {
    if (!canvas) return;
    const bounds=canvas.getBoundingClientRect();
    const width=Math.max(320,bounds.width||elements.compareContainer.clientWidth||640);
    const height=Math.max(250,bounds.height||elements.compareContainer.clientHeight-75||400);
    const dpr=Math.max(1,Number(window.devicePixelRatio)||1);
    canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);
    canvas.style.width=`${width}px`;canvas.style.height=`${height}px`;
    let context;
    try {context=canvas.getContext('2d');} catch (error) {context=null;}
    if (!context) {
      elements.missingNote.textContent='Canvas is unavailable in this browser. Use the table to inspect every matching site.';
      return;
    }
    context.setTransform(dpr,0,0,dpr,0,0);context.clearRect(0,0,width,height);
    const margin={left:82,right:22,top:20,bottom:53};
    const plotWidth=Math.max(20,width-margin.left-margin.right);
    const plotHeight=Math.max(20,height-margin.top-margin.bottom);
    context.font='11px IBM Plex Sans, system-ui, sans-serif';context.fillStyle='#597078';context.strokeStyle='#dce5e3';context.lineWidth=1;
    for (let index=0;index<=4;index++) {
      const fraction=index/4;const x=margin.left+fraction*plotWidth;const y=margin.top+plotHeight-fraction*plotHeight;
      const xValue=Math.expm1(fraction*Math.log1p(state.domains.xMax));
      const yValue=Math.expm1(fraction*Math.log1p(state.domains.yMax));
      context.beginPath();context.moveTo(x,margin.top);context.lineTo(x,margin.top+plotHeight);context.stroke();
      context.beginPath();context.moveTo(margin.left,y);context.lineTo(margin.left+plotWidth,y);context.stroke();
      context.textAlign='center';context.textBaseline='top';context.fillText(labelDistance(xValue),x,margin.top+plotHeight+5);
      context.textAlign='right';context.textBaseline='middle';context.fillText(labelDistance(yValue),margin.left-8,y);
    }
    context.strokeStyle='#78949a';context.beginPath();context.moveTo(margin.left,margin.top);context.lineTo(margin.left,margin.top+plotHeight);context.lineTo(margin.left+plotWidth,margin.top+plotHeight);context.stroke();
    context.fillStyle='#31545e';context.font='600 11px IBM Plex Sans, system-ui, sans-serif';
    context.textAlign='center';context.textBaseline='bottom';context.fillText('Substation distance (km) · log(1 + km)',margin.left+plotWidth/2,height-5);
    context.save();context.translate(14,margin.top+plotHeight/2);context.rotate(-Math.PI/2);context.textAlign='center';context.textBaseline='middle';context.fillText('Nearest IXP facility distance (km) · log(1 + km)',0,0);context.restore();
    context.textAlign='left';context.textBaseline='top';context.font='10px IBM Plex Sans, system-ui, sans-serif';
    context.fillText(`Bubble display cap: P95 = ${Number(state.domains.networkCap.toFixed(1))} registered networks`,margin.left,4);
    state.points=[];let incomplete=0;
    for (const id of state.visibleIds) {
      const metric=state.payload.sites[id]||{};const site=state.siteById.get(id);
      const position=comparisonPosition(metric,state.domains);
      if (!position) {incomplete++;continue;}
      const x=margin.left+position.x*plotWidth;const y=margin.top+position.y*plotHeight;
      const selected=String(state.selectedId)===id;
      const style=networkMarkerStyle(metric.peerNetworks,selected,state.domains.networkCap);
      context.beginPath();context.arc(x,y,style.radius,0,Math.PI*2);
      context.fillStyle=style.fill;
      context.globalAlpha=selected?1:style.hollow?0.85:0.36;
      if (!style.hollow) context.fill();
      context.strokeStyle=style.stroke;context.lineWidth=selected?2.5:style.hollow?1.7:1;
      context.stroke();
      context.globalAlpha=1;
      state.points.push({id,x,y,radius:style.radius,metric,site});
    }
    if (state.points.length===0) {
      context.fillStyle='#597078';context.textAlign='center';context.textBaseline='middle';
      context.fillText('No matching sites have both distance values available.',margin.left+plotWidth/2,margin.top+plotHeight/2);
    }
    elements.missingNote.textContent=incomplete
      ?`${incomplete.toLocaleString()} matching sites lack one or both distance metrics and are not drawn. View them in the table.`:'';
    elements.compareAxes.textContent=`Axes use fixed full-cohort domains (substation 0–${labelDistance(state.domains.xMax)} km; facility 0–${labelDistance(state.domains.yMax)} km) on log(1 + km) scales. Hollow gray bubbles mean network count unavailable; zero is a filled minimum bubble.`;
  }
  function nearestPoint(event) {
    const bounds=canvas.getBoundingClientRect();const x=event.clientX-bounds.left;const y=event.clientY-bounds.top;
    return nearestHit(state.points,x,y,6);
  }
  function showTooltip(event) {
    const point=nearestPoint(event);
    if (!point) {tooltip.hidden=true;return;}
    const metric=point.metric;const facility=metric.peerId==null?null:state.payload.facilities[String(metric.peerId)];
    tooltip.textContent=`${point.site?point.site.name:`Site ${point.id}`} · Substation ${formatKm(metric.subKm)} · Facility ${formatKm(metric.peerKm)} · Networks ${formatCount(metric.peerNetworks)} · ${facility?facility.name:'Nearest facility unknown'}`;
    const parentBounds=elements.compareContainer.getBoundingClientRect();
    tooltip.style.left=`${Math.max(5,Math.min(event.clientX-parentBounds.left+12,parentBounds.width-330))}px`;
    tooltip.style.top=`${Math.max(5,Math.min(event.clientY-parentBounds.top+12,parentBounds.height-55))}px`;
    tooltip.hidden=false;
  }
  handle(canvas,'pointermove',showTooltip);
  handle(canvas,'pointerleave',()=>{tooltip.hidden=true;});
  handle(canvas,'click',(event)=>{const point=nearestPoint(event);if(point&&onSelect)onSelect(point.id);});
  handle(elements.tableBody,'click',(event)=>{
    const button=event.target.closest('button[data-site-id]');
    if(button&&onSelect)onSelect(button.dataset.siteId);
  });
  handle(elements.tableContainer,'click',(event)=>{
    const button=event.target.closest('button[data-sort]');
    if(!button)return;
    if(state.sortKey===button.dataset.sort)state.sortDirection=state.sortDirection==='asc'?'desc':'asc';
    else {state.sortKey=button.dataset.sort;state.sortDirection='asc';}
    state.tablePage=0;renderTable();
  });
  handle(elements.pagination,'click',(event)=>{
    const button=event.target.closest('button[data-page]');if(!button)return;
    state.tablePage+=button.dataset.page==='next'?1:-1;renderTable();
  });
  state.resizeHandler=()=>{if(state.view==='compare')renderPlot();};
  if (typeof ResizeObserver!=='undefined') {
    state.resizeObserver=new ResizeObserver(state.resizeHandler);
    state.resizeObserver.observe(elements.compareContainer);
  } else {
    window.addEventListener('resize',state.resizeHandler);
    state.cleanup.push(()=>window.removeEventListener('resize',state.resizeHandler));
  }
  state.renderPlot=renderPlot;
  state.renderTable=renderTable;
  mountedState=state;
  renderTable();
  return {domains:state.domains};
}

function update({visibleIds,selectedId,view,colorBy}) {
  if (!mountedState) return;
  if (visibleIds) {
    const next=new Set([...visibleIds].map(String));
    if (next.size!==mountedState.visibleIds.size||[...next].some((id)=>!mountedState.visibleIds.has(id))) {
      mountedState.tablePage=0;
    }
    mountedState.visibleIds=next;
  }
  if (selectedId!==undefined) mountedState.selectedId=selectedId;
  if (view) mountedState.view=view;
  if (colorBy) mountedState.colorBy=colorBy;
  if (mountedState.view==='compare') renderMountedPlot();
  if (mountedState.view==='table') renderMountedTable();
}

function renderMountedPlot() {
  if (!mountedState) return;
  mountedState.renderPlot();
}
function renderMountedTable() {
  if (!mountedState) return;
  mountedState.renderTable();
}
function destroy() {
  if (!mountedState) return;
  if (mountedState.resizeObserver) mountedState.resizeObserver.disconnect();
  for (const cleanup of mountedState.cleanup) cleanup();
  mountedState=null;
}

const api = {
  passesFilters,colorForMetric,bubbleRadius,parseThreshold,splitAtAntimeridian,
  comparisonDomains,comparisonPosition,sortVisibleIds,networkMarkerStyle,nearestHit,
  mount,update,destroy
};
if (typeof module !== 'undefined') module.exports = api;
if (typeof window !== 'undefined') window.PowerConnectivity = api;
