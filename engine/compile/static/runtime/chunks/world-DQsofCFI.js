import{f as _t,a as ht,i as Ut,c as at,d as kt}from"../index.js";import{p as St,l as It,r as Lt,W as Bt,i as Ft,c as Dt,P as xt}from"./worldText-C7zi4fQu.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */function mt(){const i=document.createElement("video");return i.muted=!0,i.playsInline=!0,i.preload="auto",i}async function vt(i,l,r){try{i.src=await _t(l,r,"video/mp4")}catch{i.src=l}await new Promise(n=>{if(i.readyState>=2)return n();i.addEventListener("loadeddata",()=>n(),{once:!0}),i.addEventListener("error",()=>n(),{once:!0})})}class Nt{constructor(l,r,n){this.videos=l,this.fps=r,this.onLanded=n}busy=!1;shown=-1;id=0;timer=0;seek(l){this.busy=!0;const r=++this.id;let n=!1;const t=(l+.5)/this.fps;let h=this.videos.length;const m=()=>{n||r!==this.id||(n=!0,clearTimeout(this.timer),this.busy=!1,this.shown=l,this.onLanded(l))},v=()=>{--h<=0&&m()};this.timer=window.setTimeout(m,800);for(const p of this.videos){if(Math.abs(p.currentTime-t)<1e-4){queueMicrotask(v);continue}p.addEventListener("seeked",v,{once:!0}),p.currentTime=t}}}const T=3,Gt={behind:0,sky:1,surface:2},Xt=`#version 300 es
in vec2 aPos; out vec2 vUv;
void main() { vUv = vec2(aPos.x * 0.5 + 0.5, 0.5 - aPos.y * 0.5); gl_Position = vec4(aPos, 0.0, 1.0); }`,Ct=`#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
#define N ${T}
#define PAD ${xt.toFixed(3)}
${Bt}
uniform sampler2D uFilm, uAtlas, uText;
uniform vec2 uGrid, uInset, uTexel;
uniform float uOn[N], uIn[N];
uniform int uKind[N];
uniform mat3 uM[N];
uniform vec4 uBox[N], uCell[N], uA[N], uB[N];
uniform vec2 uSlot[N];

float atlasAt(vec2 slot, vec2 uv) {
  vec2 t = clamp(uv, uInset, 1.0 - uInset);
  return texture(uAtlas, (slot + t) / uGrid).r;
}
// the scene's depth here; the nearest of a few taps, so an occluder's edge is not eaten by the type's halo
float depthAt(vec2 slot, vec2 uv) {
  float d = atlasAt(slot, uv);
  d = max(d, atlasAt(slot, uv + vec2(uTexel.x, 0.0)));
  d = max(d, atlasAt(slot, uv - vec2(uTexel.x, 0.0)));
  d = max(d, atlasAt(slot, uv + vec2(0.0, uTexel.y)));
  d = max(d, atlasAt(slot, uv - vec2(0.0, uTexel.y)));
  return d;
}

