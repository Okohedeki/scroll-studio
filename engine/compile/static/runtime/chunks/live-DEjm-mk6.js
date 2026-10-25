import{c as b}from"../index.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */const _={sweep:1,glint:2,drift:3,rise:4,flow:5},y=4,p=24,f=(t,o,n,e)=>typeof t=="number"&&Number.isFinite(t)?b(t,n,e):o;function B(t){if(!Array.isArray(t))return[];const o=[];for(const n of t){if(!n||typeof n!="object"||!(n.kind in _)||!Array.isArray(n.box)||n.box.length!==4)continue;const[e,s,c,a]=n.box.map(i=>f(i,0,0,1));if(c>e&&a>s&&(o.push({kind:n.kind,box:[e,s,c,a],speed:f(n.speed,1,.1,4),strength:f(n.strength,.6,0,1),softness:f(n.softness,.25,0,.5),count:Math.round(f(n.count,12,1,p)),color:typeof n.color=="string"&&/^#[0-9a-f]{6}$/i.test(n.color)?n.color:"#ffffff",angle:f(n.angle,0,-360,360),origin:Array.isArray(n.origin)&&n.origin.length===2?[f(n.origin[0],.5,-2,3),f(n.origin[1],.5,-2,3)]:null,mask:typeof n.mask=="string"?n.mask:null,points:Array.isArray(n.points)?n.points.slice(0,p).filter(i=>Array.isArray(i)&&i.length>=2).map(i=>[f(i[0],.5,0,1),f(i[1],.5,0,1),f(i[2],1,0,1)]):[]}),o.length===y))break}return o}const d=Math.PI*2,x=(t,o,n)=>{const e=b((n-t)/(o-t));return e*e*(3-2*e)},E=t=>[Math.cos(t*Math.PI/180),Math.sin(t*Math.PI/180)],L={sweep:7,beam:9,glint:3.2,drift:16,flow:0};function U(t,o){if(t[0]<0||t[0]>1||t[1]<0||t[1]>1)return 0;const n=Math.max(o,.001);return x(0,n,t[0])*x(0,n,1-t[0])*x(0,n,t[1])*x(0,n,1-t[1])}const O=(t,o)=>[(t[0]-o[0])/(o[2]-o[0]),(t[1]-o[1])/(o[3]-o[1])],N=(t,o)=>(t[2]-t[0])*o/(t[3]-t[1]);function C(t,o,n){const e=.035*o*Math.sin(d*t/L.drift);return[n[0]*e,n[1]*e]}function D(t,o,n,e){const s=Math.max(e,1),c=[(t[0]-.5)*e/s,(t[1]-.5)/s],a=c[0]*n[0]+c[1]*n[1],i=(o/L.sweep%1+1)%1/.5;if(i>1)return 0;const r=-.8+1.6*x(0,1,i);return Math.exp(-(((a-r)/.07)**2))*Math.sqrt(Math.max(0,Math.sin(Math.PI*i)))}function G(t,o,n,e,s){const c=Math.max(s,1),a=[(t[0]-e[0])*s/c,(t[1]-e[1])/c],i=Math.atan2(a[1],a[0]),r=Math.atan2(n[1],n[0])+d*o/L.beam,l=Math.abs(((i-r+Math.PI)%d+d)%d-Math.PI);return Math.exp(-((l/.16)**2))*(.55+.45*Math.exp(-Math.hypot(a[0],a[1])*1.5))}function j(t,o){const n=((t/L.glint+o)%1+1)%1;return n<.35?Math.sin(Math.PI*n/.35)**2:0}function W(t,o){const n=Math.abs(t[0])/o,e=Math.abs(t[1])/o,s=Math.exp(-(n*n+e*e)*6),c=Math.exp(-n*n*60-e*3)+Math.exp(-e*e*60-n*3);return Math.min(1,s+.6*c)}const g=(t,o)=>{const n=Math.sin(t*127.1+o*311.7)*43758.5453;return n-Math.floor(n)};function R(t,o){const n=Math.max(2,Math.round(Math.sqrt(t*o)));return[n,Math.max(2,Math.round(t/n))]}function $(t,o,n,e){const[s,c]=R(n,e),a=t[0]*s,i=(t[1]+o*.09)*c,r=Math.floor(a),l=Math.floor(i),u=g(r,l),v=g(r+7.1,l+1.7);if(g(r+3.3,l+9.2)<.45)return 0;const m=[a-r,i-l],h=[.3+.4*u+.15*Math.sin(o*1.1+u*d),.3+.4*v],A=e/s,k=1/c,V=Math.min(A,k),M=[(m[0]-h[0])*A/V,(m[1]-h[1])*k/V],I=.1+.08*v,q=x(0,.45,t[1])*(1-x(.85,1,t[1]));return Math.exp(-(M[0]*M[0]+M[1]*M[1])/(I*I))*(.7+.3*Math.sin(o*3+u*20))*q}function H(t,o,n,e){const s=[-e[1],e[0]],c=(t[0]*s[0]+t[1]*s[1])*38+o*1.6,a=(t[0]*e[0]+t[1]*e[1])*11-o*.9,i=n/.6,r=Math.sin(c+Math.sin(a))*.0022*i,l=Math.cos(c*.7-o)*.0012*i;return{d:[s[0]*r+e[0]*l,s[1]*r+e[1]*l],shimmer:1+.05*n*Math.sin(c*1.3+a)}}const K=(t,o)=>1-(1-t)*(1-b(o));function S(t){return[1,3,5].map(o=>parseInt(t.slice(o,o+2),16)/255)}function J(t){const o=t*y*4;return{box:new Float32Array(o),a:new Float32Array(o),b:new Float32Array(o),c:new Float32Array(o),m:new Float32Array(o),p:new Float32Array(t*p*4)}}function Q(t,o,n,e=[]){for(let s=0;s<y;s++){const c=(o*y+s)*4,a=n[s];for(const v of[t.box,t.a,t.b,t.c,t.m])v.fill(0,c,c+4);if(!a)continue;const i=E(a.angle);t.box.set(a.box,c),t.a.set([_[a.kind],a.speed,a.strength,a.softness],c);let r=-99,l=-99;if(a.kind==="sweep"&&a.origin&&([r,l]=a.origin),a.kind==="glint"){const v=n.slice(0,s).reduce((m,h)=>m+(h.kind==="glint"?Math.min(h.points?.length??0,h.count):0),0),w=(a.points??[]).slice(0,Math.min(a.count,p-v));w.forEach((m,h)=>t.p.set([m[0],m[1],m[2],g(h+.37,s+1.3)],(o*p+v+h)*4)),r=o*p+v,l=w.length}t.b.set([i[0],i[1],r,l],c),t.c.set([...S(a.color),a.count],c);const u=e[s];u&&t.m.set(u,c)}}function z(t,o=256){const n=Math.max(1,Math.ceil(Math.sqrt(t))),e=Math.max(1,Math.ceil(t/n)),s=n*o,c=e*o,a=[];for(let i=0;i<t;i++){const r=i%n,l=Math.floor(i/n);a.push([(r*o+.5)/s,(l*o+.5)/c,(o-1)/s,(o-1)/c])}return{cols:n,rows:e,cells:a}}async function X(t,o){const n=t.map((r,l)=>r?l:-1).filter(r=>r>=0);if(!n.length)return{canvas:null,cells:t.map(()=>null)};const e=256,s=z(n.length,e),c=document.createElement("canvas");c.width=s.cols*e,c.height=s.rows*e;const a=c.getContext("2d"),i=t.map(()=>null);return await Promise.all(n.map(async(r,l)=>{try{const u=await o(t[r]);a?.drawImage(u,l%s.cols*e,Math.floor(l/s.cols)*e,e,e),i[r]=s.cells[l]}catch{}})),{canvas:c,cells:i}}function P(t){if(t==="left"||t==="top")return 0;if(t==="right"||t==="bottom")return 1;if(t==="center")return .5;const o=parseFloat(t);return Number.isFinite(o)?o/100:.5}function Y(t,o,n,e,s){if(!t||!o||!n)return null;const c=s.split(/\s+/),a=P(c[0]??"50%"),i=P(c[1]??c[0]??"50%");let r,l;if(e==="cover")l=Math.max(t/n,o),r=l*n;else if(e==="contain"||e==="scale-down")l=Math.min(t/n,o),r=l*n;else if(e==="fill"||e==="100% 100%")r=t,l=o;else return null;return{x:(t-r)*a,y:(o-l)*i,w:r,h:l}}const Z=(t,o,n)=>[t/n.w,o/n.h,-n.x/n.w,-n.y/n.h],T=30,tt=(t,o,n=T)=>o<0||t-o>=1e3/n-1,nt=(t,o,n)=>t&&!o&&!n,ot=`
#define LV_PER ${y}
#define LV_POINTS ${p}
uniform vec4 uLvBox[LV_VIEWS * LV_PER], uLvA[LV_VIEWS * LV_PER], uLvB[LV_VIEWS * LV_PER], uLvC[LV_VIEWS * LV_PER], uLvM[LV_VIEWS * LV_PER];
uniform vec4 uLvP[LV_VIEWS * LV_POINTS];
uniform float uLvT, uLvAsp;
uniform sampler2D uLvMask;
const float LV_TAU = 6.28318530718;
float lvHash(vec2 p) { return fract(sin(p.x * 127.1 + p.y * 311.7) * 43758.5453); }
float lvRegion(int i, vec2 q) {
  vec4 b = uLvBox[i];
  vec2 l = (q - b.xy) / (b.zw - b.xy);
  if (l.x < 0.0 || l.x > 1.0 || l.y < 0.0 || l.y > 1.0) return 0.0;
  float s = max(uLvA[i].w, 1e-3);
  vec2 e = smoothstep(vec2(0.0), vec2(s), l) * smoothstep(vec2(0.0), vec2(s), 1.0 - l);
  float m = e.x * e.y;
  vec4 c = uLvM[i];
  if (c.z > 0.0) m *= texture(uLvMask, c.xy + l * c.zw).r;
  return m;
}
float lvSweep(vec2 l, float t, vec2 dir, vec2 o, float ba) {
  float k = max(ba, 1.0);
  if (o.x > -50.0) {
    vec2 v = (l - o) * vec2(ba, 1.0) / k;
    float th = atan(dir.y, dir.x) + LV_TAU * t / 9.0;
    float d = abs(mod(atan(v.y, v.x) - th + 3.14159265, LV_TAU) - 3.14159265);
    float e = d / 0.16;
    return exp(-e * e) * (0.55 + 0.45 * exp(-length(v) * 1.5));
  }
  vec2 p = (l - 0.5) * vec2(ba, 1.0) / k;
  float s = dot(p, dir);
  float x = fract(t / 7.0) / 0.5;
  if (x > 1.0) return 0.0;
  float c = -0.8 + 1.6 * smoothstep(0.0, 1.0, x);
  float e = (s - c) / 0.07;
  return exp(-e * e) * sqrt(max(sin(3.14159265 * x), 0.0));
}
float lvGlint(vec2 q, int first, int n, float t, float s) {
  float I = 0.0;
  for (int j = 0; j < LV_POINTS; j++) {
    if (j >= n) break;
    vec4 pt = uLvP[first + j];
    vec2 d = (q - pt.xy) * vec2(uLvAsp, 1.0);
    float r = 0.016 * (0.6 + 0.4 * pt.z) * (0.7 + 0.5 * s);
    if (abs(d.x) > r * 3.0 || abs(d.y) > r * 3.0) continue;
    float ph = fract(t / 3.2 + pt.w);
    float sw = sin(3.14159265 * ph / 0.35);
    float tw = ph < 0.35 ? sw * sw : 0.0;
    vec2 a = abs(d) / r;
    float st = exp(-dot(a, a) * 6.0) + 0.6 * (exp(-a.x * a.x * 60.0 - a.y * 3.0) + exp(-a.y * a.y * 60.0 - a.x * 3.0));
    I += tw * min(st, 1.0);
  }
  return min(I, 1.0);
}
float lvRise(vec2 l, float t, float count, float ba) {
  float cols = max(2.0, floor(sqrt(count * ba) + 0.5));
  float rows = max(2.0, floor(count / cols + 0.5));
  vec2 g = vec2(l.x * cols, (l.y + t * 0.09) * rows);
  vec2 cell = floor(g), f = g - cell;
  float h = lvHash(cell), h2 = lvHash(cell + vec2(7.1, 1.7)), h3 = lvHash(cell + vec2(3.3, 9.2));
  if (h3 < 0.45) return 0.0;
  vec2 c = vec2(0.3 + 0.4 * h + 0.15 * sin(t * 1.1 + h * LV_TAU), 0.3 + 0.4 * h2);
  vec2 sc = vec2(ba / cols, 1.0 / rows);
  vec2 d = (f - c) * sc / min(sc.x, sc.y);
  float r = 0.1 + 0.08 * h2;
  float fade = smoothstep(0.0, 0.45, l.y) * (1.0 - smoothstep(0.85, 1.0, l.y));
  return exp(-dot(d, d) / (r * r)) * (0.7 + 0.3 * sin(t * 3.0 + h * 20.0)) * fade;
}
vec3 liveApply(sampler2D img, vec2 q, vec3 col, int v, inout float alpha) {
  for (int k = 0; k < LV_PER; k++) {
    int i = v * LV_PER + k;
    vec4 A = uLvA[i];
    int kind = int(A.x + 0.5);
    if (kind == 0) continue;
    vec4 b = uLvBox[i];
    float reach = kind == 3 ? 0.04 * A.z / min(uLvAsp, 1.0) + 0.002 : 0.0;
    if (q.x < b.x - reach || q.x > b.z + reach || q.y < b.y - reach || q.y > b.w + reach) continue;
    float t = uLvT * A.y, s = A.z;
    vec2 dir = uLvB[i].xy;
    if (kind == 3) {
      vec2 off = dir * 0.035 * s * sin(LV_TAU * t / 16.0);
      vec2 offUv = vec2(off.x / uLvAsp, off.y);
      float m = max(lvRegion(i, q), lvRegion(i, q - offUv));
      if (m <= 0.0) continue;
      col = mix(col, texture(img, q - offUv).rgb, m);
      alpha = max(alpha, m);
      continue;
    }
    float m = lvRegion(i, q);
    if (m <= 0.0) continue;
    if (kind == 5) {
      vec2 p = q * vec2(uLvAsp, 1.0), across = vec2(-dir.y, dir.x);
      float a1 = dot(p, across) * 38.0 + t * 1.6, a2 = dot(p, dir) * 11.0 - t * 0.9, kk = s / 0.6;
      vec2 d = across * sin(a1 + sin(a2)) * 0.0022 * kk + dir * cos(a1 * 0.7 - t) * 0.0012 * kk;
      vec3 w = texture(img, q + vec2(d.x / uLvAsp, d.y)).rgb * (1.0 + 0.05 * s * sin(a1 * 1.3 + a2));
      col = mix(col, clamp(w, 0.0, 1.0), m);
      alpha = max(alpha, m);
      continue;
    }
    vec2 l = (q - b.xy) / (b.zw - b.xy);
    float ba = (b.z - b.x) * uLvAsp / (b.w - b.y);
    float I = kind == 1 ? lvSweep(l, t, dir, uLvB[i].zw, ba)
            : kind == 2 ? lvGlint(q, int(uLvB[i].z + 0.5), int(uLvB[i].w + 0.5), t, s)
            : lvRise(l, t, uLvC[i].w, ba);
    // a sweep is a broad light, so gentler; glints and specks are small, so brighter
    float gain = kind == 1 ? 0.7 : kind == 2 ? 1.4 : 1.2;
    vec3 light = clamp(uLvC[i].rgb * I * s * m * gain, 0.0, 1.0);
    col = 1.0 - (1.0 - col) * (1.0 - light);
    alpha = max(alpha, max(light.r, max(light.g, light.b)));
  }
  return col;
}
`;export{T as FPS,_ as KINDS,ot as LIVE_GLSL,y as PER,L as PERIOD,p as POINTS,z as atlasCells,N as boxAspect,E as dirOf,C as driftOffset,tt as due,U as edge,J as emptyPack,H as flowAt,g as hash,S as hexRgb,O as local,X as maskAtlas,Q as packView,P as parsePos,Y as pictureRect,B as readLive,$ as riseField,R as riseGrid,K as screenOver,nt as shouldRun,W as star,D as sweepBand,G as sweepBeam,j as twinkle,Z as uvMap};
