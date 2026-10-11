import{a as w,r as v,b as st,$ as G,o as N}from"./_kit-B7TPsitT.js";import{c as O,l as it,s as lt}from"../index.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */const et=o=>[1,3,5].map(t=>parseInt(o.slice(t,t+2),16)/255),U=[["#ef008f","#6ec3f4","#7038ff","#ffba27"],["#00d4ff","#3ee1a8","#80e9ff","#635bff"],["#635bff","#a960ee","#90e0ff","#ff6ec7"],["#1a1f71","#635bff","#00d4ff","#80e9ff"],["#ff7a59","#ffba27","#ef008f","#a960ee"]].map(o=>o.map(et)),tt=()=>matchMedia("(max-width: 900px)").matches,y=12;function bt(){document.documentElement.classList.add("gm-live"),mt(),ft(),ut(),dt(),pt(),xt(),gt()}function mt(){w("[data-gm-lines]").forEach(o=>{const t=[],c=(o.textContent||"").trim(),r=f=>{if(f.nodeType===3){const a=document.createDocumentFragment();(f.textContent||"").split(/(\s+)/).forEach(i=>{if(!i)return;if(/^\s+$/.test(i)){a.appendChild(document.createTextNode(" "));return}const g=document.createElement("span");g.className="gm-w",g.textContent=i,t.push(g),a.appendChild(g)}),f.parentNode.replaceChild(a,f)}else[...f.childNodes].forEach(r)};[...o.childNodes].forEach(r),o.setAttribute("aria-label",c);const u=()=>{let f=-1,a=-1e9;for(const i of t)i.offsetTop>a+4&&(f++,a=i.offsetTop),i.style.setProperty("--l",String(f))};u(),document.fonts?.ready.then(u)})}function ft(){const o=new IntersectionObserver(t=>t.forEach(c=>{c.isIntersecting&&(c.target.classList.add("gm-in"),o.unobserve(c.target))}),{threshold:.2,rootMargin:"0px 0px -6% 0px"});w(".gm-rise, [data-gm-lines]").forEach(t=>o.observe(t))}function ut(){w("[data-gm-count]").forEach(o=>{const t=o.dataset.gmCount||"",c=parseFloat(t.replace(/,/g,"")),r=(t.split(".")[1]||"").length,u=t.includes(",");if(v||!isFinite(c))return;const f=a=>u?a.toLocaleString("en-US",{minimumFractionDigits:r,maximumFractionDigits:r}):a.toFixed(r);o.setAttribute("aria-label",t),o.textContent=f(0),st(o.closest(".gm-figure")||o,()=>{const a=performance.now(),i=2100,g=$=>{const b=O(($-a)/i);o.textContent=f(c*(1-Math.pow(1-b,4))),b<1?requestAnimationFrame(g):o.textContent=t};requestAnimationFrame(g)},.4)})}function dt(){w("[data-gm-line]").forEach(o=>{const t=G(".gm-steps__rail i",o),c=w(".gm-step",o);N(({vh:r})=>{const u=o.getBoundingClientRect();if(u.bottom<-r||u.top>r*2)return;const f=v?1:O((r*.62-u.top)/Math.max(1,u.height));t?.style.setProperty("--fill",f.toFixed(4)),c.forEach(a=>a.classList.toggle("is-on",v||a.getBoundingClientRect().top<r*.62))})})}function pt(){const o=G(".gm-hero"),t=document.documentElement;N(()=>{const c=!o||o.getBoundingClientRect().bottom<90;c!==t.classList.contains("gm-past")&&t.classList.toggle("gm-past",c)})}function xt(){if(v)return;const o=w("[data-gm-par]").map(t=>({el:t,d:parseFloat(t.dataset.gmPar||"1"),off:0}));N(({vh:t})=>{for(const c of o){const r=c.el.getBoundingClientRect();if(r.bottom<-200||r.top>t+200)continue;const u=r.top+r.height/2-c.off;c.off=O((u-t/2)*(c.d-1),-80,80),c.el.style.transform=`translate3d(0, ${c.off.toFixed(1)}px, 0)`}})}const ht="attribute vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }",vt=`precision highp float;
uniform vec2 uRes; uniform float uScale;
uniform vec3 uC0; uniform vec3 uC1; uniform vec3 uC2; uniform vec3 uC3; uniform vec3 uGround;
uniform float uAmp; uniform vec3 uPtr;
uniform int uN;
uniform vec4 uR[${y}]; uniform vec4 uE[${y}]; uniform vec4 uK[${y}]; uniform vec4 uW[${y}];
vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
  vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
  float n_=0.142857142857; vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.0*floor(p*ns.z*ns.z); vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
  vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;
  vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
  return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