void main() {
  vec3 film = texture(uFilm, vUv).rgb;
  vec3 col = film;
  vec3 near = textureLod(uFilm, vUv, 1.6).rgb;      // the picture without its grain
  vec3 locl = textureLod(uFilm, vUv, 3.6).rgb;      // the light right here
  vec3 air = textureLod(uFilm, vUv, 6.5).rgb;       // the colour of the air here
  for (int s = 0; s < N; s++) {
    if (uOn[s] < 0.002) continue;
    vec3 q = uM[s] * vec3(vUv, 1.0);
    vec2 pl = q.xy / q.z;
    vec2 lc = (pl - uBox[s].xy) / (uBox[s].zw * (1.0 + 2.0 * PAD)) + 0.5;
    vec2 dx = dFdx(lc), dy = dFdy(lc);
    vec2 inb = step(vec2(0.0), lc) * step(lc, vec2(1.0));
    float inside = inb.x * inb.y * step(0.0, q.z);
    vec2 tuv = uCell[s].xy + clamp(lc, 0.0, 1.0) * uCell[s].zw;
    float bl = exp2(uA[s].w);
    vec4 t = textureGrad(uText, tuv, dx * uCell[s].zw * bl, dy * uCell[s].zw * bl);      // premultiplied
    float cov = t.a * inside;
    if (cov < 0.002) continue;
    vec3 ink = t.rgb / max(t.a, 1e-4);
    if (uKind[s] != 2) {
      float dep = depthAt(uSlot[s], vUv);
      col = worldBehindSky(col, ink, cov, film, near, locl, air, dep, uA[s], uB[s], uOn[s], uIn[s], uKind[s], vUv.y);
    } else {
      col = worldSurface(col, ink, cov, film, near, locl, pl, atlasAt(uSlot[s], vUv), uB[s], uOn[s], uIn[s], lc.x);
    }
  }
  o = vec4(col, 1.0);
}`;function pt(i,l,r){const n=i.createShader(l);if(i.shaderSource(n,r),i.compileShader(n),!i.getShaderParameter(n,i.COMPILE_STATUS))throw new Error("world shader: "+i.getShaderInfoLog(n));return n}const nt=(i,l,r)=>{const n=at((r-i)/Math.max(l-i,1e-9));return n*n*(3-2*n)};function Ot(i){const[l,r,n,t,h,m,v,p,E]=i,B=h*E-m*p,R=-(t*E-m*v),G=t*p-h*v,F=l*B+r*R+n*G;if(Math.abs(F)<1e-12)return null;const c=1/F;return[B*c,-(r*E-n*p)*c,(r*m-n*h)*c,R*c,(l*E-n*v)*c,-(l*m-n*t)*c,G*c,-(l*p-r*v)*c,(l*h-r*t)*c]}async function $t(i,l){const r=i.world;if(!r||!r.texts.length||ht)return null;const n=document.createElement("canvas"),t=n.getContext("webgl2",{alpha:!1,antialias:!1,powerPreference:"high-performance"});if(!t)return null;const h=Ut(),m=mt(),v=r.atlas?mt():null,p=v?[m,v]:[m],E=[0,0],B=()=>l.progress(.95*(E[0]*.75+E[1]*.25));if(await Promise.all([vt(m,h&&i.videoMobile?i.videoMobile:i.video,e=>{E[0]=e,B()}),v&&r.atlas?vt(v,h&&r.atlas.mobile?r.atlas.mobile:r.atlas.video,e=>{E[1]=e,B()}):Promise.resolve()]),p.some(e=>e.readyState<2))return null;const R=r.fps||24,G=Math.min(...p.map(e=>e.duration||0)),F=Math.max(1,Math.min(r.frames,Math.round(G*R)));try{await document.fonts.ready}catch{}const c=St(l.section);try{await document.fonts.load(`${c.weight} 64px ${c.family}`),await document.fonts.load(`italic ${c.weight} 64px ${c.family}`)}catch{}const q=m.videoWidth||1920,st=m.videoHeight||1080,it=Math.min(1,(h?1280:1920)/q);n.width=Math.round(q*it),n.height=Math.round(st*it);const P=[],Tt=[...l.section.querySelectorAll(".ss-caption[data-world]")];for(const e of r.texts){const s=l.data.steps[e.i];if(!s||!s.at)continue;const o=e.style,a=o.weight??c.weight,f=(e.quad?.6:.3)*e.plane[1],S=It(s.title,c,{size:e.box[2],hMax:f,lines:o.lines??void 0,caps:o.caps,track:o.track,weight:a,align:o.align});P.push({cfg:e,step:e.i,at:s.at,lay:S,cell:{x:0,y:0,w:0,h:0},enabled:!0,rgb:[1,1,1],caption:Tt.find(I=>I.dataset.world===String(e.i))||null})}if(!P.length)return null;const wt=(e,s)=>{const o=e.cfg.style,a=e.cfg.tone??.5;let f;return o.color==="ink"?f=c.ink:o.color==="paper"?f=c.paper:o.color==="accent"?f=c.accent:/^#|^rgb/i.test(o.color)?f=o.color:f=Ft(a,c),!s||o.color!=="auto"?f:Dt(c.emColor,a,c)},Y=Lt(P.map(e=>{const s=e.lay.wPlane*(e.cfg.ppp??1)*n.width*1.2;return{layout:e.lay,px:Math.min(2600,Math.max(256,s)),colors:o=>wt(e,o),weight:e.cfg.style.weight??c.weight,track:e.cfg.style.track,caps:e.cfg.style.caps,align:e.cfg.style.align,st:c}}));P.forEach((e,s)=>{e.cell=Y.cells[s]});let y;try{if(y=t.createProgram(),t.attachShader(y,pt(t,t.VERTEX_SHADER,Xt)),t.attachShader(y,pt(t,t.FRAGMENT_SHADER,Ct)),t.linkProgram(y),!t.getProgramParameter(y,t.LINK_STATUS))throw new Error(t.getProgramInfoLog(y)||"link failed")}catch(e){return console.warn("[scroll-studio] world: shader failed, playing the plain film",e),null}t.useProgram(y);const Et=t.createBuffer();t.bindBuffer(t.ARRAY_BUFFER,Et),t.bufferData(t.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),t.STATIC_DRAW);const rt=t.getAttribLocation(y,"aPos");t.enableVertexAttribArray(rt),t.vertexAttribPointer(rt,2,t.FLOAT,!1,0,0);const H=(e,s)=>{const o=t.createTexture();return t.activeTexture(t.TEXTURE0+e),t.bindTexture(t.TEXTURE_2D,o),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MIN_FILTER,s?t.LINEAR_MIPMAP_LINEAR:t.LINEAR),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MAG_FILTER,t.LINEAR),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_S,t.CLAMP_TO_EDGE),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_T,t.CLAMP_TO_EDGE),o},yt=H(0,!0),At=H(1,!1),gt=H(2,!0),d=e=>t.getUniformLocation(y,e);t.uniform1i(d("uFilm"),0),t.uniform1i(d("uAtlas"),1),t.uniform1i(d("uText"),2),t.activeTexture(t.TEXTURE2),t.bindTexture(t.TEXTURE_2D,gt),t.pixelStorei(t.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!0),t.texImage2D(t.TEXTURE_2D,0,t.RGBA,t.RGBA,t.UNSIGNED_BYTE,Y.canvas),t.generateMipmap(t.TEXTURE_2D),t.pixelStorei(t.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1);const M=r.atlas,X=M?M.tile:[960,544];t.uniform2f(d("uGrid"),M?.cols??1,M?.rows??1),t.uniform2f(d("uInset"),.5/X[0]*(h?2:1),.5/X[1]*(h?2:1)),t.uniform2f(d("uTexel"),1.5/X[0]/(h?.5:1),1.5/X[1]/(h?.5:1)),t.viewport(0,0,n.width,n.height),l.visual.appendChild(n);const bt=e=>{const s=Math.max(0,M?.slots.indexOf(e)??0),o=M?.cols??1;return[s%o,Math.floor(s/o)]},A={on:d("uOn[0]"),inn:d("uIn[0]"),kind:d("uKind[0]"),m:d("uM[0]"),box:d("uBox[0]"),cell:d("uCell[0]"),A:d("uA[0]"),B:d("uB[0]"),slot:d("uSlot[0]")},u={on:new Float32Array(T),inn:new Float32Array(T),kind:new Int32Array(T),m:new Float32Array(9*T),box:new Float32Array(4*T),cell:new Float32Array(4*T),A:new Float32Array(4*T),B:new Float32Array(4*T),slot:new Float32Array(2*T)},_=q/st;function V(){const e=l.visual.getBoundingClientRect(),s=Math.max(.1,e.width/Math.max(1,e.height)),o=s<_?s/_:1,a=s>_?_/s:1,f=document.getElementById("ss-nav"),S=f?Math.min(.3,(f.offsetHeight+6)/Math.max(1,e.height)):0,I=(1-o)/2+.01,C=1-(1-o)/2-.01,O=(1-a)/2+.01+a*S,Q=1-(1-a)/2-.01,x=s<_?e.height*_:e.width;for(const g of P){const b=g.cfg;let L=!0;for(const Z of[b.anchor]){const tt=b.m[Math.min(b.m.length-1,Math.max(0,Z-b.f0))],w=Ot(tt);if(!w){L=!1;break}const[z,W]=[b.box[0],b.box[1]],$=g.lay.wPlane/2,K=g.lay.hPlane/2;for(const[et,ot]of[[z-$,W-K],[z+$,W-K],[z+$,W+K],[z-$,W+K]]){const ut=w[6]*et+w[7]*ot+w[8],dt=(w[0]*et+w[1]*ot+w[2])/ut,ft=(w[3]*et+w[4]*ot+w[5])/ut;dt>I&&dt<C&&ft>O&&ft<Q||(L=!1)}}g.lay.fs*(b.ppp??1)*x<22&&(L=!1),g.enabled=L&&!ht,g.caption?.classList.toggle("ss-world-on",g.enabled)}}V();const Rt=()=>V(),U=window.__ssWorld||={};U.live=P,U.fits=V;let D=0,N=0,j="";function lt(){let e=0;const s=[String(N)];u.on.fill(0);for(const o of P){if(e>=T||!o.enabled)continue;const a=o.cfg,[f,S]=o.at,I=at((D-f)/.07),C=nt(f,f+.02,D)*(1-nt(S-.025,S,D));if(C<.002||N<a.f0||N>a.f1)continue;const O=N-a.f0,Q=a.c[Math.min(a.c.length-1,O)],x=a.m[Math.min(a.m.length-1,O)],g=e*9;u.m.set([x[0],x[3],x[6],x[1],x[4],x[7],x[2],x[5],x[8]],g);const b=a.kind==="surface"?nt(.1,.5,Q):1;u.on[e]=C*b,u.inn[e]=I,u.kind[e]=Gt[a.kind],u.box.set([a.box[0],a.box[1],o.lay.wPlane,o.lay.hPlane],e*4),u.cell.set([o.cell.x,o.cell.y,o.cell.w,o.cell.h],e*4);const L=a.blur??(a.kind==="surface"?.8:0),Z=o.cell.w*Y.canvas.width/Math.max(1,o.lay.wPlane*(a.ppp??1)*(1+2*xt)*n.width),tt=Math.log2(Math.max(1,1+L*(n.width/1920)*Z));u.A.set([a.depth??0,a.soft??.04,a.style.haze,tt],e*4),u.B.set([a.style.fog,a.style.wear,a.style.relief,a.tone??.5],e*4),u.slot.set(bt(a.slot),e*2),s.push(`${e}:${u.on[e].toFixed(3)}:${I.toFixed(2)}`),e++}return s.join("|")}const ct=()=>{t.uniform1fv(A.on,u.on),t.uniform1fv(A.inn,u.inn),t.uniform1iv(A.kind,u.kind),t.uniformMatrix3fv(A.m,!1,u.m),t.uniform4fv(A.box,u.box),t.uniform4fv(A.cell,u.cell),t.uniform4fv(A.A,u.A),t.uniform4fv(A.B,u.B),t.uniform2fv(A.slot,u.slot)};function Pt(){t.activeTexture(t.TEXTURE0),t.bindTexture(t.TEXTURE_2D,yt),t.texImage2D(t.TEXTURE_2D,0,t.RGBA,t.RGBA,t.UNSIGNED_BYTE,m),t.generateMipmap(t.TEXTURE_2D),v&&(t.activeTexture(t.TEXTURE1),t.bindTexture(t.TEXTURE_2D,At),t.texImage2D(t.TEXTURE_2D,0,t.RGBA,t.RGBA,t.UNSIGNED_BYTE,v))}function Mt(){j=lt(),ct(),t.drawArrays(t.TRIANGLES,0,3)}const k=new Nt(p,R,e=>{N=e,Pt(),Mt(),U.frame=e,U.times=p.map(s=>s.currentTime),U.onDraw?.(e)});k.seek(0),await new Promise(e=>{const s=()=>k.busy?requestAnimationFrame(s):e();s()}),addEventListener("touchstart",()=>{p.forEach(e=>e.play().then(()=>e.pause()).catch(()=>{}))},{once:!0,passive:!0}),l.section.classList.add("ss-world");let J=0;return{resize(){Rt()},update(e){D=e.p;const s=e.p*(F-1)/R;J+=(s-J)*kt;const o=at(Math.round(J*R),0,F-1);if(U.p=D,o!==k.shown&&!k.busy)k.seek(o);else if(!k.busy){const a=lt();a!==j&&(ct(),t.drawArrays(t.TRIANGLES,0,3),j=a)}}}}export{$t as default};
