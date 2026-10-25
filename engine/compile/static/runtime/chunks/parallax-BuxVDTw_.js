const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["./live-DEjm-mk6.js","../index.js"])))=>i.map(i=>d[i]);
import{a as ee,_ as se,g as F,c as H,s as K,j as le}from"../index.js";import{r as ce,t as ue,p as me,u as fe,P as de,b as pe}from"./pointer-ZLS-kQ3E.js";import{p as ve,l as he,r as Te,W as Ae,P as xe,i as ye,c as Ee}from"./worldText-C7zi4fQu.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */const ge=`#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`,we=(n,v="")=>`#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
#define PAD ${xe.toFixed(3)}
#define PTR_MODE ${n?n.mode==="light"?2:1:0}
#define PTR_LAYER ${n?.layer==="picture"?2:1}
#define RELIEF 0.08
${Ae}
${n?de:""}
${v?`#define LIVE 1
#define LV_VIEWS 2
${v}`:""}
${n?`vec3 ptrBase(vec3 c, vec3 bl) { return ${pe(n.base)}; }`:""}
uniform sampler2D imgA, depA, imgB, depB, mskA, mskB, uText, layA, layB;
uniform float hasLayA, hasLayB;
uniform vec2 scaleA, scaleB;      // cover-fit uv scale per image
uniform vec3 camA, camB;          // x, y offset and zoom per chapter
uniform float mixAB, strength, focusA, focusB;
uniform float grade;              // 0..1 vignette amount
// the title of each view's chapter, if it has one (type in the world)
uniform float uOnT[2], uInT[2];
uniform int uKindT[2];
uniform mat3 uMT[2];
uniform vec4 uBoxT[2], uCellT[2], uAT[2], uBT[2];

