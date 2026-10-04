import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const ROOT='/Users/bao/Documents/ChatGPT/DataCenterLocator/infrastructure-inheritance-symbiosis/presentation';
const SKILL='/Users/bao/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations';
const PY='/Users/bao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const BUILD=path.join(ROOT,'.build');
const OUT=path.join(ROOT,'output');
const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
await fs.mkdir(BUILD,{recursive:true});
await fs.mkdir(OUT,{recursive:true});
const C={bg:'#071722',ink:'#EEF6F4',muted:'#9CB2BC',cyan:'#58D8E4',amber:'#F0AA6B',grid:'#294451',soft:'#17303B',green:'#89D9BF'};
const FONT='Arial';
const ppt=Presentation.create({slideSize:{width:1280,height:720}});
const visible=[];
function box(slide,x,y,w,h,fill='none',stroke='none',sw=0,name=''){
 return slide.shapes.add({geometry:'rect',name,position:{left:x,top:y,width:w,height:h},fill,line:{style:'solid',fill:stroke,width:sw}});
}
function line(slide,x1,y1,x2,y2,color=C.grid,sw=2,name=''){
 return slide.shapes.add({geometry:'line',name,position:{left:Math.min(x1,x2),top:Math.min(y1,y2),width:Math.abs(x2-x1),height:Math.abs(y2-y1),horizontalFlip:(x2-x1)*(y2-y1)<0},fill:'none',line:{style:'solid',fill:color,width:sw}});
}
function ellipse(slide,cx,cy,r,fill,stroke='none',sw=0,name=''){
 return slide.shapes.add({geometry:'ellipse',name,position:{left:cx-r,top:cy-r,width:r*2,height:r*2},fill,line:{style:'solid',fill:stroke,width:sw}});
}
function txt(slide,s,x,y,w,h,size=27,color=C.ink,bold=false,align='left',name=''){
 const sh=slide.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{style:'solid',fill:'none',width:0}});
 sh.text=s;
 sh.text.style={typeface:FONT,fontSize:size,bold,color,alignment:align,verticalAlignment:'middle',wrap:'square',autoFit:'none',insets:{top:0,bottom:0,left:0,right:0}};
 visible.push(s);
 return sh;
}
function base(n,title){
 const s=ppt.slides.add();s.background.fill=C.bg;
 txt(s,title,72,42,1100,100,45,C.ink,true,'left',`s${n}-title`);
 txt(s,String(n).padStart(2,'0')+'/07',1168,48,58,36,18,C.muted,false,'right',`s${n}-number`);
 line(s,72,151,1208,151,C.grid,2);
 return s;
}
// 1: Concept illustration from project asset.
{
 const s=ppt.slides.add();s.background.fill=C.bg;
 const image=await fs.readFile(path.join(ROOT,'assets/urban_infrastructure_illustration.png'));
 s.images.add({blob:new Uint8Array(image),contentType:'image/png',alt:'Illustrative urban industrial waterfront with a compact inference facility and network paths',fit:'cover',position:{left:0,top:0,width:1280,height:720}});
 txt(s,'Urban inference can\nbelong near demand',76,176,620,175,57,C.ink,true,'left','s1-title');
 txt(s,'Cheap land pulls facilities outward. Interactive AI pulls compute toward users. Existing urban infrastructure may make that trade worthwhile.',80,420,540,126,27,C.ink,false,'left','s1-copy');
 txt(s,'01/07',1168,49,58,36,18,C.ink,false,'right','s1-number');
}
// 2: Density tradeoff.
{
 const s=base(2,'Density raises costs and creates synergies');
 line(s,640,210,640,590,C.grid,2);
 txt(s,'COST',94,208,490,47,23,C.amber,true);
 txt(s,'Land',94,281,485,51,37,C.ink,true);
 txt(s,'Grid competition',94,360,485,51,37,C.ink,true);
 txt(s,'Permits and community',94,439,500,51,37,C.ink,true);
 txt(s,'SYNERGY',700,208,480,47,23,C.cyan,true);
 txt(s,'Users and networks',700,281,490,51,37,C.ink,true);
 txt(s,'Workforce and heat customers',700,360,500,51,35,C.ink,true);
 txt(s,'Reused industrial sites',700,439,490,51,37,C.ink,true);
 txt(s,'Both sides need site-level proof.',94,608,1080,55,29,C.muted,false);
}
// 3: Explicitly requested editable diagram.
{
 const s=base(3,'One site can connect six systems');
 const center={x:640,y:406};
 const nodes=[
  {x:640,y:232,label:'GRID ASSETS',tx:532,ty:183,w:216},
  {x:301,y:325,label:'CARRIER ROUTES',tx:105,ty:290,w:226},
  {x:976,y:325,label:'INFERENCE USERS',tx:978,ty:288,w:210},
  {x:302,y:532,label:'HEAT CUSTOMERS',tx:107,ty:535,w:230},
  {x:640,y:570,label:'TREATMENT WATER',tx:524,ty:605,w:232},
  {x:978,y:532,label:'REUSED LAND',tx:993,ty:535,w:210}
 ];
 for(const n of nodes) line(s,center.x,center.y,n.x,n.y,C.grid,3);
 for(let i=0;i<nodes.length;i++){
  const n=nodes[i];ellipse(s,n.x,n.y,13,i%2?C.cyan:C.amber,C.bg,2);txt(s,n.label,n.tx,n.ty,n.w,41,22,C.ink,true,i===0||i===4?'center':'left');
 }
 ellipse(s,center.x,center.y,91,C.soft,C.cyan,3);
 txt(s,'URBAN\nINFERENCE\nSITE',552,348,176,116,28,C.ink,true,'center');
 txt(s,'Proximity starts the case. Engineering and contracts complete it.',82,654,1120,39,22,C.muted,false,'center');
}
// 4: Evidence pipeline.
{
 const s=base(4,'The locator turns national records into site evidence');
 txt(s,'190,976',91,212,445,120,91,C.ink,true);
 txt(s,'EPA site records',94,332,430,52,25,C.muted,false);
 line(s,545,305,651,305,C.cyan,4);
 txt(s,'8,479',679,212,460,120,91,C.cyan,true);
 txt(s,'screened candidates',685,332,440,52,25,C.muted,false);
 line(s,92,420,1189,420,C.grid,2);
 txt(s,'INFRASTRUCTURE\nINHERITANCE',97,453,440,96,32,C.ink,true);
 txt(s,'INDUSTRIAL\nSYMBIOSIS',681,453,430,96,32,C.ink,true);
 txt(s,'Two independent axes',98,580,420,46,25,C.cyan,false);
 txt(s,'Local 5 km facility context',685,580,477,46,25,C.cyan,false);
}
// 5: Editable comparison diagram.
{
 const s=base(5,'Two axes make urban tradeoffs visible');
 const p={x:155,y:608,w:625,h:393};
 line(s,p.x,p.y,p.x+p.w,p.y,C.muted,2);line(s,p.x,p.y,p.x,p.y-p.h,C.muted,2);
 const xx=v=>p.x+p.w*v/100;const yy=v=>p.y-p.h*v/100;
 line(s,xx(60),p.y,xx(60),p.y-p.h,C.grid,2);
 line(s,p.x,yy(75),p.x+p.w,yy(75),C.grid,2);
 txt(s,'60',xx(60)-18,p.y+11,40,29,17,C.muted,false,'center');
 txt(s,'75',p.x-44,yy(75)-13,38,26,17,C.muted,false,'right');
 txt(s,'Inheritance',542,635,230,38,20,C.muted,false,'right');
 txt(s,'Symbiosis',83,173,125,35,20,C.muted,false);
 const dots=[
  {name:'Astoria',a:78.46,b:93.21,c:C.cyan,tx:xx(78.46)+17,ty:yy(93.21)-40,w:160},
  {name:'Salem',a:61.19,b:79.99,c:C.cyan,tx:xx(61.19)+15,ty:yy(79.99)+1,w:125},
  {name:'Indian Point',a:89.32,b:68.69,c:C.amber,tx:xx(89.32)-160,ty:yy(68.69)+4,w:155},
  {name:'Davis Street',a:30.27,b:100,c:C.amber,tx:xx(30.27)-62,ty:yy(100)-41,w:180}
 ];
 for(const d of dots){ellipse(s,xx(d.a),yy(d.b),10,d.c,C.bg,1);txt(s,d.name,d.tx,d.ty,d.w,37,19,C.ink,true);}
 txt(s,'Astoria',870,230,304,43,30,C.ink,true);
 txt(s,'78.46  /  93.21',870,278,320,46,34,C.cyan,true);
 txt(s,'Salem',870,370,304,43,30,C.ink,true);
 txt(s,'61.19  /  79.99',870,418,320,46,34,C.cyan,true);
 txt(s,'Connectivity remains a separate exploratory view.',870,523,318,97,22,C.muted,false);
}
// 6: Recommendation / decision output.
{
 const s=base(6,'Astoria is the first due-diligence lead');
 txt(s,'ASTORIA',77,206,676,103,78,C.ink,true);
 txt(s,'Queens, NY  ·  EPA site 40157',84,310,660,47,25,C.muted,false);
 line(s,80,389,1196,389,C.grid,2);
 txt(s,'78.46',87,422,287,82,70,C.cyan,true);
 txt(s,'inheritance',92,509,277,41,24,C.muted,false);
 txt(s,'93.21',429,422,275,82,70,C.cyan,true);
 txt(s,'symbiosis',433,509,268,41,24,C.muted,false);
 txt(s,'37',811,426,175,77,67,C.ink,true);
 txt(s,'selected-manufacturing FRS IDs\n34 coordinate groups · within 5 km',814,503,378,65,21,C.muted,false);
 txt(s,'Food 3  ·  Beverage 4  ·  Paper 6  ·  Chemicals 15  ·  Primary metals 9',84,568,1110,40,21,C.ink,false);
 txt(s,'Potential heat-reuse leads; operations, heat demand/temperature, pipes and partner interest unverified.',84,629,1110,58,21,C.amber,false);
}
// 7: Long-horizon planning premises and a conditional roadmap.
{
 const s=base(7,'Metro proximity can support a 30-year strategy');
 const rows=[
  {y:190,label:'DEMAND ANCHOR',body:'Residents and firms change location gradually. Latency-sensitive demand may stay tied to the metro.',color:C.cyan},
  {y:320,label:'LAND OPTION',body:'Suburban sites near fiber and grid are scarcer than rural acreage. Preserve expansion room early.',color:C.amber},
  {y:450,label:'DURABLE LINKS',body:'Power, carrier and heat links can outlast GPUs. Refresh hardware and reroute work as demand changes.',color:C.green}
 ];
 for(const r of rows){
  txt(s,r.label,82,r.y,245,64,25,r.color,true);
  txt(s,r.body,354,r.y-1,833,84,25,C.ink,false);
 }
 line(s,82,301,1198,301,C.grid,2);
 line(s,82,431,1198,431,C.grid,2);
 line(s,126,621,1154,621,C.grid,3);
 const milestones=[{x:179,text:'2030  VERIFY',c:C.amber},{x:640,text:'2040  PHASE',c:C.cyan},{x:1100,text:'2050  REASSESS',c:C.green}];
 for(const m of milestones){ellipse(s,m.x,621,9,m.c,C.bg,1);txt(s,m.text,m.x-139,643,278,39,21,m.c,true,'center');}
}

