import{i as tt,g as I,c as A,h as et,s as N,b as lt,a as ft}from"../index.js";import{r as mt,t as ut,p as pt,u as dt,P as ht,b as gt}from"./pointer-ZLS-kQ3E.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */function G(o,a){if(!a.length)return 0;if(o<=a[0].a)return a[0].t;for(let c=0;c<a.length;c++){const l=a[c];if(o<=l.b||c+1>=a.length)return l.t;const u=a[c+1];if(o<u.a)return l.t+(u.t-l.t)*N(l.b,u.a,o)}return a[a.length-1].t}function Rt(o,a,c){if(a>=1)return 1;const l=Math.max(c,.001);return N(o,o+l,a*(1+l))}function At(o,a,c,l){if(a<=0||a>=1)return 0;const u=Math.max(c,.001),p=(a*(1+u)-u*.5-o)/Math.max(l,.001);return Math.exp(-p*p)}function ot(o,a,c,l,u){const T=a/Math.max(c,1),p=l/Math.max(u,1),E=Math.max(.05,o.zoom);let f,m;o.fit==="cover"==T>p?(f=1,m=T/p):(f=p/T,m=1),f*=E,m*=E;let d,y;if(o.fit==="contain"&&E<=1.0001)d=f/2+(1-f)*o.position[0],y=m/2+(1-m)*o.position[1];else{const t=(o.position[0]-.5)*f,i=(o.position[1]-.5)*m;d=.5-A(t,-(f-1)/2,(f-1)/2)*(f>=1?1:0),y=.5-A(i,-(m-1)/2,(m-1)/2)*(m>=1?1:0),f<1&&(d=f/2+(1-f)*o.position[0]),m<1&&(y=m/2+(1-m)*o.position[1])}return{sx:1/f,sy:1/m,ox:d,oy:y}}const xt=`#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`;function Tt(o){return`#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
#define PTR_MODE ${o?o.mode==="light"?2:1:0}
#define PTR_LAYER ${o?.layer==="picture"?2:1}
uniform sampler2D imgA, imgB, mapT, layT;
uniform vec4 fitT;            // sx, sy, ox, oy: picture uv = (uv - o) * s + .5
uniform vec3 cam;             // drift x, y and zoom
uniform float f;              // reveal progress of stage B over A, 0-1
uniform int kind;             // 0 none, 1 fade, 2 wipe, 3 map
uniform vec2 dir;             // wipe direction
uniform float soft;
uniform vec3 frontCol; uniform float frontW, frontS, frontAll, hasFront;
uniform vec3 bg;              // the stage's background, outside a contained picture
uniform float ptrOn, hasLay;
${o?ht:""}
${o?`vec3 ptrBase(vec3 c, vec3 bl) { return ${gt(o.base)}; }`:""}
void main(){
  vec2 q = (uv - fitT.zw) * fitT.xy / cam.z + .5 + cam.xy;
  float inside = step(0., q.x) * step(q.x, 1.) * step(0., q.y) * step(q.y, 1.);
  vec2 qc = clamp(q, vec2(.0005), vec2(.9995));
  vec3 A = texture(imgA, qc).rgb, B = texture(imgB, qc).rgb;
  float s = 0.;
  if (kind == 2) { vec2 d = normalize(dir); float lo = min(0., d.x) + min(0., d.y), hi = max(0., d.x) + max(0., d.y); s = (dot(qc, d) - lo) / max(hi - lo, 1e-4); }
  else if (kind == 3) s = texture(mapT, qc).r;
  float w = max(soft, 1e-3);
  float m = kind == 1 ? f : (f >= 1. ? 1. : smoothstep(s, s + w, f * (1. + w)));
  if (kind == 0) m = 0.;
  vec3 col = mix(A, B, m);
  if (hasFront > .5 && kind >= 2 && f > 0. && f < 1.) {
    float x = f * (1. + w) - w * .5;
    float dd = (x - s) / max(frontW, 1e-3);
    float band = exp(-dd * dd);
    // all: across the subject (not the stage's own background around it); change: only where the picture changes
    float subject = max(smoothstep(.03, .1, length(A - bg)), smoothstep(.03, .1, length(B - bg)));
    float change = frontAll > .5 ? subject : smoothstep(.03, .12, length(B - A));
    col += frontCol * band * change * frontS * (1. - col * .5);
  }
#if PTR_MODE == 1
  float lm = ptrLens(q) * uPtrStr * ptrOn;
  if (lm > .0005 || ptrOn > .001) {
    vec3 outside = ptrBase(col, col);
    outside = mix(col, outside, ptrOn);
#if PTR_LAYER == 2
    col = hasLay > .5 ? mix(col, ptrRim(mix(outside, texture(layT, qc).rgb, lm), q), ptrOn) : col;
#else
    col = mix(col, ptrRim(mix(outside, col, lm), q), ptrOn);
#endif
  }
#elif PTR_MODE == 2
  col = mix(col, ptrLight(col, q, 1., vec2(0.)), ptrOn);
#endif
  o = vec4(mix(bg, col, inside), 1.);
}`}const Pt=async(o,a)=>{const c=o.stages,l=o.holds,u=c.length,T=tt()||innerWidth<900,p=tt()?o.phone:o.fit,E=ft,f=a.visual.querySelector(".ss-poster"),m=e=>{e.style.objectFit=p.fit,e.style.objectPosition=`${p.position[0]*100}% ${p.position[1]*100}%`,p.zoom!==1&&(e.style.transform=`scale(${p.zoom})`)};f&&m(f);const d=document.createElement("canvas"),y=d.getContext("webgl2",{antialias:!1,preserveDrawingBuffer:!0});if(!y){const e=[];return await Promise.all(c.map(async(n,r)=>{const g=await I(T?n.imgS:n.img);g.alt="",g.className="ss-stage-still",g.style.opacity=r===0?"1":"0",g.style.transition="opacity .5s",m(g),a.visual.appendChild(g),e[r]=g,a.progress((r+1)/u)})),{update(n){const r=Math.round(G(n.p,l));e.forEach((g,J)=>{g.style.opacity=J===r?"1":"0"})}}}const t=y;a.visual.insertBefore(d,a.visual.firstChild),d.setAttribute("aria-hidden","true");const i=mt(a.section,o),z=(e,n)=>{const r=t.createShader(e);if(t.shaderSource(r,n),t.compileShader(r),!t.getShaderParameter(r,t.COMPILE_STATUS))throw new Error(t.getShaderInfoLog(r)||"shader");return r},v=t.createProgram();t.attachShader(v,z(t.VERTEX_SHADER,xt)),t.attachShader(v,z(t.FRAGMENT_SHADER,Tt(i))),t.linkProgram(v),t.useProgram(v),t.bindBuffer(t.ARRAY_BUFFER,t.createBuffer()),t.bufferData(t.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),t.STATIC_DRAW);const W=t.getAttribLocation(v,"p");t.enableVertexAttribArray(W),t.vertexAttribPointer(W,2,t.FLOAT,!1,0,0);const s={};for(const e of["imgA","imgB","mapT","layT","fitT","cam","f","kind","dir","soft","frontCol","frontW","frontS","frontAll","hasFront","bg","ptrOn","hasLay","uPtrC","uPtrR","uPtrAsp","uPtrSoft","uPtrStr","uPtrCol"])s[e]=t.getUniformLocation(v,e);["imgA","imgB","mapT","layT"].forEach((e,n)=>t.uniform1i(s[e],n)),i&&(t.uniform1f(s.uPtrSoft,i.softness),t.uniform1f(s.uPtrStr,i.strength),t.uniform3fv(s.uPtrCol,i.color));const w=(e,n=!0)=>{const r=t.createTexture();return t.bindTexture(t.TEXTURE_2D,r),e?t.texImage2D(t.TEXTURE_2D,0,t.RGBA,t.RGBA,t.UNSIGNED_BYTE,e):t.texImage2D(t.TEXTURE_2D,0,t.RGBA,1,1,0,t.RGBA,t.UNSIGNED_BYTE,new Uint8Array([0,0,0,255])),e&&n&&t.generateMipmap(t.TEXTURE_2D),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MIN_FILTER,e&&n?t.LINEAR_MIPMAP_LINEAR:t.LINEAR),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MAG_FILTER,t.LINEAR),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_S,t.CLAMP_TO_EDGE),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_T,t.CLAMP_TO_EDGE),r},j=w(null),O=[],Y=[];let S=null;const C=i?.layer==="picture"?i.layers[0]??null:null,nt=u+c.filter(e=>e.reveal.map).length+(C?1:0);let rt=0;const B=()=>a.progress(++rt/Math.max(1,nt));await Promise.all([...c.map(async(e,n)=>{O[n]=w(await I(T?e.imgS:e.img)),B()}),...c.map(async(e,n)=>{Y[n]=e.reveal.map?w(await I(e.reveal.map),!1):null,e.reveal.map&&B()}),C?I(C).then(e=>{S=w(e),B()}).catch(()=>{S=null,B()}):Promise.resolve()]);const F=i?[i.rest[0],i.rest[1]]:null,h=i?ut(d,i,pt()):null;let P=1,b=1;function V(){const e=d.getBoundingClientRect(),n=Math.min(devicePixelRatio||1,2);if(P=d.width=Math.max(1,Math.round(e.width*n)),b=d.height=Math.max(1,Math.round(e.height*n)),t.viewport(0,0,P,b),i&&F){const r=ot(p,P,b,o.w,o.h);i.rest[0]=A((F[0]-.5)/r.sx+r.ox),i.rest[1]=A((F[1]-.5)/r.sy+r.oy),h&&(h.pos[0]=i.rest[0],h.pos[1]=i.rest[1])}h?.dirty()}V();const D=(e,n)=>{t.activeTexture(t.TEXTURE0+e),t.bindTexture(t.TEXTURE_2D,n)},k=(()=>{const e=(getComputedStyle(a.section).getPropertyValue("--bg")||lt("--bg")).trim(),n=e.match(/\d+(\.\d+)?/g);return e.startsWith("#")?et(e):n&&n.length>=3?n.slice(0,3).map(r=>+r/255):[1,1,1]})();let H="";return{resize:V,update(e){const n=A(E?Math.round(G(e.p,l)):G(e.p,l),0,u-1),r=Math.min(u-2,Math.max(0,Math.floor(n+1e-6))),g=A(n-r),L=c[r+1].reveal,U=E?0:o.drift,q=E?0:e.t,$=U*.004*Math.sin(q*.11),X=U*.003*Math.cos(q*.083),_=1+U*.05*e.p+U*.003*Math.sin(q*.07),K=i?N(u-1.35,u-1,n):0,at=h?h.update(e.t):!1,Q=`${r}|${g.toFixed(4)}|${_.toFixed(5)}|${$.toFixed(5)}|${X.toFixed(5)}|${K.toFixed(3)}|${h?h.pos.join(","):""}|${P}x${b}`;if(Q===H&&!at)return;H=Q,D(0,O[r]),D(1,O[r+1]),D(2,Y[r+1]||j),D(3,S||j);const x=ot(p,P,b,o.w,o.h);t.uniform4f(s.fitT,x.sx,x.sy,x.ox,x.oy),t.uniform3f(s.cam,$,X,_),t.uniform1f(s.f,g),t.uniform1i(s.kind,{none:0,fade:1,wipe:2,map:3}[L.kind]??1);const Z=L.angle*Math.PI/180;t.uniform2f(s.dir,Math.cos(Z),Math.sin(Z)),t.uniform1f(s.soft,L.soft);const R=L.front;if(t.uniform1f(s.hasFront,R?1:0),R){const M=et(R.color);t.uniform3f(s.frontCol,M[0],M[1],M[2]),t.uniform1f(s.frontW,R.width),t.uniform1f(s.frontS,R.strength),t.uniform1f(s.frontAll,R.where==="all"?1:0)}if(t.uniform3f(s.bg,k[0],k[1],k[2]),t.uniform1f(s.ptrOn,K),t.uniform1f(s.hasLay,S?1:0),h&&i){const M=d.getBoundingClientRect(),it=dt(h.pos,i.radius,M,null),st=(h.pos[0]-x.ox)*x.sx/_+.5+$,ct=(h.pos[1]-x.oy)*x.sy/_+.5+X;t.uniform2f(s.uPtrC,st,ct),t.uniform1f(s.uPtrR,it.radius*x.sy/_),t.uniform1f(s.uPtrAsp,o.w/o.h)}t.drawArrays(t.TRIANGLE_STRIP,0,4)}}};export{Pt as default,ot as fitTransform,At as frontAt,Rt as revealAt,G as stageAt};