vec3 sampleView(sampler2D img, sampler2D dep, sampler2D msk, sampler2D lay, float hasLay, vec2 sc, vec3 cam, float focus, int v){
  vec2 c = (uv - .5) / (sc * cam.z) + .5;
  vec2 dir = cam.xy * strength;
  // solve uv' + (d(uv') - focus) * dir = c by fixed-point iteration: near pixels move further
  vec2 q = c;
  for (int i = 0; i < 6; i++) {
    float d = texture(dep, q).r;
    q = c - (d - focus) * dir;
  }
  q = clamp(q, vec2(.001), vec2(.999));
  vec3 col = texture(img, q).rgb;
#ifdef LIVE
  float la = 0.0;
  col = liveApply(img, q, col, v, la);
#endif
  if (uOnT[v] > 0.002) {
    int kind = uKindT[v];
    // behind / sky: where the title's own depth puts it on screen; surface: on the photo's surface point itself
    vec2 qt = kind == 2 ? q : clamp(c - (uAT[v].x - focus) * dir, vec2(.001), vec2(.999));
    vec3 pq = uMT[v] * vec3(qt, 1.0);
    vec2 pl = pq.xy / pq.z;
    vec2 lc = (pl - uBoxT[v].xy) / (uBoxT[v].zw * (1.0 + 2.0 * PAD)) + 0.5;
    vec2 dx = dFdx(lc), dy = dFdy(lc);
    vec2 inb = step(vec2(0.0), lc) * step(lc, vec2(1.0));
    float bl = exp2(uAT[v].w);
    vec4 t = textureGrad(uText, uCellT[v].xy + clamp(lc, 0.0, 1.0) * uCellT[v].zw, dx * uCellT[v].zw * bl, dy * uCellT[v].zw * bl);
    float cov = t.a * inb.x * inb.y * step(0.0, pq.z);
    if (cov > 0.002) {
      vec3 ink = t.rgb / max(t.a, 1e-4);
      vec3 near = textureLod(img, q, 1.6).rgb, locl = textureLod(img, q, 3.6).rgb, air = textureLod(img, q, 6.5).rgb;
      if (kind != 2) col = worldBehindSky(col, ink, cov, col, near, locl, air, texture(dep, q).r, uAT[v], uBT[v], uOnT[v], uInT[v], kind, uv.y);
      else col = worldSurface(col, ink, cov, col, near, locl, pl, texture(msk, q).r, uBT[v], uOnT[v], uInT[v], lc.x);
    }
  }
#if PTR_MODE == 1
  // the lens: the second layer through a soft circle under the pointer (on screen), sampled through the same depth warp as
  // the photo so it lines up whatever the camera does; outside it, the photo in the base look
  float lm = ptrLens(uv) * uPtrStr;
  vec3 outside = ptrBase(col, ${n?.base==="blur"?"textureLod(img, q, 3.5).rgb":"col"});
#if PTR_LAYER == 2
  col = hasLay > 0.5 ? ptrRim(mix(outside, texture(lay, q).rgb, lm), uv) : outside;
#else
  col = ptrRim(mix(outside, col, lm), uv);
#endif
#elif PTR_MODE == 2
  // the torch: the depth map's gradient is the surface's slope, in picture heights (x scaled by the photo's aspect)
  // (read a little blurred, from a smaller mip, so the light follows the big shapes and not the depth map's steps)
  vec2 ts = 4.0 / vec2(textureSize(dep, 0));
  float gx = textureLod(dep, q + vec2(ts.x, 0.0), 1.5).r - textureLod(dep, q - vec2(ts.x, 0.0), 1.5).r;
  float gy = textureLod(dep, q + vec2(0.0, ts.y), 1.5).r - textureLod(dep, q - vec2(0.0, ts.y), 1.5).r;
  vec2 grad = vec2(gx / (2.0 * ts.x) / (sc.x / sc.y * uPtrAsp), gy / (2.0 * ts.y)) * RELIEF;
  col = ptrLight(col, uv, texture(dep, q).r, grad);
#endif
  return col;
}
void main(){
  vec3 a = sampleView(imgA, depA, mskA, layA, hasLayA, scaleA, camA, focusA, 0);
  vec3 b = mixAB > 0.001 ? sampleView(imgB, depB, mskB, layB, hasLayB, scaleB, camB, focusB, 1) : a;
  vec3 c = mix(a, b, mixAB);
  float v = smoothstep(1.15, .35, length((uv - .5) * vec2(1.1, 1.)));
  o = vec4(c * mix(1., v, grade), 1.);
}`,Re={dolly:n=>[0,-.01+.02*n,1.04+.1*n],pan:n=>[-.03+.06*n,0,1.08],orbit:n=>[Math.sin((n-.5)*2.4)*.035,Math.cos((n-.5)*2.4)*.012-.01,1.07],rise:n=>[0,.03-.06*n,1.06+.03*n]},Be={behind:0,sky:1,surface:2};function _e(n){const[v,p,e,u,m,y,R,b,E]=n,S=m*E-y*b,r=-(u*E-y*R),s=u*b-m*R,_=v*S+p*r+e*s;if(Math.abs(_)<1e-12)return null;const g=1/_;return[S*g,-(p*E-e*b)*g,(p*y-e*m)*g,r*g,(v*E-e*R)*g,-(v*y-e*u)*g,s*g,-(v*b-p*R)*g,(v*m-p*u)*g]}const ke=async(n,v)=>{const p=document.createElement("canvas");v.visual.appendChild(p);const e=p.getContext("webgl2",{antialias:!1,preserveDrawingBuffer:!0});if(!e)throw new Error("no webgl2");const u=ce(v.section,n),m=!ee&&n.chapters.some(t=>Array.isArray(t.live)&&t.live.length)?await se(()=>import("./live-DEjm-mk6.js"),__vite__mapDeps([0,1]),import.meta.url):null,y=m?n.chapters.map(t=>m.readLive(t.live)):[],R=[],b=(t,o)=>{const i=e.createShader(t);if(e.shaderSource(i,o),e.compileShader(i),!e.getShaderParameter(i,e.COMPILE_STATUS))throw new Error(e.getShaderInfoLog(i)||"shader");return i},E=e.createProgram();e.attachShader(E,b(e.VERTEX_SHADER,ge)),e.attachShader(E,b(e.FRAGMENT_SHADER,we(u,m?.LIVE_GLSL))),e.linkProgram(E),e.useProgram(E),e.bindBuffer(e.ARRAY_BUFFER,e.createBuffer()),e.bufferData(e.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),e.STATIC_DRAW);const S=e.getAttribLocation(E,"p");e.enableVertexAttribArray(S),e.vertexAttribPointer(S,2,e.FLOAT,!1,0,0);const r=t=>e.getUniformLocation(E,t),s={imgA:r("imgA"),depA:r("depA"),imgB:r("imgB"),depB:r("depB"),scaleA:r("scaleA"),scaleB:r("scaleB"),camA:r("camA"),camB:r("camB"),mixAB:r("mixAB"),strength:r("strength"),focusA:r("focusA"),focusB:r("focusB"),grade:r("grade"),mskA:r("mskA"),mskB:r("mskB"),uText:r("uText"),on:r("uOnT[0]"),inn:r("uInT[0]"),kind:r("uKindT[0]"),m:r("uMT[0]"),box:r("uBoxT[0]"),cell:r("uCellT[0]"),A:r("uAT[0]"),B:r("uBT[0]"),hasLayA:r("hasLayA"),hasLayB:r("hasLayB"),ptrC:r("uPtrC"),ptrR:r("uPtrR"),ptrAsp:r("uPtrAsp")};e.uniform1i(s.imgA,0),e.uniform1i(s.depA,1),e.uniform1i(s.imgB,2),e.uniform1i(s.depB,3),e.uniform1i(s.mskA,4),e.uniform1i(s.mskB,5),e.uniform1i(s.uText,6),e.uniform1i(r("layA"),7),e.uniform1i(r("layB"),8),u&&(e.uniform1f(r("uPtrSoft"),u.softness),e.uniform1f(r("uPtrStr"),u.strength),e.uniform3fv(r("uPtrCol"),u.color));function _(t){const o=e.createTexture();return e.bindTexture(e.TEXTURE_2D,o),t?e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,t):e.texImage2D(e.TEXTURE_2D,0,e.RGBA,1,1,0,e.RGBA,e.UNSIGNED_BYTE,new Uint8Array([255,255,255,255])),e.generateMipmap(e.TEXTURE_2D),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR_MIPMAP_LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),o}let g=0;await Promise.all(n.chapters.map(async(t,o)=>{const i=u?.layer==="picture"?u.layers[o]:null,[a,l,T,c]=await Promise.all([F(t.image),F(t.depth),t.world?.mask?F(t.world.mask):Promise.resolve(null),i?F(i).catch(()=>null):Promise.resolve(null)]);R[o]={img:_(a),dep:_(l),msk:_(T),lay:c?_(c):null,w:a.naturalWidth,h:a.naturalHeight,focus:t.focus??.5,move:t.move||n.move||"dolly"},v.progress(++g/n.chapters.length)}));const P=[],j=!ee&&n.chapters.some(t=>t.world);let $=null;const h=j?ve(v.section):null;if(j&&h){try{await document.fonts.ready,await document.fonts.load(`${h.weight} 64px ${h.family}`),await document.fonts.load(`italic ${h.weight} 64px ${h.family}`)}catch{}const t=[...v.section.querySelectorAll(".ss-step")];n.chapters.forEach((i,a)=>{const l=i.world,T=v.data.steps[i.step??a];if(!l||!T||!l.m)return;const c=he(T.title,h,{size:l.box[2],hMax:.3*l.plane[1],lines:l.style.lines??void 0,caps:l.style.caps,track:l.style.track,weight:l.style.weight??h.weight,align:l.style.align});P.push({ch:a,w:l,lay:c,cell:{x:0,y:0,w:0,h:0},enabled:!0,el:t[i.step??a]||null})});const o=(i,a)=>{const l=i.w.style,T=i.w.tone??.5,c=l.color==="ink"?h.ink:l.color==="paper"?h.paper:l.color==="accent"?h.accent:/^#|^rgb/i.test(l.color)?l.color:ye(T,h);return!a||l.color!=="auto"?c:Ee(h.emColor,T,h)};if(P.length){const i=Te(P.map(a=>({layout:a.lay,px:Math.min(2600,Math.max(256,a.lay.wPlane*2200)),colors:l=>o(a,l),weight:a.w.style.weight??h.weight,track:a.w.style.track,caps:a.w.style.caps,align:a.w.style.align,st:h})));P.forEach((a,l)=>{a.cell=i.cells[l]}),$=i.canvas}}const te=e.createTexture();$&&(e.activeTexture(e.TEXTURE6),e.bindTexture(e.TEXTURE_2D,te),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!0),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,$),e.generateMipmap(e.TEXTURE_2D),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR_MIPMAP_LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1));const ae=new Map(P.map(t=>[t.ch,t])),f={on:new Float32Array(2),inn:new Float32Array(2),kind:new Int32Array(2),m:new Float32Array(18),box:new Float32Array(8),cell:new Float32Array(8),A:new Float32Array(8),B:new Float32Array(8)};let G=1,N=1;const O=t=>{const o=G/N,i=t.w/t.h;return o>i?[1,o/i]:[i/o,1]};function oe(){for(const t of P){const o=R[t.ch];if(!o)continue;const[i,a]=O(o),l=.5/(i*1.12),T=.5/(a*1.12),c=_e(t.w.m);let k=!!c;if(c){const[A,x]=[t.w.box[0],t.w.box[1]],M=t.lay.wPlane/2,D=t.lay.hPlane/2;for(const[d,C]of[[A-M,x-D],[A+M,x-D],[A+M,x+D],[A-M,x+D]]){const U=c[6]*d+c[7]*C+c[8],ie=(c[0]*d+c[1]*C+c[2])/U,ne=(c[3]*d+c[4]*C+c[5])/U;(Math.abs(ie-.5)>l-.01||Math.abs(ne-.5)>T-.01)&&(k=!1)}}const w=p.getBoundingClientRect().width*(i>1?i:1);t.lay.fs*w<22&&(k=!1),t.enabled=k,t.el?.classList.toggle("ss-world-on",k)}}function J(){const t=p.getBoundingClientRect(),o=Math.min(devicePixelRatio||1,2);G=p.width=Math.max(1,Math.round(t.width*o)),N=p.height=Math.max(1,Math.round(t.height*o)),e.viewport(0,0,G,N),oe(),z="",I?.dirty()}const I=u?ue(p,{rest:u.rest,radius:u.radius},me()):null,V=_(null);let W=[];const B=m?m.emptyPack(2):null;let Q="";if(m){const t=y.flat(),o=await m.maskAtlas(t.map(a=>a.mask),F);let i=0;W=y.map(a=>a.map(()=>o.cells[i++])),e.activeTexture(e.TEXTURE9),e.bindTexture(e.TEXTURE_2D,o.canvas?_(o.canvas):V),e.uniform1i(r("uLvMask"),9)}let z="";J(),(window.__ssWorld||={}).live=P;const Y=n.chapters.map((t,o)=>t.step??o);let X=0,q=0;const L=(t,o)=>{e.activeTexture(e.TEXTURE0+t),e.bindTexture(e.TEXTURE_2D,o)},re=t=>K(.04,.22,t)*(1-K(.9,1,t));function Z(t,o,i){const a=ae.get(o);if(f.on[t]=0,!a||!a.enabled)return;const l=re(i);if(l<.002)return;f.on[t]=l,f.inn[t]=H(i/.35),f.kind[t]=Be[a.w.kind],f.m.set([a.w.m[0],a.w.m[3],a.w.m[6],a.w.m[1],a.w.m[4],a.w.m[7],a.w.m[2],a.w.m[5],a.w.m[8]],t*9),f.box.set([a.w.box[0],a.w.box[1],a.lay.wPlane,a.lay.hPlane],t*4),f.cell.set([a.cell.x,a.cell.y,a.cell.w,a.cell.h],t*4);const T=Math.log2(Math.max(1,1+(a.w.blur??(a.w.kind==="surface"?.8:0))*(p.width/1920)*.7));f.A.set([a.w.depth??0,a.w.soft??.04,a.w.style.haze,T],t*4),f.B.set([a.w.style.fog,a.w.style.wear,a.w.style.relief,a.w.tone??.5],t*4)}return{resize:J,update(t){I?.update(t.t);let o=0;for(let d=0;d<Y.length;d++)(t.steps[Y[d]]??0)>0&&(o=d);o=Math.min(o,n.chapters.length-1);const i=H(t.steps[Y[o]]??0),a=Math.max(0,o-1),l=o>0?K(0,.18,i):1,T=R[a],c=R[o];if(!c&&!T)return;X+=(t.mx-X)*.05,q+=(t.my-q)*.05;const k=(d,C)=>{const U=Re[R[d]?.move||"dolly"](le(H(C)));return[U[0]+X*.02,U[1]+q*.012,U[2]]},w=c&&l>=1?c:T||c,A=c||T,x=w===c?o:a;let M="";if(B&&m&&(y[x]?.length||y[o]?.length)){const d=p.getBoundingClientRect();d.bottom>0&&d.top<innerHeight&&!document.hidden&&(M=String(Math.floor(t.t*m.FPS)))}const D=`${x}|${o}|${i.toFixed(4)}|${l.toFixed(4)}|${X.toFixed(4)}|${q.toFixed(4)}|${I?I.pos.join(","):""}|${M}`;if(D!==z){if(z=D,L(0,w.img),L(1,w.dep),L(2,A.img),L(3,A.dep),L(4,w.msk),L(5,A.msk),L(7,w.lay||V),L(8,A.lay||V),e.uniform1f(s.hasLayA,w.lay?1:0),e.uniform1f(s.hasLayB,A.lay?1:0),B&&m&&(Q!==`${x}|${o}`&&(Q=`${x}|${o}`,m.packView(B,0,y[x]||[],W[x]),m.packView(B,1,y[o]||[],W[o]),e.uniform4fv(r("uLvBox"),B.box),e.uniform4fv(r("uLvA"),B.a),e.uniform4fv(r("uLvB"),B.b),e.uniform4fv(r("uLvC"),B.c),e.uniform4fv(r("uLvM"),B.m),e.uniform4fv(r("uLvP"),B.p)),e.uniform1f(r("uLvT"),t.t),e.uniform1f(r("uLvAsp"),A.w/A.h)),I&&u){const d=fe(I.pos,u.radius,p.getBoundingClientRect(),null);e.uniform2fv(s.ptrC,d.centre),e.uniform1f(s.ptrR,d.radius),e.uniform1f(s.ptrAsp,d.aspect)}e.uniform2fv(s.scaleA,O(w)),e.uniform2fv(s.scaleB,O(A)),e.uniform3fv(s.camA,k(x,x===o?i:1)),e.uniform3fv(s.camB,k(o,i)),e.uniform1f(s.mixAB,w===A?0:l),e.uniform1f(s.focusA,w.focus),e.uniform1f(s.focusB,A.focus),e.uniform1f(s.strength,n.strength??1),e.uniform1f(s.grade,n.vignette??.35),P.length&&(Z(0,x,x===o?i:1),Z(1,o,i),e.uniform1fv(s.on,f.on),e.uniform1fv(s.inn,f.inn),e.uniform1iv(s.kind,f.kind),e.uniformMatrix3fv(s.m,!1,f.m),e.uniform4fv(s.box,f.box),e.uniform4fv(s.cell,f.cell),e.uniform4fv(s.A,f.A),e.uniform4fv(s.B,f.B)),e.drawArrays(e.TRIANGLE_STRIP,0,4)}}}};export{ke as default};