float sdRound(vec2 p, vec2 b, float r){ vec2 q = abs(p) - b + r; return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r; }
void main(){
  vec2 px = vec2(gl_FragCoord.x, uRes.y - gl_FragCoord.y);
  float mask = 0.0; vec4 R = vec4(0.0); vec4 K = vec4(0.0); vec4 W = vec4(0.0);
  for (int i = 0; i < ${y}; i++) {
    if (i >= uN) break;
    vec4 r = uR[i]; vec4 e = uE[i];
    float lx = clamp((px.x - r.x) / max(r.z, 1.0), 0.0, 1.0);
    float m;
    if (uK[i].w > 1.5) {            // a rounded patch, top corners rounded (the card clips the rest)
      float rad = uK[i].y;
      vec2 c = vec2(r.x + r.z * 0.5, r.y + (r.w + rad) * 0.5);
      m = clamp(0.5 - sdRound(px - c, vec2(r.z, r.w + rad) * 0.5, rad), 0.0, 1.0) * clamp(r.y + r.w - px.y + 0.5, 0.0, 1.0);
    } else {                         // a band with angled top and bottom edges
      float yt = r.y + mix(e.x, e.y, lx); float yb = r.y + r.w - mix(e.z, e.w, lx);
      m = clamp(px.y - yt + 0.5, 0.0, 1.0) * clamp(yb - px.y + 0.5, 0.0, 1.0) * clamp(px.x - r.x + 0.5, 0.0, 1.0) * clamp(r.x + r.z - px.x + 0.5, 0.0, 1.0);
    }
    if (m > mask) { mask = m; R = r; K = uK[i]; W = uW[i]; }
  }
  if (mask <= 0.0) { gl_FragColor = vec4(0.0); return; }
  float s = K.x;
  float t = K.z;
  vec2 uv = px / (uRes.y * 0.9) ;
  // pointer: a hand near water
  vec2 d = px - uPtr.xy; float infl = exp(-dot(d, d) / (220.0 * 220.0 * uScale * uScale)) * uPtr.z;
  uv += normalize(d + 0.0001) * infl * 0.05;
  vec2 q = vec2(snoise(vec3(uv * 0.8, t * 0.35)), snoise(vec3(uv * 0.8 + 5.2, t * 0.35)));
  vec2 w = uv + q * 0.55 * uAmp;
  float n1 = snoise(vec3(w * 0.7, t * 0.5)) * 0.5 + 0.5;
  float n2 = snoise(vec3(w * 1.05 + 3.1, t * 0.6)) * 0.5 + 0.5;
  float n3 = snoise(vec3(w * 0.55 + 7.7, t * 0.42)) * 0.5 + 0.5;
  vec3 col = uC0;
  col = mix(col, uC1, smoothstep(0.32, 0.78, n1));
  col = mix(col, uC2, smoothstep(0.38, 0.82, n2));
  col = mix(col, uC3, smoothstep(0.5, 0.9, n3) * 0.9);
  // a resting patch is quieter: paler, closer to the ground
  col = mix(mix(col, uGround, 0.5), col, s);
  col += infl * 0.06 * s;
  // the hero darkens a little under the nav, so its white links read
  if (K.w > 0.5 && K.w < 1.5) col = mix(col, vec3(0.04, 0.1, 0.2), 0.52 * (1.0 - smoothstep(20.0 * uScale, 150.0 * uScale, px.y - R.y)));
  // mist behind copy that sits on the field
  if (W.w > 0.0) {
    vec2 wc = R.xy + W.xy * R.zw; vec2 wr = R.zw * W.z;
    float dd = length((px - wc) / wr);
    col = mix(col, uGround, W.w * (1.0 - smoothstep(0.25, 1.0, dd)));
  }
  col += (hash(px + fract(t)) - 0.5) * 0.045;     // grain against banding
  gl_FragColor = vec4(col * mask, mask);
}`;function gt(){const o=G(".gm-field");if(!o)return;const t=o.getContext("webgl",{premultipliedAlpha:!0,antialias:!1,alpha:!0});if(!t)return;const c=(n,x)=>{const m=t.createShader(n);if(t.shaderSource(m,x),t.compileShader(m),!t.getShaderParameter(m,t.COMPILE_STATUS))throw new Error(t.getShaderInfoLog(m)||"shader");return m};let r;try{if(r=t.createProgram(),t.attachShader(r,c(t.VERTEX_SHADER,ht)),t.attachShader(r,c(t.FRAGMENT_SHADER,vt)),t.linkProgram(r),!t.getProgramParameter(r,t.LINK_STATUS))throw new Error("link")}catch(n){console.warn("[gradient-mesh] field unavailable",n);return}t.useProgram(r);const u=t.createBuffer();t.bindBuffer(t.ARRAY_BUFFER,u),t.bufferData(t.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),t.STATIC_DRAW);const f=t.getAttribLocation(r,"p");t.enableVertexAttribArray(f),t.vertexAttribPointer(f,2,t.FLOAT,!1,0,0);const a=n=>t.getUniformLocation(r,n),i={res:a("uRes"),scale:a("uScale"),c:[0,1,2,3].map(n=>a(`uC${n}`)),ground:a("uGround"),amp:a("uAmp"),ptr:a("uPtr"),n:a("uN"),r:a("uR"),e:a("uE"),k:a("uK"),w:a("uW")};t.uniform3fv(i.ground,et("#f6f9fc")),document.documentElement.classList.add("gm-gl");const g=w("[data-gm-zone]").map(n=>{const x=n.dataset.gmZone,m=T=>T?T.split(",").map(Number):[0,0,0,0],P=parseFloat(n.dataset.rest||"1");return{el:n,kind:x==="patch"?2:n.classList.contains("gm-zone--hero")?1:0,cutT:parseFloat(n.dataset.cutT||"0"),cutB:parseFloat(n.dataset.cutB||"0"),rest:P,s:P,target:P,t:Math.random()*20,wash:m(n.dataset.wash),mwash:m(n.dataset.mwash||n.dataset.wash),radius:parseFloat(n.dataset.r||"0")}});w("[data-gm-card]").forEach(n=>{const x=g.find(m=>n.contains(m.el));x&&(n.addEventListener("pointerenter",()=>{x.target=1}),n.addEventListener("pointerleave",()=>{x.target=x.rest}))});const $=w("main > section, main > .gm-sec, main > div > section"),b=$.map((n,x)=>{const m=n.dataset.gmPal;return U[m!=null?+m:x%U.length]});let p={x:-9999,y:-9999,z:0},z={x:-9999,y:-9999,z:0};addEventListener("pointermove",n=>{z={x:n.clientX,y:n.clientY,z:1},p.x<-999&&(p={...z,z:0})},{passive:!0}),document.addEventListener("pointerleave",()=>{z.z=0});let F=0,A=0,d=1,C=0,H=0,S="";const j=()=>{d=Math.min(devicePixelRatio||1,2)*(tt()?.6:.5),F=Math.max(1,Math.round(innerWidth*d)),A=Math.max(1,Math.round(innerHeight*d)),(o.width!==F||o.height!==A)&&(o.width=F,o.height=A,t.viewport(0,0,F,A)),S=""};j(),addEventListener("resize",j);const k=new Float32Array(y*4),M=new Float32Array(y*4),_=new Float32Array(y*4),L=new Float32Array(y*4),ot=document.documentElement;let V="";N(({v:n,dt:x,vh:m,y:P})=>{const T=v?0:Math.min(.15,Math.abs(n)*.012);C+=(T-C)*(T>C?.15:.025),p.x+=(z.x-p.x)*.06,p.y+=(z.y-p.y)*.06,p.z+=(z.z-p.z)*.05;const B=m/2,h=$.map(e=>{const s=e.getBoundingClientRect();return s.top+s.height/2});let E=0;if(h.length){if(B<=h[0])E=0;else if(B>=h[h.length-1])E=h.length-1;else for(let e=0;e<h.length-1;e++)if(B>=h[e]&&B<h[e+1]){const s=(B-h[e])/(h[e+1]-h[e]);E=e+(v?s>.5?1:0:lt(.15,.85,s));break}}const q=Math.floor(E),nt=E-q,X=b[q]||U[0],at=b[Math.min(b.length-1,q+1)]||X,Y=[0,1,2,3].map(e=>X[e].map((s,l)=>it(s,at[e][l],nt))),D=E.toFixed(3);D!==V&&(V=D,Y.forEach((e,s)=>ot.style.setProperty(`--gm${s+1}`,"#"+e.map(l=>Math.round(l*255).toString(16).padStart(2,"0")).join(""))));let R=0,Z=!1;const rt=tt();for(const e of g){if(e.s+=(e.target-e.s)*.06,Math.abs(e.target-e.s)>.01&&(Z=!0),e.t+=v?0:x*(.32+.7*e.s)*(1+C*3),R>=y)continue;const s=e.el.getBoundingClientRect();if(s.bottom<=0||s.top>=m||s.width<1)continue;const l=R*4;k[l]=s.left*d,k[l+1]=s.top*d,k[l+2]=s.width*d,k[l+3]=s.height*d;const Q=v?0:((s.top+s.height/2)/m-.5)*1.5,K=Math.tan((e.cutT?e.cutT+Q:0)*Math.PI/180)*s.width*d,W=Math.tan((e.cutB?e.cutB-Q:0)*Math.PI/180)*s.width*d;M[l]=K>0?K:0,M[l+1]=K>0?0:-K,M[l+2]=W>0?0:-W,M[l+3]=W>0?W:0,_[l]=e.s,_[l+1]=e.radius*d,_[l+2]=e.t,_[l+3]=e.kind;const I=rt?e.mwash:e.wash;L[l]=I[0],L[l+1]=I[1],L[l+2]=I[2]||.5,L[l+3]=I[3]||0,R++}if(!R){S!=="empty"&&(t.clearColor(0,0,0,0),t.clear(t.COLOR_BUFFER_BIT),S="empty");return}const ct=Math.abs(n)>.3||Z||p.z>.02||C>.005;H++;const J=`${P.toFixed(0)}|${D}|${R}|${innerWidth}`;v&&J===S||!v&&!ct&&H%2||(S=J,t.uniform2f(i.res,F,A),t.uniform1f(i.scale,d),Y.forEach((e,s)=>t.uniform3fv(i.c[s],e)),t.uniform1f(i.amp,1+C),t.uniform3f(i.ptr,p.x*d,p.y*d,v?0:p.z),t.uniform1i(i.n,R),t.uniform4fv(i.r,k),t.uniform4fv(i.e,M),t.uniform4fv(i.k,_),t.uniform4fv(i.w,L),t.drawArrays(t.TRIANGLES,0,3))})}export{bt as default};
