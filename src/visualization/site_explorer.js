'use strict';
function sitePassesFilters(site, f) {
  return (!f.formerOnly || site.former) &&
    (site.acreage !== null && site.acreage >= f.minAcreage) &&
    (site.transKv !== null && site.transKv >= f.minTransKv) &&
    (site.transMi !== null && site.transMi <= f.maxTransMi) &&
    (site.subMi !== null && site.subMi <= f.maxSubMi) &&
    (site.inheritance !== null && site.inheritance >= f.minInheritance) &&
    (site.symbiosis !== null && site.symbiosis >= f.minSymbiosis);
}
if (typeof module !== 'undefined') module.exports = {sitePassesFilters};
if (typeof document !== 'undefined') {
  const sites = JSON.parse(document.getElementById('site-data').textContent);
  const ecosystems = JSON.parse(document.getElementById('ecosystem-data').textContent);
  const connectivity = JSON.parse(document.getElementById('connectivity-data').textContent);
  if (connectivity && connectivity.meta) {
    document.getElementById('connectivity-source-note').hidden = false;
    const epaSourceVersion = document.getElementById('epa-source-version');
    epaSourceVersion.textContent = connectivity.meta.epa_source_version || 'EPA source date unknown';
    const peeringRetrievedAt = document.getElementById('peering-retrieved-at');
    const retrievedDate = new Date(connectivity.meta.retrieved_at);
    peeringRetrievedAt.textContent = Number.isNaN(retrievedDate.getTime())
      ? 'Unknown'
      : retrievedDate.toISOString().slice(0, 10);
    document.getElementById('peering-snapshot-id').textContent = connectivity.meta.snapshot_id;
  }
  const controls = {
    formerOnly: document.getElementById('former-only'),
    minAcreage: document.getElementById('min-acreage'),
    minTransKv: document.getElementById('min-transmission-kv'),
    maxTransMi: document.getElementById('max-transmission-mi'),
    maxSubMi: document.getElementById('max-substation-mi'),
    minInheritance: document.getElementById('min-inheritance'),
    minSymbiosis: document.getElementById('min-symbiosis')
  };
  const defaults = {formerOnly:false,minAcreage:50,minTransKv:115,maxTransMi:3,maxSubMi:5,minInheritance:0,minSymbiosis:0};
  const panel = document.getElementById('detail-panel');
  let selectedId = null;
  let mode = connectivity ? 'connectivity' : 'legacy';
  let visibleIds = new Set();
  let legacyRedraw = () => {};
  let connectivityMap = null;
  let connectivitySiteLayer = null;
  let connectivityFacilityLayer = null;
  let connectivityLinkLayer = null;
  let connectivityFilters = {maxSubKm:null,maxPeerKm:null,minPeerNetworks:null};
  let connectivityColorBy = 'peerKm';
  let connectivityView = 'map';
  let connectivityTimer = null;
  const connectivityModule = typeof window !== 'undefined' ? window.PowerConnectivity : null;
  const connectivityControls = {
    maxSubKm: document.getElementById('max-substation-km'),
    maxPeerKm: document.getElementById('max-peering-km'),
    minPeerNetworks: document.getElementById('min-peering-networks')
  };
  let localMap = null;
  let localLayer = null;
  let infrastructureRequest = 0;
  const infrastructureSources = [
    {kind:'Transmission',url:'https://services1.arcgis.com/Hp6G80Pky0om7QvQ/ArcGIS/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0',fields:'OBJECTID_1,VOLTAGE,VOLT_CLASS,STATUS',color:'#c65b39'},
    {kind:'Substation',url:'https://services1.arcgis.com/7DRakJXKPEhwv0fM/ArcGIS/rest/services/Electric_Substations/FeatureServer/0',fields:'FID,NAME,TYPE,STATUS',color:'#a74664'},
    {kind:'Rail',url:'https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_North_American_Rail_Network_Lines/FeatureServer/0',fields:'OBJECTID,RROWNER1',color:'#596170'}
  ];
  function fmt(value, digits=1) {return value === null || value === undefined ? 'Unknown' : Number(value).toFixed(digits);}
  function rows(elementId, entries) {
    const parent=document.getElementById(elementId);parent.replaceChildren();
    for (const [label,value] of entries) {
      const row=document.createElement('div');row.className='evidence-row';
      const left=document.createElement('span');left.textContent=label;
      const right=document.createElement('span');right.textContent=value;
      row.append(left,right);parent.append(row);
    }
  }
  function inheritanceReason(site) {
    const reasons=[];
    if(site.formerMw!==null && site.powerComponent>0) reasons.push(`Matched retired generator nameplate ${fmt(site.formerMw,0)} MW (${site.powerConfidence} confidence); historical capacity, not available grid power.`);
    else if(site.formerMw!==null) reasons.push('A retired generator is nearby, but site identity evidence does not support legacy credit.');
    else reasons.push('No corroborated retired EIA generator match; former capacity is unknown.');
    reasons.push(`${fmt(site.transKv,0)} kV reported transmission ${fmt(site.transMi)} mi away; substation ${fmt(site.subMi)} mi away.`);
    reasons.push(`${fmt(site.acreage)} reported acres. Component scores: power ${fmt(site.powerComponent,0)}, line ${fmt(site.transComponent,0)}, substation ${fmt(site.subComponent,0)}, land ${fmt(site.landComponent,0)}, transport ${fmt(site.transportComponent,0)}.`);
    return reasons.join(' ');
  }
  function symbiosisReason(site) {
    const reasons=[`${fmt(site.industrial5,0)} selected manufacturing facilities within 5 km; nearest listed facility ${fmt(site.sinkKm)} km away. These are potential heat sinks, not confirmed offtakers.`];
    if(site.wwtp5===0) reasons.push('No CWNS treatment plant within 5 km.');
    else if(site.waterFlow5===null) reasons.push(`${fmt(site.wwtp5,0)} treatment plants within 5 km, but none report design flow; the flow proxy is unknown.`);
    else reasons.push(`${fmt(site.wwtp5,0)} treatment plants within 5 km; known design-flow sum ${fmt(site.waterFlow5,2)} MGD from ${fmt(site.wwtpKnownFlow5,0)} reporting plants. Design flow is not actual available water.`);
    reasons.push(`Component scores: industrial density ${fmt(site.industrialComponent,0)}, heat proximity ${fmt(site.heatComponent,0)}, water opportunity ${fmt(site.waterComponent,0)}.`);
    return reasons.join(' ');
  }
  async function loadInfrastructure(site, requestId) {
    const status=document.getElementById('local-layer-status');
    status.textContent='Loading HIFLD grid and FRA/BTS rail geometry…';
    const results=await Promise.allSettled(infrastructureSources.map(async source=>{
      const params=new URLSearchParams({
        where:'1=1',geometry:JSON.stringify({x:site.lon,y:site.lat,spatialReference:{wkid:4326}}),
        geometryType:'esriGeometryPoint',inSR:'4326',spatialRel:'esriSpatialRelIntersects',
        distance:'5000',units:'esriSRUnit_Meter',outFields:source.fields,
        returnGeometry:'true',outSR:'4326',f:'geojson',resultRecordCount:'2000'
      });
      const response=await fetch(`${source.url}/query?${params.toString()}`);
      if(!response.ok) throw new Error(`${response.status}`);
      const data=await response.json();
      if(data.error || !Array.isArray(data.features)) throw new Error('invalid service response');
      return {source,data};
    }));
    if(requestId!==infrastructureRequest || site.id!==selectedId) return;
    let failed=0;let loaded=0;let truncated=0;
    for(const result of results) {
      if(result.status!=='fulfilled'){failed++;continue;}
      const {source,data}=result.value;
      loaded+=data.features.length;
      if(data.exceededTransferLimit || data.features.length===2000) truncated++;
      L.geoJSON(data,{
        style:()=>({color:source.color,weight:source.kind==='Rail'?2:2.6,opacity:0.85}),
        pointToLayer:(feature,latlng)=>L.circleMarker(latlng,{radius:7,color:'#fff',weight:1,fillColor:source.color,fillOpacity:0.95}),
        onEachFeature:(feature,layer)=>{
          const properties=feature.properties||{};
          const name=source.kind==='Substation'?(properties.NAME||'Unnamed substation'):
            source.kind==='Rail'?(properties.RROWNER1||'Rail segment'):
              `${properties.VOLTAGE||properties.VOLT_CLASS||'Unknown voltage'} transmission line`;
          layer.bindTooltip(document.createTextNode(`${source.kind}: ${name}`));
          layer.on('click',()=>{
            document.getElementById('local-facility-detail').textContent=`${source.kind}: ${name} · mapped source geometry · ${source.url} · feature ${properties.OBJECTID_1||properties.OBJECTID||properties.FID||'ID unknown'}. This layer may differ from the EPA nearest-distance asset.`;
          });
        }
      }).addTo(localLayer);
    }
    status.textContent=`Mapped source geometry: ${loaded} grid/rail features${failed?`; ${failed} live layers unavailable`:''}${truncated?`; ${truncated} layers hit the service limit`:''}. HIFLD and FRA/BTS geometries are independent of EPA nearest-distance fields.`;
  }
  function showLocal(site) {
    const detail=document.getElementById('local-facility-detail');
    detail.textContent='Select a facility marker for details.';
    document.getElementById('local-distance-facts').textContent=`EPA-reported nearest distances: transmission ${fmt(site.transMi)} mi, substation ${fmt(site.subMi)} mi, rail ${fmt(site.railMi)} mi. EPA does not identify those specific assets by coordinate. Mapped HIFLD/FRA features use separate source geometry and may not be the EPA nearest asset.`;
    if(typeof L==='undefined') return;
    if(!localMap) {
      localMap=L.map('local-map',{zoomControl:true,preferCanvas:true});
      L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}',{
        attribution:'Map tiles: <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map">USGS The National Map</a>',maxZoom:16
      }).addTo(localMap);
      localLayer=L.layerGroup().addTo(localMap);
    }
    localLayer.clearLayers();
    localMap.setView([site.lat,site.lon],11);
    L.circle([site.lat,site.lon],{radius:5000,color:'#143445',weight:1.5,fillColor:'#087e91',fillOpacity:0.06}).addTo(localLayer);
    L.circleMarker([site.lat,site.lon],{radius:8,color:'#fff',weight:2,fillColor:'#143445',fillOpacity:1})
      .bindTooltip('★ Candidate data center').addTo(localLayer);
    const nearby=ecosystems[String(site.id)]||{i:[],w:[]};
    for(const [kind,facilities] of [['i',nearby.i],['w',nearby.w]]) {
      for(const facility of facilities) {
        L.circleMarker([facility.lat,facility.lon],{radius:kind==='i'?5:6,color:'#fff',weight:1,fillColor:kind==='i'?'#be6b32':'#2b72a8',fillOpacity:0.9})
          .bindTooltip(document.createTextNode(facility.name))
          .on('click',()=>{detail.textContent=`${facility.name} · ${facility.type} · ${fmt(facility.km,3)} km · NAICS ${facility.naics||'not applicable/unknown'} · source ID ${facility.id}`;})
          .addTo(localLayer);
      }
    }
    infrastructureRequest++;
    loadInfrastructure(site,infrastructureRequest);
    setTimeout(()=>{localMap.invalidateSize();localMap.setView([site.lat,site.lon],11);},0);
  }
  function showSite(site) {
    selectedId = site.id;
    const connected = Boolean(connectivity && connectivity.sites[String(site.id)]);
    const connectedMetric = connected ? connectivity.sites[String(site.id)] : null;
    const connectedFacility = connectedMetric && connectedMetric.peerId !== null
      ? connectivity.facilities[String(connectedMetric.peerId)] : null;
    document.getElementById('connectivity-detail').hidden = mode !== 'connectivity' || !connected;
    document.getElementById('legacy-background').open = mode === 'legacy';
    if (connected) {
      const kmText = (value) => value == null ? 'Unknown' :
        `${value > 0 && value < 0.01 ? '<0.01' : Number(value).toFixed(2)} km`;
      document.getElementById('detail-substation-km').textContent = kmText(connectedMetric.subKm);
      document.getElementById('detail-peering-km').textContent = kmText(connectedMetric.peerKm);
      document.getElementById('detail-peering-networks').textContent = connectedMetric.peerNetworks == null
        ? 'Unknown' : Number(connectedMetric.peerNetworks).toLocaleString();
      document.getElementById('detail-facility-name').textContent = connectedFacility
        ? `${connectedFacility.name || 'Unnamed facility'} · ${[connectedFacility.city,connectedFacility.state].filter(Boolean).join(', ')}`
        : 'No eligible interconnection facility was matched.';
      const updated = connectedFacility && connectedFacility.sourceUpdatedAt
        ? connectedFacility.sourceUpdatedAt : 'Unknown';
      document.getElementById('detail-facility-updated').textContent =
        `PeeringDB record last updated: ${updated} · snapshot retrieved: ${connectivity.meta.retrieved_at}`;
      const facilityLink = document.getElementById('facility-link');
      const safeUrl = connectedFacility && /^https:\/\/www\.peeringdb\.com\/fac\/\d+$/.test(connectedFacility.url || '')
        ? connectedFacility.url : null;
      facilityLink.hidden = !safeUrl;
      if (safeUrl) {
        facilityLink.href = safeUrl;
        facilityLink.textContent = `PeeringDB facility #${connectedFacility.id}`;
      } else {
        facilityLink.removeAttribute('href');
        facilityLink.textContent = '';
      }
    }
    document.getElementById('detail-id').textContent = site.id;
    document.getElementById('detail-name').textContent = site.name;
    document.getElementById('detail-place').textContent = [site.county,site.state].filter(Boolean).join(', ');
    document.getElementById('detail-inheritance').textContent = fmt(site.inheritance,0);
    document.getElementById('detail-symbiosis').textContent = fmt(site.symbiosis,0);
    document.getElementById('detail-summary').textContent = `${fmt(site.acreage)} acres · ${fmt(site.transKv,0)} kV transmission at ${fmt(site.transMi)} mi · substation ${fmt(site.subMi)} mi away.`;
    rows('inheritance-rows',[
      ['Former power evidence',site.former?`${site.powerName||'Retired plant'} · ${fmt(site.powerDistanceKm,2)} km match`:
        site.nearbyPowerRecord?`Nearby ${site.powerName||'EIA record'} · identity unconfirmed`:'No nearby retired EIA match'],
      ['Historical nameplate',site.formerMw===null?'Unknown':`${fmt(site.formerMw,0)} MW · ${site.powerFuel||'fuel unknown'} · retired ${fmt(site.retirementYear,0)}`],
      ['Transmission',`${fmt(site.transKv,0)} kV · ${fmt(site.transMi)} mi · source-reported`],
      ['Substation',`${fmt(site.subMi)} mi · voltage raw ${fmt(site.subVoltageRaw,0)} (unit unverified)`],
      ['Land',`${fmt(site.acreage)} acres · source-reported`],
      ['Transport',`Rail ${fmt(site.railMi)} mi · road ${fmt(site.roadMi)} mi`]
    ]);
    rows('symbiosis-rows',[
      ['Industry within 5 km',`${fmt(site.industrial5,0)} selected facilities`],
      ['Sector counts',`Food ${fmt(site.food5,0)} · beverage ${fmt(site.beverage5,0)} · paper ${fmt(site.paper5,0)} · chemical ${fmt(site.chemical5,0)} · metal ${fmt(site.metal5,0)}`],
      ['Nearest potential sink',site.sinkName?`${site.sinkName} · ${fmt(site.sinkKm)} km · NAICS ${site.sinkNaics||'unknown'}`:'Unknown'],
      ['Nearest WWTP',site.wwtpName?`${site.wwtpName} · ${fmt(site.wwtpKm)} km`:'None reported nearby'],
      ['Nearest WWTP design flow',site.wwtpDesignFlow===null?'Unknown':`${fmt(site.wwtpDesignFlow,2)} MGD · design capacity`],
      ['5 km flow proxy',site.waterFlow5===null?'Unknown (missing CWNS design flow)':`${fmt(site.waterFlow5,2)} MGD · known design flow only`]
    ]);
    document.getElementById('inheritance-reason').textContent=inheritanceReason(site);
    document.getElementById('symbiosis-reason').textContent=symbiosisReason(site);
    document.getElementById('quality-note').textContent=`Data quality ${fmt(site.quality,0)}/100 · ${fmt(site.missingCount,0)} expected fields missing${site.qualityMissing?` (${site.qualityMissing})`:''}. Distances and facility categories are screening proxies; parcel, interconnection, heat demand and reuse rights need verification.`;
    panel.hidden = false;
    if (mode === 'legacy') showLocal(site);
    if (mode === 'connectivity') drawConnectivityMap();
  }
  document.getElementById('close-detail').addEventListener('click',()=>{
    panel.hidden=true;selectedId=null;
    if (mode === 'connectivity') drawConnectivityMap();
  });
  let legacyMap = null;
  let legacyGroup = null;
  let legacyRenderer = null;
  let connectivityRenderer = null;
  const siteById = new Map(sites.map((site) => [String(site.id), site]));
  function legacyFilters() {
    const read = (key) => {
      const raw=controls[key].value;const value=Number(raw);
      return Number.isFinite(value)&&raw!=='' ? Math.max(0,value) : defaults[key];
    };
    return {formerOnly:controls.formerOnly.checked,minAcreage:read('minAcreage'),minTransKv:read('minTransKv'),maxTransMi:read('maxTransMi'),maxSubMi:read('maxSubMi'),minInheritance:read('minInheritance'),minSymbiosis:read('minSymbiosis')};
  }
  legacyRedraw = function() {
    const f=legacyFilters();let count=0;let selectedVisible=false;
    if (legacyGroup) legacyGroup.clearLayers();
    for (const site of sites) {
      if (!sitePassesFilters(site,f)) continue;
      count++;
      if (site.id===selectedId) selectedVisible=true;
      if (!legacyGroup) continue;
      const high=site.inheritance>=60&&site.symbiosis>=75;
      const color=high?'#be6b32':site.former?'#087e91':'#607d83';
      L.circleMarker([site.lat,site.lon],{renderer:legacyRenderer,radius:high?5:4,color:'#fff',weight:0.6,fillColor:color,fillOpacity:0.78})
        .on('click',()=>showSite(site)).addTo(legacyGroup);
    }
    if (selectedId!==null&&!selectedVisible) {
      selectedId=null;panel.hidden=true;
      document.getElementById('connectivity-detail').hidden=true;
    }
    document.getElementById('visible-count').textContent=count.toLocaleString();
  };
  function validateFilter(input, key) {
    return connectivityModule.parseThreshold(input.value,key==='minPeerNetworks');
  }
  function updateConnectivity() {
    if (!connectivity || !connectivityModule) return;
    visibleIds=new Set();let missing=0;
    for (const [id,metric] of Object.entries(connectivity.sites)) {
      if (!connectivityModule.passesFilters(metric,connectivityFilters)) continue;
      visibleIds.add(String(id));
      if (metric.subKm==null||metric.peerKm==null||metric.peerNetworks==null) missing++;
    }
    document.getElementById('connectivity-visible-count').textContent=visibleIds.size.toLocaleString();
    document.getElementById('connectivity-missing-note').textContent=
      `${missing.toLocaleString()} of ${visibleIds.size.toLocaleString()} matching sites have at least one unknown metric.`;
    if (selectedId!==null&&!visibleIds.has(String(selectedId))) {
      selectedId=null;panel.hidden=true;
      document.getElementById('connectivity-detail').hidden=true;
    }
    drawConnectivityMap();
  }
  function initConnectivityMap() {
    if (connectivityMap||typeof L==='undefined') return;
    try {
      connectivityMap=L.map('connectivity-map',{preferCanvas:true,zoomControl:true}).setView([39,-96],4);
      const tiles=L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}',{
        attribution:'Map tiles: <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map">USGS The National Map</a>',maxZoom:16
      }).addTo(connectivityMap);
      tiles.on('tileerror',()=>{document.getElementById('connectivity-map-error').hidden=false;});
      connectivitySiteLayer=L.layerGroup().addTo(connectivityMap);
      connectivityFacilityLayer=L.layerGroup().addTo(connectivityMap);
      connectivityLinkLayer=L.layerGroup().addTo(connectivityMap);
      connectivityRenderer=L.canvas({padding:0.5});
    } catch (error) {
      connectivityMap=null;connectivitySiteLayer=null;connectivityFacilityLayer=null;connectivityLinkLayer=null;
      document.getElementById('connectivity-map-error').hidden=false;
    }
  }
  function mapLegend() {
    const isNetworks=connectivityColorBy==='peerNetworks';
    const labels=isNetworks?['0','1–9','10–49','50–99','100–249','250+']:
      ['0–0.5 km','>0.5–2 km','>2–5 km','>5–10 km','>10–25 km','>25–50 km','>50 km'];
    const representatives=isNetworks?[0,1,10,50,100,250]:[0,0.50001,2.00001,5.00001,10.00001,25.00001,50.00001];
    const legend=document.getElementById('connectivity-map-legend');legend.replaceChildren();
    const title=document.createElement('strong');
    title.textContent=isNetworks?'Registered networks at nearest facility':
      connectivityColorBy==='subKm'?'EPA nearest substation distance':'Nearest listed IXP facility distance';
    const swatches=document.createElement('div');swatches.className='legend-swatches';
    labels.forEach((label,index)=>{
      const entry=document.createElement('span');entry.className='legend-swatch';
      const dot=document.createElement('i');
      dot.style.backgroundColor=connectivityModule.colorForMetric(
        isNetworks?{peerNetworks:representatives[index]}:
          connectivityColorBy==='subKm'?{subKm:representatives[index]}:{peerKm:representatives[index]},
        connectivityColorBy);
      entry.append(dot,document.createTextNode(label));swatches.append(entry);
    });
    const unknown=document.createElement('span');unknown.className='legend-swatch';
    const unknownDot=document.createElement('i');unknownDot.style.backgroundColor='#8a9698';
    unknown.append(unknownDot,document.createTextNode('Unknown'));
    legend.append(title,swatches,unknown);
  }
  function drawConnectivityMap() {
    if (connectivity&&connectivityModule&&connectivityModule.update) {
      connectivityModule.update({visibleIds,selectedId,view:connectivityView,colorBy:connectivityColorBy});
    }
    if (!connectivity||typeof L==='undefined') return;
    initConnectivityMap();
    if (!connectivityMap) return;
    connectivitySiteLayer.clearLayers();connectivityFacilityLayer.clearLayers();connectivityLinkLayer.clearLayers();
    mapLegend();
    for (const id of visibleIds) {
      const site=siteById.get(id);const metric=connectivity.sites[id];
      if (!site||!metric||!Number.isFinite(site.lat)||!Number.isFinite(site.lon)) continue;
      const selected=String(selectedId)===id;
      const color=connectivityModule.colorForMetric(metric,connectivityColorBy);
      const missing=metric[connectivityColorBy]==null;
      L.circleMarker([site.lat,site.lon],{
        renderer:connectivityRenderer,radius:4.5,color:selected?'#be6b32':missing?'#8a9698':'#fff',
        weight:selected?2.5:missing?1.8:0.8,fillColor:missing?'#d4dcdb':color,fillOpacity:0.9
      }).on('click',()=>showSite(site)).addTo(connectivitySiteLayer);
    }
    let selectedSite=null;let selectedMetric=null;let selectedFacility=null;
    if (selectedId!==null&&visibleIds.has(String(selectedId))) {
      selectedSite=siteById.get(String(selectedId));selectedMetric=connectivity.sites[String(selectedId)];
      selectedFacility=selectedMetric&&selectedMetric.peerId!==null
        ?connectivity.facilities[String(selectedMetric.peerId)]:null;
    }
    if (document.getElementById('show-matched-facilities').checked) {
      const drawn=new Set();
      for (const id of visibleIds) {
        const metric=connectivity.sites[id];
        if (!metric||metric.peerId===null||drawn.has(String(metric.peerId))) continue;
        const facility=connectivity.facilities[String(metric.peerId)];
        if (!facility) continue;
        drawn.add(String(metric.peerId));
        const marker=L.marker([facility.lat,facility.lon],{
          icon:L.divIcon({className:'facility-map-icon',html:'◆',iconSize:[18,18],iconAnchor:[9,9]})
        });
        const label=document.createElement('span');
        label.textContent=`${facility.name||'Unnamed facility'} · ${[facility.city,facility.state].filter(Boolean).join(', ')}`;
        marker.bindTooltip(label).addTo(connectivityFacilityLayer);
      }
    }
    if (selectedSite&&selectedFacility) {
      const lines=connectivityModule.splitAtAntimeridian(selectedSite,selectedFacility);
      L.polyline(lines,{color:'#be6b32',weight:2,dashArray:'5 6',opacity:0.9}).addTo(connectivityLinkLayer);
    }
    if (connectivityMap) setTimeout(()=>connectivityMap.invalidateSize(),0);
  }
  function setConnectivityView(view) {
    connectivityView=view;
    document.getElementById('connectivity-map-panel').hidden=view!=='map';
    document.getElementById('connectivity-compare-container').hidden=view!=='compare';
    document.getElementById('connectivity-table-container').hidden=view!=='table';
    for (const button of document.querySelectorAll('.connectivity-view-tab')) {
      button.setAttribute('aria-pressed',String(button.dataset.view===view));
    }
    drawConnectivityMap();
  }
  function setMode(nextMode) {
    if (nextMode==='connectivity'&&!connectivity) return;
    mode=nextMode;
    const app=document.querySelector('.app');
    app.classList.toggle('mode-connectivity',mode==='connectivity');
    document.getElementById('connectivity-workspace').hidden=mode!=='connectivity';
    document.getElementById('connectivity-detail').hidden=mode!=='connectivity'||selectedId===null;
    document.getElementById('legacy-background').open=mode==='legacy';
    document.getElementById('connectivity-view-button').setAttribute('aria-pressed',String(mode==='connectivity'));
    document.getElementById('legacy-view-button').setAttribute('aria-pressed',String(mode==='legacy'));
    if (mode==='connectivity') {
      updateConnectivity();
      setTimeout(()=>{if(typeof L!=='undefined'&&connectivityMap)connectivityMap.invalidateSize();},0);
    } else {
      legacyRedraw();
      setTimeout(()=>{if(typeof L!=='undefined'&&legacyMap)legacyMap.invalidateSize();},0);
    }
  }
  document.getElementById('header-count').textContent = sites.length.toLocaleString();
  if (typeof L === 'undefined') {
    document.getElementById('map-error').hidden=false;
    document.getElementById('connectivity-map-error').hidden=false;
  } else {
    try {
      legacyMap=L.map('map',{preferCanvas:true,zoomControl:true}).setView([39,-96],4);
      L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}',{
        attribution:'Map tiles: <a href="https://www.usgs.gov/programs/national-geospatial-program/national-map">USGS The National Map</a>',maxZoom:16
      }).addTo(legacyMap);
      legacyGroup=L.layerGroup().addTo(legacyMap);
      legacyRenderer=L.canvas({padding:0.5});
    } catch (error) {
      document.getElementById('map-error').hidden=false;
    }
  }
  let legacyTimer;
  for (const control of Object.values(controls)) control.addEventListener('input',()=>{
    clearTimeout(legacyTimer);legacyTimer=setTimeout(legacyRedraw,120);
  });
  document.getElementById('reset-filters').addEventListener('click',()=>{
    for (const [key,value] of Object.entries(defaults)) {
      if(key==='formerOnly') controls[key].checked=value; else controls[key].value=value;
    }
    legacyRedraw();
  });
  for (const [key,input] of Object.entries(connectivityControls)) {
    input.addEventListener('input',()=>{
      const result=validateFilter(input,key);
      const error=document.getElementById(`${input.id}-error`);
      input.setAttribute('aria-invalid',String(!result.valid));
      error.textContent=result.valid?'':result.message;
      if (!result.valid) return;
      connectivityFilters[key]=result.value;
      clearTimeout(connectivityTimer);connectivityTimer=setTimeout(updateConnectivity,120);
    });
  }
  document.getElementById('reset-connectivity-filters').addEventListener('click',()=>{
    for (const [key,input] of Object.entries(connectivityControls)) {
      input.value='';input.setAttribute('aria-invalid','false');
      document.getElementById(`${input.id}-error`).textContent='';
      connectivityFilters[key]=null;
    }
    updateConnectivity();
  });
  document.getElementById('show-matched-facilities').addEventListener('change',drawConnectivityMap);
  document.getElementById('connectivity-color-by').addEventListener('change',(event)=>{
    connectivityColorBy=event.target.value;drawConnectivityMap();
  });
  for (const button of document.querySelectorAll('.connectivity-view-tab')) {
    button.addEventListener('click',()=>setConnectivityView(button.dataset.view));
  }
  document.getElementById('connectivity-view-button').addEventListener('click',()=>setMode('connectivity'));
  document.getElementById('legacy-view-button').addEventListener('click',()=>setMode('legacy'));
  if (connectivity&&connectivityModule&&connectivityModule.mount) {
    connectivityModule.mount({
      sites,payload:connectivity,
      elements:{
        compareContainer:document.getElementById('connectivity-compare-container'),
        tableContainer:document.getElementById('connectivity-table-container'),
        compareCanvas:document.getElementById('connectivity-compare-canvas'),
        compareAxes:document.getElementById('connectivity-compare-axes'),
        tableBody:document.getElementById('connectivity-table-body'),
        pagination:document.getElementById('connectivity-pagination'),
        missingNote:document.getElementById('connectivity-plot-missing')
      },
      onSelect:(id)=>{const site=siteById.get(String(id));if(site)showSite(site);}
    });
  }
  legacyRedraw();
  setConnectivityView('map');
  if (connectivity) setMode('connectivity');
  else setMode('legacy');
}
