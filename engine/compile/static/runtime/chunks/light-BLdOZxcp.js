import{i as Lt,k as It,g as _,c as R,l as z,s as C,a as Ut}from"../index.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */const Ct=`#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`,Ft=`#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
uniform sampler2D imgA, imgB, ratioT, lampT, depthT, skyT, flowT;
uniform vec2 sc;            // cover-fit scale
uniform vec2 ctr;           // the picture point the screen's centre looks at
uniform vec3 cam;           // drift x, y and zoom
uniform float strength;     // parallax strength
uniform float focus;        // depth that stays put
uniform float fe;           // progress between the two times, 0-1
uniform float aspect;       // picture width / height
uniform vec2 origin;        // where the new light arrives from, picture uv
uniform float light;        // 1: light-aware transition, 0: plain crossfade
uniform float hasLamp, lampOn, glow;
uniform vec3 lampCol;
uniform float hazeA, hazeB, mistOn;
uniform vec3 fogA, fogB;
uniform vec3 sunCol, edgeCol;
uniform vec2 sunPos;
uniform float sunAmt, sunSize, t;
uniform float vig, grain;

vec3 lin(vec3 c){ return pow(c, vec3(2.2)); }
float hash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vn(vec2 p){
  vec2 i = floor(p), f = fract(p); f = f * f * (3. - 2. * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p){ return .55 * vn(p) + .3 * vn(p * 2.1 + 7.3) + .15 * vn(p * 4.3 + 2.9); }

void main(){
  // 2.5D: solve for the picture point that lands on this pixel (near things move further than far ones)
  vec2 c = (uv - .5) / (sc * cam.z) + ctr;
  vec2 q = c;
  for (int i = 0; i < ITER; i++) { float d = texture(depthT, q).r; q = c - (d - focus) * cam.xy * strength; }
  q = clamp(q, vec2(.001), vec2(.999));

  float d = texture(depthT, q).r;
  float sk = smoothstep(.4, .6, texture(skyT, q).r);          // the sky's edge stays where the roofline is
  // how the place's structure sits differently in the two pictures (the editor redrew it a little): the picture glides
  // along it as the light changes, so edges slide into place instead of cross-fading doubled
  vec3 fl = texture(flowT, q).rgb;
  vec2 F = (fl.rg - .5) * (2. * 24.) * fl.b;
  vec2 Fuv = vec2(F.x / 1024., F.y * aspect / 1024.);
  float s = fe;
  vec3 R = vec3(1.);
  if (light > .5) {
    // the front: new light spreads from its source, sky first, near ground last, ragged edge
    float gr = clamp(length((q - origin) * vec2(aspect, 1.)) / (aspect * .9), 0., 1.);
    float g = .5 * gr + .32 * (1. - d) + .12 * vn(q * vec2(8. * aspect, 8.)) + .06 * q.y;
    g = mix(g, g * .55, sk);
    g = clamp(g, 0., 1.);
    const float w = .42;
    s = smoothstep(g * (1. - w), g * (1. - w) + w, fe);
    // the low-frequency change of light, carried by both pictures to the same in-between light
    R = exp2((texture(ratioT, q).rgb - .5) * 6.);
  }
  vec3 A = lin(texture(imgA, q - s * Fuv).rgb), B = lin(texture(imgB, q + (1. - s) * Fuv).rgb);
  vec3 col, Am = A, Bm = B;
  if (light > .5) {
    Am = A * pow(R, vec3(fe));
    Bm = B * pow(R, vec3(-(1. - fe)));
    col = mix(Am, Bm, s);
    col += edgeCol * (s * (1. - s) * 4.) * .05 * smoothstep(0., .1, fe) * smoothstep(1., .9, fe);
  } else {
    col = mix(A, B, fe);
  }

  // lamps and windows: each its own moment, then a halo
  if (hasLamp > .5) {
    vec4 L = texture(lampT, q);
    float pop = smoothstep(L.g * .6, L.g * .6 + .16, fe);
    vec3 offc = lampOn > .5 ? Am : A;
    vec3 onc = lampOn > .5 ? B : Bm;
    col = mix(col, mix(offc, onc, pop), L.r);
    // the halo is the flash of switching, not a state: the pictures at either end already carry their own glow
    float level = sin(3.14159 * fe);
    col += lampCol * L.b * glow * .45 * level * level;
  }

  // mist: thicker with distance and low on the water, drifting
  if (mistOn > .5) {
    float hz = mix(hazeA, hazeB, fe);
    if (hz > .002) {
      float n = fbm(q * vec2(3.4 * aspect, 2.4) + vec2(t * .010, t * .004));
      float amt = hz * pow(1. - d, 1.25) * (.55 + .7 * n) * mix(.55, 1., smoothstep(.3, .7, q.y));
      col = mix(col, lin(mix(fogA, fogB, fe)), clamp(amt, 0., .85));
    }
  }

  // sun / moon: a glow over the sky only
  if (sunAmt > .002) {
    float dd = length((q - sunPos) * vec2(aspect, 1.));
    float gl = exp(-dd * dd / (2. * sunSize * sunSize)) * .85 + exp(-dd / (sunSize * 2.8)) * .22;
    vec3 add = sunCol * gl * sunAmt * smoothstep(.15, .7, sk);
    col = 1. - (1. - col) * (1. - clamp(add, 0., .95));
  }

  col = pow(max(col, 0.), vec3(1. / 2.2));
  float v = smoothstep(1.2, .4, length((uv - .5) * vec2(1.1, 1.)));
  col *= mix(1., v, vig);
  col += (hash(gl_FragCoord.xy + fract(t) * 17.) - .5) * grain;
  o = vec4(col, 1.);
}`,Dt=n=>{const c=n.replace("#","");return[0,2,4].map(i=>parseInt(c.slice(i,i+2),16)/255)},U=(n,c,i)=>n.map((u,p)=>u+(c[p]-u)*i),h=n=>n.map(c=>Math.round(c)).join(", ");function tt(n,c){if(!c.length)return 0;if(n<=c[0].a)return c[0].t;for(let i=0;i<c.length;i++){const u=c[i];if(n<=u.b)return u.t;const p=c[i+1];if(!p)return u.t;if(n<p.a)return z(u.t,p.t,C(u.b,p.a,n))}return c[c.length-1].t}function et(n,c){const i=c.rise,u=c.noon,p=c.set,d=[2*u[0]-.5*(i[0]+p[0]),2*u[1]-.5*(i[1]+p[1])],b=n>=5.5&&n<=20.5,k=n<5.5?n+24:n,l=R(b?(n-5.5)/15:(k-20.5)/9),X=(1-l)*(1-l)*i[0]+2*l*(1-l)*d[0]+l*l*p[0],N=(1-l)*(1-l)*i[1]+2*l*(1-l)*d[1]+l*l*p[1];return{x:X,y:N,k:Math.sin(Math.PI*l),u:l,moon:!b}}const $t=async(n,c)=>{const i=n.times,u=n.pairs,p=n.holds,d=i.length,b=Lt()||innerWidth<900,k=Ut;let l=null,X=null,N=null,F=null;const ot=[];n.clock&&(l=document.createElement("div"),l.className="ss-tod",l.setAttribute("aria-hidden","true"),l.innerHTML=`<svg viewBox="0 0 64 34" width="64" height="34"><path d="M4 31 Q32 -12 60 31" fill="none" stroke="currentColor" stroke-width="1" opacity=".45"/><line x1="2" y1="31" x2="62" y2="31" stroke="currentColor" stroke-width="1" opacity=".45"/><circle class="ss-tod__dot" r="3.6" cx="4" cy="31"/></svg><div class="ss-tod__t"><b class="ss-tod__time">--:--</b><span class="ss-tod__label"></span></div><div class="ss-tod__ticks">${i.map(()=>"<i></i>").join("")}</div>`,c.visual.appendChild(l),X=l.querySelector(".ss-tod__time"),N=l.querySelector(".ss-tod__label"),F=l.querySelector(".ss-tod__dot"),ot.push(...l.querySelectorAll(".ss-tod__ticks i")));const st=(e,s)=>{if(!l)return;const o=Math.min(d-2,Math.max(0,Math.floor(e))),r=R(e-o),f=z(i[o].hours,i[Math.min(d-1,o+1)].hours,r),m=(f%24+24)%24,T=Math.floor(m%1*60);X.textContent=`${String(Math.floor(m)).padStart(2,"0")}:${String(T).padStart(2,"0")}`;const v=Math.round(e);if(N.textContent=i[Math.min(d-1,Math.max(0,v))].label,ot.forEach((y,x)=>y.classList.toggle("on",x===v)),F){const y=et(f,s||{rise:[.1,.5],noon:[.5,.06],set:[.92,.5]});F.setAttribute("cx",(4+56*y.u).toFixed(1)),F.setAttribute("cy",(31-Math.sin(Math.PI*y.u)*21.5).toFixed(1)),F.classList.toggle("moon",y.moon)}},E=c.section;let nt=-1;const rt=e=>{if(!n.follow||Math.abs(e-nt)<.003)return;nt=e;const s=Math.min(d-1,Math.max(0,Math.floor(e))),o=Math.min(d-1,s+1),r=R(e-s),f=i[s].tokens,m=i[o].tokens,T=C(.4,.6,r),v=U(f.bg,m.bg,r),y=U(f.bg2,m.bg2,r),x=U(f.ink,m.ink,T),Q=U(f.em,m.em,T),O=U(f.accent,m.accent,T),I=z(f.a2,m.a2,T),q=z(f.a3,m.a3,T),g=E.style;g.setProperty("--bg",`rgb(${h(v)})`),g.setProperty("--bg-2",`rgb(${h(y)})`),g.setProperty("--bg-rgb",h(v)),g.setProperty("--ink",`rgb(${h(x)})`),g.setProperty("--ink-rgb",h(x)),g.setProperty("--ink-2",`rgba(${h(x)}, ${I.toFixed(2)})`),g.setProperty("--ink-3",`rgba(${h(x)}, ${q.toFixed(2)})`),g.setProperty("--line",`rgba(${h(x)}, .14)`),g.setProperty("--accent",`rgb(${h(O)})`),g.setProperty("--accent-text",`rgb(${h(O)})`),g.setProperty("--em-color",`rgb(${h(Q)})`),E.dataset.tod=i[Math.round(e)<0?0:Math.min(d-1,Math.round(e))].id},at=It(E,c.data),bt=[...E.querySelectorAll(".ss-caption")],Et=[...E.querySelectorAll(".ss-step")],it=(e,s)=>{if(!e||!n.follow)return;const o=i[Math.max(0,Math.min(d-1,s))].tokens,r=e.style;r.setProperty("--ink",`rgb(${h(o.ink)})`),r.setProperty("--ink-rgb",h(o.ink)),r.setProperty("--bg-rgb",h(o.bg)),r.setProperty("--ink-2",`rgba(${h(o.ink)}, ${o.a2.toFixed(2)})`),r.setProperty("--ink-3",`rgba(${h(o.ink)}, ${o.a3.toFixed(2)})`),r.setProperty("--accent",`rgb(${h(o.accent)})`),r.setProperty("--accent-text",`rgb(${h(o.accent)})`),r.setProperty("--em-color",`rgb(${h(o.em)})`),r.setProperty("--line",`rgba(${h(o.ink)}, .14)`)};bt.forEach((e,s)=>it(e,n.stepTimes[at[s]?.step??s]??0)),Et.forEach((e,s)=>it(e,n.stepTimes[s]??0));const At=at.map(e=>e.show);let ct=-1;const lt=e=>{if(E.dataset.layout==="cards"||c.data.layout!=="overlay")return;let s=0;for(const[o,r]of At)s=Math.max(s,C(o-.05,o+.01,e)*(1-C(r-.01,r+.05,e)));Math.abs(s-ct)>.004&&(ct=s,E.style.setProperty("--shade",s.toFixed(3)))},M=document.createElement("canvas"),ft=M.getContext("webgl2",{antialias:!1,preserveDrawingBuffer:!0});if(!ft){const e=[];return await Promise.all(i.map(async(s,o)=>{const r=await _(b?s.imgS:s.img);r.className="ss-light-still",r.alt="",r.style.opacity=o===0?"1":"0",r.style.objectPosition=`${(n.focus?.[0]??.5)*100}% ${(n.focus?.[1]??.5)*100}%`,c.visual.appendChild(r),e[o]=r})),{update(s){const o=Math.round(tt(s.p,p));e.forEach((r,f)=>{r.style.opacity=f===o?"1":"0"}),rt(o),st(o,n.sun),lt(s.p)}}}const t=ft;c.visual.insertBefore(M,c.visual.firstChild),M.setAttribute("aria-hidden","true");const wt=b?4:6,mt=(e,s)=>{const o=t.createShader(e);if(t.shaderSource(o,s),t.compileShader(o),!t.getShaderParameter(o,t.COMPILE_STATUS))throw new Error(t.getShaderInfoLog(o)||"shader");return o},P=t.createProgram();t.attachShader(P,mt(t.VERTEX_SHADER,Ct)),t.attachShader(P,mt(t.FRAGMENT_SHADER,Ft.replace("ITER",String(wt)))),t.linkProgram(P),t.useProgram(P),t.bindBuffer(t.ARRAY_BUFFER,t.createBuffer()),t.bufferData(t.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),t.STATIC_DRAW);const ht=t.getAttribLocation(P,"p");t.enableVertexAttribArray(ht),t.vertexAttribPointer(ht,2,t.FLOAT,!1,0,0);const a={};for(const e of["imgA","imgB","ratioT","lampT","depthT","skyT","flowT","sc","ctr","cam","strength","focus","fe","aspect","origin","light","hasLamp","lampOn","glow","lampCol","hazeA","hazeB","mistOn","fogA","fogB","sunCol","edgeCol","sunPos","sunAmt","sunSize","t","vig","grain"])a[e]=t.getUniformLocation(P,e);["imgA","imgB","ratioT","lampT","depthT","skyT","flowT"].forEach((e,s)=>t.uniform1i(a[e],s));const S=(e,s,o=!0)=>{const r=t.createTexture();return t.bindTexture(t.TEXTURE_2D,r),t.texImage2D(t.TEXTURE_2D,0,t.RGBA,t.RGBA,t.UNSIGNED_BYTE,e),s&&t.generateMipmap(t.TEXTURE_2D),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MIN_FILTER,s?t.LINEAR_MIPMAP_LINEAR:t.LINEAR),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MAG_FILTER,o?t.LINEAR:t.NEAREST),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_S,t.CLAMP_TO_EDGE),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_T,t.CLAMP_TO_EDGE),r},D=e=>{const s=t.createTexture();return t.bindTexture(t.TEXTURE_2D,s),t.texImage2D(t.TEXTURE_2D,0,t.RGBA,1,1,0,t.RGBA,t.UNSIGNED_BYTE,new Uint8Array(e)),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MIN_FILTER,t.LINEAR),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MAG_FILTER,t.LINEAR),s},_t=D([0,0,0,255]),Rt=D([128,128,128,255]),kt=D([128,128,0,255]),Mt=d*1+u.length*3+2;let Pt=0;const B=()=>c.progress(++Pt/Mt),G=[],ut=[],H=[],pt=[];let gt=D([128,128,128,255]),dt=D([0,0,0,255]),L=n.w/n.h;await Promise.all([...i.map(async(e,s)=>{const o=await _(b?e.imgS:e.img);G[s]=S(o,!0),L=n.w/n.h,B()}),...u.map(async(e,s)=>{const o=await _(e.ratio);ut[s]=S(o,!1),B()}),...u.map(async(e,s)=>{H[s]=e.lamp?S(await _(e.lamp),!1):null,B()}),...u.map(async(e,s)=>{pt[s]=e.flow?S(await _(e.flow),!1):null,B()}),_(n.depth).then(e=>{gt=S(e,!1),B()}),_(n.sky).then(e=>{dt=S(e,!1),B()})]);let W=1,Y=1;function vt(){const e=M.getBoundingClientRect(),s=Math.min(devicePixelRatio||1,b?1.5:2);W=M.width=Math.max(1,Math.round(e.width*s)),Y=M.height=Math.max(1,Math.round(e.height*s)),t.viewport(0,0,W,Y)}vt();const A=(e,s)=>{t.activeTexture(t.TEXTURE0+e),t.bindTexture(t.TEXTURE_2D,s)},w=n.sun;let j=0,V=0;function St(e,s){if(!s||!w)return t.uniform1f(a.sunAmt,0),t.uniform2f(a.sunPos,.5,.2),{x:.5,y:.3};const o=et(e,w),r=o.moon?[.62,.74,1]:U([1,.52,.22],[1,.93,.8],C(.05,.5,o.k)),f=(o.moon?.32:.55+.25*(1-o.k))*w.strength*C(.02,.18,o.k);return t.uniform2f(a.sunPos,o.x,o.y),t.uniform3f(a.sunCol,r[0],r[1],r[2]),t.uniform1f(a.sunAmt,f),t.uniform1f(a.sunSize,.05*w.size),o}return{resize:vt,update(e){const s=R(k?Math.round(tt(e.p,p)):tt(e.p,p),0,d-1),o=Math.min(d-2,Math.max(0,Math.floor(s+1e-6))),r=R(s-o),f=i[o],m=i[o+1],T=u[o];j+=(e.mx-j)*.05,V+=(e.my-V)*.05;const v=k?0:n.drift,y=k?0:e.t,x=v*(.012*Math.sin(y*.11)+.016*(e.p-.5))+j*.01*v,Q=v*(.006*Math.cos(y*.083))+V*.006*v,O=1.035+v*.025*(s/Math.max(1,d-1))+v*.004*Math.sin(y*.07);A(0,G[o]),A(1,G[o+1]),A(2,ut[o]||Rt),A(3,H[o]||_t),A(4,gt),A(5,dt),A(6,pt[o]||kt);const I=W/Y,q=I>L?1:L/I,g=I>L?I/L:1,Tt=n.focus||[.5,.5];t.uniform2f(a.sc,q,g),t.uniform2f(a.ctr,R(Tt[0],.5/(q*1.04),1-.5/(q*1.04)),R(Tt[1],.5/(g*1.04),1-.5/(g*1.04))),t.uniform3f(a.cam,x,Q,O),t.uniform1f(a.strength,1),t.uniform1f(a.focus,.55),t.uniform1f(a.fe,r),t.uniform1f(a.aspect,L),t.uniform1f(a.light,n.blend==="light"?1:0);const Bt=z(f.hours,m.hours,r);St(Bt,!!w);const yt=m.sun==="none"&&f.sun==="none"?{x:.5,y:.9}:et(m.hours,w||{rise:[.1,.5],noon:[.5,.06],set:[.92,.5]});t.uniform2f(a.origin,yt.x,yt.y);const J=m.tokens.em.map($=>$/255);t.uniform3f(a.edgeCol,J[0],J[1],J[2]);const xt=!!H[o]&&T.lamp;if(t.uniform1f(a.hasLamp,xt?1:0),xt){const $=Dt(T.color||"#ffb35c");t.uniform3f(a.lampCol,$[0],$[1],$[2]),t.uniform1f(a.glow,T.glow),t.uniform1f(a.lampOn,m.lit&&!f.lit?1:f.lit&&!m.lit?0:1)}t.uniform1f(a.mistOn,n.mist?1:0),t.uniform1f(a.hazeA,f.haze),t.uniform1f(a.hazeB,m.haze);const K=f.tokens.fog||f.tokens.bg,Z=m.tokens.fog||m.tokens.bg;t.uniform3f(a.fogA,K[0]/255,K[1]/255,K[2]/255),t.uniform3f(a.fogB,Z[0]/255,Z[1]/255,Z[2]/255),t.uniform1f(a.t,k?0:e.t),t.uniform1f(a.vig,.3),t.uniform1f(a.grain,.012),t.drawArrays(t.TRIANGLE_STRIP,0,4),rt(s),st(s,w),lt(e.p)}}};export{et as celestial,$t as default,tt as timeAt};
