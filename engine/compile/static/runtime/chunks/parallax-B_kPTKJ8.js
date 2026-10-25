import{g as F,a as te,c as $,s as z,j as ae}from"../index.js";import{r as re,t as oe,p as ne,u as se,P as ie,b as le}from"./pointer-ZLS-kQ3E.js";import{p as ce,l as ue,r as me,W as fe,P as de,i as pe,c as he}from"./worldText-C7zi4fQu.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */const ve=`#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`,Te=l=>`#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
#define PAD ${de.toFixed(3)}
#define PTR_MODE ${l?l.mode==="light"?2:1:0}
#define PTR_LAYER ${l?.layer==="picture"?2:1}
#define RELIEF 0.08
${fe}
${l?ie:""}
${l?`vec3 ptrBase(vec3 c, vec3 bl) { return ${le(l.base)}; }`:""}
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
  vec3 outside = ptrBase(col, ${l?.base==="blur"?"textureLod(img, q, 3.5).rgb":"col"});
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
}`,Ae={dolly:l=>[0,-.01+.02*l,1.04+.1*l],pan:l=>[-.03+.06*l,0,1.08],orbit:l=>[Math.sin((l-.5)*2.4)*.035,Math.cos((l-.5)*2.4)*.012-.01,1.07],rise:l=>[0,.03-.06*l,1.06+.03*l]},xe={behind:0,sky:1,surface:2};function ye(l){const[T,f,e,u,g,_,x,P,r]=l,s=g*r-_*P,B=-(u*r-_*x),U=u*P-g*x,y=T*s+f*B+e*U;if(Math.abs(y)<1e-12)return null;const A=1/y;return[s*A,-(f*r-e*P)*A,(f*_-e*g)*A,B*A,(T*r-e*x)*A,-(T*_-e*u)*A,U*A,-(T*P-f*x)*A,(T*g-f*u)*A]}const Be=async(l,T)=>{const f=document.createElement("canvas");T.visual.appendChild(f);const e=f.getContext("webgl2",{antialias:!1,preserveDrawingBuffer:!0});if(!e)throw new Error("no webgl2");const u=re(T.section,l),g=[],_=(t,o)=>{const n=e.createShader(t);if(e.shaderSource(n,o),e.compileShader(n),!e.getShaderParameter(n,e.COMPILE_STATUS))throw new Error(e.getShaderInfoLog(n)||"shader");return n},x=e.createProgram();e.attachShader(x,_(e.VERTEX_SHADER,ve)),e.attachShader(x,_(e.FRAGMENT_SHADER,Te(u))),e.linkProgram(x),e.useProgram(x),e.bindBuffer(e.ARRAY_BUFFER,e.createBuffer()),e.bufferData(e.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),e.STATIC_DRAW);const P=e.getAttribLocation(x,"p");e.enableVertexAttribArray(P),e.vertexAttribPointer(P,2,e.FLOAT,!1,0,0);const r=t=>e.getUniformLocation(x,t),s={imgA:r("imgA"),depA:r("depA"),imgB:r("imgB"),depB:r("depB"),scaleA:r("scaleA"),scaleB:r("scaleB"),camA:r("camA"),camB:r("camB"),mixAB:r("mixAB"),strength:r("strength"),focusA:r("focusA"),focusB:r("focusB"),grade:r("grade"),mskA:r("mskA"),mskB:r("mskB"),uText:r("uText"),on:r("uOnT[0]"),inn:r("uInT[0]"),kind:r("uKindT[0]"),m:r("uMT[0]"),box:r("uBoxT[0]"),cell:r("uCellT[0]"),A:r("uAT[0]"),B:r("uBT[0]"),hasLayA:r("hasLayA"),hasLayB:r("hasLayB"),ptrC:r("uPtrC"),ptrR:r("uPtrR"),ptrAsp:r("uPtrAsp")};e.uniform1i(s.imgA,0),e.uniform1i(s.depA,1),e.uniform1i(s.imgB,2),e.uniform1i(s.depB,3),e.uniform1i(s.mskA,4),e.uniform1i(s.mskB,5),e.uniform1i(s.uText,6),e.uniform1i(r("layA"),7),e.uniform1i(r("layB"),8),u&&(e.uniform1f(r("uPtrSoft"),u.softness),e.uniform1f(r("uPtrStr"),u.strength),e.uniform3fv(r("uPtrCol"),u.color));function B(t){const o=e.createTexture();return e.bindTexture(e.TEXTURE_2D,o),t?e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,t):e.texImage2D(e.TEXTURE_2D,0,e.RGBA,1,1,0,e.RGBA,e.UNSIGNED_BYTE,new Uint8Array([255,255,255,255])),e.generateMipmap(e.TEXTURE_2D),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR_MIPMAP_LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),o}let U=0;await Promise.all(l.chapters.map(async(t,o)=>{const n=u?.layer==="picture"?u.layers[o]:null,[a,i,p,c]=await Promise.all([F(t.image),F(t.depth),t.world?.mask?F(t.world.mask):Promise.resolve(null),n?F(n).catch(()=>null):Promise.resolve(null)]);g[o]={img:B(a),dep:B(i),msk:B(p),lay:c?B(c):null,w:a.naturalWidth,h:a.naturalHeight,focus:t.focus??.5,move:t.move||l.move||"dolly"},T.progress(++U/l.chapters.length)}));const y=[],A=!te&&l.chapters.some(t=>t.world);let C=null;const d=A?ce(T.section):null;if(A&&d){try{await document.fonts.ready,await document.fonts.load(`${d.weight} 64px ${d.family}`),await document.fonts.load(`italic ${d.weight} 64px ${d.family}`)}catch{}const t=[...T.section.querySelectorAll(".ss-step")];l.chapters.forEach((n,a)=>{const i=n.world,p=T.data.steps[n.step??a];if(!i||!p||!i.m)return;const c=ue(p.title,d,{size:i.box[2],hMax:.3*i.plane[1],lines:i.style.lines??void 0,caps:i.style.caps,track:i.style.track,weight:i.style.weight??d.weight,align:i.style.align});y.push({ch:a,w:i,lay:c,cell:{x:0,y:0,w:0,h:0},enabled:!0,el:t[n.step??a]||null})});const o=(n,a)=>{const i=n.w.style,p=n.w.tone??.5,c=i.color==="ink"?d.ink:i.color==="paper"?d.paper:i.color==="accent"?d.accent:/^#|^rgb/i.test(i.color)?i.color:pe(p,d);return!a||i.color!=="auto"?c:he(d.emColor,p,d)};if(y.length){const n=me(y.map(a=>({layout:a.lay,px:Math.min(2600,Math.max(256,a.lay.wPlane*2200)),colors:i=>o(a,i),weight:a.w.style.weight??d.weight,track:a.w.style.track,caps:a.w.style.caps,align:a.w.style.align,st:d})));y.forEach((a,i)=>{a.cell=n.cells[i]}),C=n.canvas}}const H=e.createTexture();C&&(e.activeTexture(e.TEXTURE6),e.bindTexture(e.TEXTURE_2D,H),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!0),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,C),e.generateMipmap(e.TEXTURE_2D),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR_MIPMAP_LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1));const j=new Map(y.map(t=>[t.ch,t])),m={on:new Float32Array(2),inn:new Float32Array(2),kind:new Int32Array(2),m:new Float32Array(18),box:new Float32Array(8),cell:new Float32Array(8),A:new Float32Array(8),B:new Float32Array(8)};let X=1,q=1;const G=t=>{const o=X/q,n=t.w/t.h;return o>n?[1,o/n]:[n/o,1]};function J(){for(const t of y){const o=g[t.ch];if(!o)continue;const[n,a]=G(o),i=.5/(n*1.12),p=.5/(a*1.12),c=ye(t.w.m);let b=!!c;if(c){const[v,w]=[t.w.box[0],t.w.box[1]],L=t.lay.wPlane/2,h=t.lay.hPlane/2;for(const[D,k]of[[v-L,w-h],[v+L,w-h],[v+L,w+h],[v-L,w+h]]){const K=c[6]*D+c[7]*k+c[8],Z=(c[0]*D+c[1]*k+c[2])/K,ee=(c[3]*D+c[4]*k+c[5])/K;(Math.abs(Z-.5)>i-.01||Math.abs(ee-.5)>p-.01)&&(b=!1)}}const E=f.getBoundingClientRect().width*(n>1?n:1);t.lay.fs*E<22&&(b=!1),t.enabled=b,t.el?.classList.toggle("ss-world-on",b)}}function W(){const t=f.getBoundingClientRect(),o=Math.min(devicePixelRatio||1,2);X=f.width=Math.max(1,Math.round(t.width*o)),q=f.height=Math.max(1,Math.round(t.height*o)),e.viewport(0,0,X,q),J(),N="",M?.dirty()}const M=u?oe(f,{rest:u.rest,radius:u.radius},ne()):null,Y=B(null);let N="";W(),(window.__ssWorld||={}).live=y;const O=l.chapters.map((t,o)=>t.step??o);let I=0,S=0;const R=(t,o)=>{e.activeTexture(e.TEXTURE0+t),e.bindTexture(e.TEXTURE_2D,o)},Q=t=>z(.04,.22,t)*(1-z(.9,1,t));function V(t,o,n){const a=j.get(o);if(m.on[t]=0,!a||!a.enabled)return;const i=Q(n);if(i<.002)return;m.on[t]=i,m.inn[t]=$(n/.35),m.kind[t]=xe[a.w.kind],m.m.set([a.w.m[0],a.w.m[3],a.w.m[6],a.w.m[1],a.w.m[4],a.w.m[7],a.w.m[2],a.w.m[5],a.w.m[8]],t*9),m.box.set([a.w.box[0],a.w.box[1],a.lay.wPlane,a.lay.hPlane],t*4),m.cell.set([a.cell.x,a.cell.y,a.cell.w,a.cell.h],t*4);const p=Math.log2(Math.max(1,1+(a.w.blur??(a.w.kind==="surface"?.8:0))*(f.width/1920)*.7));m.A.set([a.w.depth??0,a.w.soft??.04,a.w.style.haze,p],t*4),m.B.set([a.w.style.fog,a.w.style.wear,a.w.style.relief,a.w.tone??.5],t*4)}return{resize:W,update(t){M?.update(t.t);let o=0;for(let h=0;h<O.length;h++)(t.steps[O[h]]??0)>0&&(o=h);o=Math.min(o,l.chapters.length-1);const n=$(t.steps[O[o]]??0),a=Math.max(0,o-1),i=o>0?z(0,.18,n):1,p=g[a],c=g[o];if(!c&&!p)return;I+=(t.mx-I)*.05,S+=(t.my-S)*.05;const b=(h,D)=>{const k=Ae[g[h]?.move||"dolly"](ae($(D)));return[k[0]+I*.02,k[1]+S*.012,k[2]]},E=c&&i>=1?c:p||c,v=c||p,w=E===c?o:a,L=`${w}|${o}|${n.toFixed(4)}|${i.toFixed(4)}|${I.toFixed(4)}|${S.toFixed(4)}|${M?M.pos.join(","):""}`;if(L!==N){if(N=L,R(0,E.img),R(1,E.dep),R(2,v.img),R(3,v.dep),R(4,E.msk),R(5,v.msk),R(7,E.lay||Y),R(8,v.lay||Y),e.uniform1f(s.hasLayA,E.lay?1:0),e.uniform1f(s.hasLayB,v.lay?1:0),M&&u){const h=se(M.pos,u.radius,f.getBoundingClientRect(),null);e.uniform2fv(s.ptrC,h.centre),e.uniform1f(s.ptrR,h.radius),e.uniform1f(s.ptrAsp,h.aspect)}e.uniform2fv(s.scaleA,G(E)),e.uniform2fv(s.scaleB,G(v)),e.uniform3fv(s.camA,b(w,w===o?n:1)),e.uniform3fv(s.camB,b(o,n)),e.uniform1f(s.mixAB,E===v?0:i),e.uniform1f(s.focusA,E.focus),e.uniform1f(s.focusB,v.focus),e.uniform1f(s.strength,l.strength??1),e.uniform1f(s.grade,l.vignette??.35),y.length&&(V(0,w,w===o?n:1),V(1,o,n),e.uniform1fv(s.on,m.on),e.uniform1fv(s.inn,m.inn),e.uniform1iv(s.kind,m.kind),e.uniformMatrix3fv(s.m,!1,m.m),e.uniform4fv(s.box,m.box),e.uniform4fv(s.cell,m.cell),e.uniform4fv(s.A,m.A),e.uniform4fv(s.B,m.B)),e.drawArrays(e.TRIANGLE_STRIP,0,4)}}}};export{Be as default};