// Slide notes from the delivered file, with source citations intact.
const noteMd=await fs.readFile(path.join(ROOT,'speaker_notes.md'),'utf8');
const chunks=noteMd.split(/^## Slide \d+ — .*$/m).slice(1);
if(chunks.length!==7) throw new Error(`expected 7 speaker notes, got ${chunks.length}`);
for(let i=0;i<7;i++) ppt.slides.items[i].speakerNotes.textFrame.setText(chunks[i].trim());
const draft=path.join(BUILD,'candidate.pptx');
await (await PresentationFile.exportPptx(ppt)).save(draft);
for(let i=0;i<7;i++){
 const blob=await ppt.export({slide:ppt.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(BUILD,`slide-${i+1}.png`),new Uint8Array(await blob.arrayBuffer()));
 const lb=await ppt.slides.items[i].export({format:'layout'});
 await fs.writeFile(path.join(BUILD,`slide-${i+1}.layout.json`),await lb.text());
}
const final=path.join(OUT,'presentation-v4.pptx');
const result=await finalizePresentation({
 explicitTotalSlideCount:7,
 workspaceDir:ROOT,
 candidatePath:draft,
 finalPath:final,
 pythonExecutable:PY,
 integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],
 requiredNativeTableOwnerSlides:[],
 requiredNativeChartOwnerSlides:[],
 fontPolicy:{basis:'design',families:[FONT]},
 verifyArtifactToolImport:true,
 receiptPath:path.join(BUILD,'validation-v4.json')
});
console.log('FINAL',final);
console.log('RESULT',JSON.stringify(result));
