import{a as mt,i as _t,c as at,d as Ut}from"../index.js";import{m as ht,l as vt,P as St}from"./film-260CH0VO.js";import{p as It,l as kt,r as Ft,W as Bt,i as Dt,c as Nt,P as xt}from"./worldText-C7zi4fQu.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */const x=3,Lt={behind:0,sky:1,surface:2},Gt=`#version 300 es
in vec2 aPos; out vec2 vUv;
void main() { vUv = vec2(aPos.x * 0.5 + 0.5, 0.5 - aPos.y * 0.5); gl_Position = vec4(aPos, 0.0, 1.0); }`,Xt=`#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
#define N ${x}
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
}`;function pt(u,c,r){const s=u.createShader(c);if(u.shaderSource(s,r),u.compileShader(s),!u.getShaderParameter(s,u.COMPILE_STATUS))throw new Error("world shader: "+u.getShaderInfoLog(s));return s}const nt=(u,c,r)=>{const s=at((r-u)/Math.max(c-u,1e-9));return s*s*(3-2*s)};function Ct(u){const[c,r,s,t,m,h,v,T,A]=u,B=m*A-h*T,R=-(t*A-h*v),G=t*T-m*v,D=c*B+r*R+s*G;if(Math.abs(D)<1e-12)return null;const l=1/D;return[B*l,-(r*A-s*T)*l,(r*h-s*m)*l,R*l,(c*A-s*v)*l,-(c*h-s*t)*l,G*l,-(c*T-r*v)*l,(c*m-r*t)*l]}async function $t(u,c){const r=u.world;if(!r||!r.texts.length||mt)return null;const s=document.createElement("canvas"),t=s.getContext("webgl2",{alpha:!1,antialias:!1,powerPreference:"high-performance"});if(!t)return null;const m=_t(),h=ht(),v=r.atlas?ht():null,T=v?[h,v]:[h],A=[0,0],B=()=>c.progress(.95*(A[0]*.75+A[1]*.25));if(await Promise.all([vt(h,m&&u.videoMobile?u.videoMobile:u.video,e=>{A[0]=e,B()}),v&&r.atlas?vt(v,m&&r.atlas.mobile?r.atlas.mobile:r.atlas.video,e=>{A[1]=e,B()}):Promise.resolve()]),T.some(e=>e.readyState<2))return null;const R=r.fps||24,G=Math.min(...T.map(e=>e.duration||0)),D=Math.max(1,Math.min(r.frames,Math.round(G*R)));try{await document.fonts.ready}catch{}const l=It(c.section);try{await document.fonts.load(`${l.weight} 64px ${l.family}`),await document.fonts.load(`italic ${l.weight} 64px ${l.family}`)}catch{}const q=h.videoWidth||1920,st=h.videoHeight||1080,lt=Math.min(1,(m?1280:1920)/q);s.width=Math.round(q*lt),s.height=Math.round(st*lt);const P=[],Tt=[...c.section.querySelectorAll(".ss-caption[data-world]")];for(const e of r.texts){const a=c.data.steps[e.i];if(!a||!a.at)continue;const o=e.style,n=o.weight??l.weight,d=(e.quad?.6:.3)*e.plane[1],I=kt(a.title,l,{size:e.box[2],hMax:d,lines:o.lines??void 0,caps:o.caps,track:o.track,weight:n,align:o.align});P.push({cfg:e,step:e.i,at:a.at,lay:I,cell:{x:0,y:0,w:0,h:0},enabled:!0,rgb:[1,1,1],caption:Tt.find(k=>k.dataset.world===String(e.i))||null})}if(!P.length)return null;const wt=(e,a)=>{const o=e.cfg.style,n=e.cfg.tone??.5;let d;return o.color==="ink"?d=l.ink:o.color==="paper"?d=l.paper:o.color==="accent"?d=l.accent:/^#|^rgb/i.test(o.color)?d=o.color:d=Dt(n,l),!a||o.color!=="auto"?d:Nt(l.emColor,n,l)},Y=Ft(P.map(e=>{const a=e.lay.wPlane*(e.cfg.ppp??1)*s.width*1.2;return{layout:e.lay,px:Math.min(2600,Math.max(256,a)),colors:o=>wt(e,o),weight:e.cfg.style.weight??l.weight,track:e.cfg.style.track,caps:e.cfg.style.caps,align:e.cfg.style.align,st:l}}));P.forEach((e,a)=>{e.cell=Y.cells[a]});let E;try{if(E=t.createProgram(),t.attachShader(E,pt(t,t.VERTEX_SHADER,Gt)),t.attachShader(E,pt(t,t.FRAGMENT_SHADER,Xt)),t.linkProgram(E),!t.getProgramParameter(E,t.LINK_STATUS))throw new Error(t.getProgramInfoLog(E)||"link failed")}catch(e){return console.warn("[scroll-studio] world: shader failed, playing the plain film",e),null}t.useProgram(E);const At=t.createBuffer();t.bindBuffer(t.ARRAY_BUFFER,At),t.bufferData(t.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),t.STATIC_DRAW);const rt=t.getAttribLocation(E,"aPos");t.enableVertexAttribArray(rt),t.vertexAttribPointer(rt,2,t.FLOAT,!1,0,0);const H=(e,a)=>{const o=t.createTexture();return t.activeTexture(t.TEXTURE0+e),t.bindTexture(t.TEXTURE_2D,o),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MIN_FILTER,a?t.LINEAR_MIPMAP_LINEAR:t.LINEAR),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MAG_FILTER,t.LINEAR),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_S,t.CLAMP_TO_EDGE),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_T,t.CLAMP_TO_EDGE),o},Et=H(0,!0),gt=H(1,!1),yt=H(2,!0),f=e=>t.getUniformLocation(E,e);t.uniform1i(f("uFilm"),0),t.uniform1i(f("uAtlas"),1),t.uniform1i(f("uText"),2),t.activeTexture(t.TEXTURE2),t.bindTexture(t.TEXTURE_2D,yt),t.pixelStorei(t.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!0),t.texImage2D(t.TEXTURE_2D,0,t.RGBA,t.RGBA,t.UNSIGNED_BYTE,Y.canvas),t.generateMipmap(t.TEXTURE_2D),t.pixelStorei(t.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1);const M=r.atlas,X=M?M.tile:[960,544];t.uniform2f(f("uGrid"),M?.cols??1,M?.rows??1),t.uniform2f(f("uInset"),.5/X[0]*(m?2:1),.5/X[1]*(m?2:1)),t.uniform2f(f("uTexel"),1.5/X[0]/(m?.5:1),1.5/X[1]/(m?.5:1)),t.viewport(0,0,s.width,s.height),c.visual.appendChild(s);const bt=e=>{const a=Math.max(0,M?.slots.indexOf(e)??0),o=M?.cols??1;return[a%o,Math.floor(a/o)]},g={on:f("uOn[0]"),inn:f("uIn[0]"),kind:f("uKind[0]"),m:f("uM[0]"),box:f("uBox[0]"),cell:f("uCell[0]"),A:f("uA[0]"),B:f("uB[0]"),slot:f("uSlot[0]")},i={on:new Float32Array(x),inn:new Float32Array(x),kind:new Int32Array(x),m:new Float32Array(9*x),box:new Float32Array(4*x),cell:new Float32Array(4*x),A:new Float32Array(4*x),B:new Float32Array(4*x),slot:new Float32Array(2*x)},_=q/st;function V(){const e=c.visual.getBoundingClientRect(),a=Math.max(.1,e.width/Math.max(1,e.height)),o=a<_?a/_:1,n=a>_?_/a:1,d=document.getElementById("ss-nav"),I=d?Math.min(.3,(d.offsetHeight+6)/Math.max(1,e.height)):0,k=(1-o)/2+.01,C=1-(1-o)/2-.01,O=(1-n)/2+.01+n*I,Q=1-(1-n)/2-.01,p=a<_?e.height*_:e.width;for(const y of P){const b=y.cfg;let F=!0;for(const Z of[b.anchor]){const tt=b.m[Math.min(b.m.length-1,Math.max(0,Z-b.f0))],w=Ct(tt);if(!w){F=!1;break}const[z,W]=[b.box[0],b.box[1]],$=y.lay.wPlane/2,K=y.lay.hPlane/2;for(const[et,ot]of[[z-$,W-K],[z+$,W-K],[z+$,W+K],[z-$,W+K]]){const ut=w[6]*et+w[7]*ot+w[8],ft=(w[0]*et+w[1]*ot+w[2])/ut,dt=(w[3]*et+w[4]*ot+w[5])/ut;ft>k&&ft<C&&dt>O&&dt<Q||(F=!1)}}y.lay.fs*(b.ppp??1)*p<22&&(F=!1),y.enabled=F&&!mt,y.caption?.classList.toggle("ss-world-on",y.enabled)}}V();const Rt=()=>V(),U=window.__ssWorld||={};U.live=P,U.fits=V;let N=0,L=0,j="";function it(){let e=0;const a=[String(L)];i.on.fill(0);for(const o of P){if(e>=x||!o.enabled)continue;const n=o.cfg,[d,I]=o.at,k=at((N-d)/.07),C=nt(d,d+.02,N)*(1-nt(I-.025,I,N));if(C<.002||L<n.f0||L>n.f1)continue;const O=L-n.f0,Q=n.c[Math.min(n.c.length-1,O)],p=n.m[Math.min(n.m.length-1,O)],y=e*9;i.m.set([p[0],p[3],p[6],p[1],p[4],p[7],p[2],p[5],p[8]],y);const b=n.kind==="surface"?nt(.1,.5,Q):1;i.on[e]=C*b,i.inn[e]=k,i.kind[e]=Lt[n.kind],i.box.set([n.box[0],n.box[1],o.lay.wPlane,o.lay.hPlane],e*4),i.cell.set([o.cell.x,o.cell.y,o.cell.w,o.cell.h],e*4);const F=n.blur??(n.kind==="surface"?.8:0),Z=o.cell.w*Y.canvas.width/Math.max(1,o.lay.wPlane*(n.ppp??1)*(1+2*xt)*s.width),tt=Math.log2(Math.max(1,1+F*(s.width/1920)*Z));i.A.set([n.depth??0,n.soft??.04,n.style.haze,tt],e*4),i.B.set([n.style.fog,n.style.wear,n.style.relief,n.tone??.5],e*4),i.slot.set(bt(n.slot),e*2),a.push(`${e}:${i.on[e].toFixed(3)}:${k.toFixed(2)}`),e++}return a.join("|")}const ct=()=>{t.uniform1fv(g.on,i.on),t.uniform1fv(g.inn,i.inn),t.uniform1iv(g.kind,i.kind),t.uniformMatrix3fv(g.m,!1,i.m),t.uniform4fv(g.box,i.box),t.uniform4fv(g.cell,i.cell),t.uniform4fv(g.A,i.A),t.uniform4fv(g.B,i.B),t.uniform2fv(g.slot,i.slot)};function Pt(){t.activeTexture(t.TEXTURE0),t.bindTexture(t.TEXTURE_2D,Et),t.texImage2D(t.TEXTURE_2D,0,t.RGBA,t.RGBA,t.UNSIGNED_BYTE,h),t.generateMipmap(t.TEXTURE_2D),v&&(t.activeTexture(t.TEXTURE1),t.bindTexture(t.TEXTURE_2D,gt),t.texImage2D(t.TEXTURE_2D,0,t.RGBA,t.RGBA,t.UNSIGNED_BYTE,v))}function Mt(){j=it(),ct(),t.drawArrays(t.TRIANGLES,0,3)}const S=new St(T,R,e=>{L=e,Pt(),Mt(),U.frame=e,U.times=T.map(a=>a.currentTime),U.onDraw?.(e)});S.seek(0),await new Promise(e=>{const a=()=>S.busy?requestAnimationFrame(a):e();a()}),addEventListener("touchstart",()=>{T.forEach(e=>e.play().then(()=>e.pause()).catch(()=>{}))},{once:!0,passive:!0}),c.section.classList.add("ss-world");let J=0;return{resize(){Rt()},update(e){N=e.p;const a=e.p*(D-1)/R;J+=(a-J)*Ut;const o=at(Math.round(J*R),0,D-1);if(U.p=N,o!==S.shown&&!S.busy)S.seek(o);else if(!S.busy){const n=it();n!==j&&(ct(),t.drawArrays(t.TRIANGLES,0,3),j=n)}}}}export{$t as default};
