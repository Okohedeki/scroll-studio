import"../index.js";/*! DesignAI runtime by Edeki Okoh: https://github.com/Okohedeki/designai. GNU AGPL-3.0 with the DesignAI Output Exception (see NOTICE.md); keep this notice. */const G=`
const vec3 LW = vec3(0.2126, 0.7152, 0.0722);
float hash(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) { float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * vnoise(p); p *= 2.03; a *= 0.5; } return s / 0.9375; }

// A = (type depth, soft, haze, blur lod), B = (fog, wear, relief, tone of the footage behind the type)
vec3 worldBehindSky(vec3 col, vec3 ink, float cov, vec3 film, vec3 near, vec3 locl, vec3 air, float dep, vec4 A, vec4 B,
                    float on, float intro, int kind, float vy) {
  float vis = 1.0 - smoothstep(A.x - A.y, A.x + A.y, dep);
  float lumLoc = dot(locl, LW), Lf = dot(film, LW), Ln = dot(near, LW);
  vec3 lit = ink * mix(1.0, clamp(lumLoc / max(B.w, 0.02), 0.55, 1.25), 0.55);
  float hz = clamp(A.z * (1.0 + (1.0 - intro) * 1.4), 0.0, 0.95);
  lit = mix(lit, air, hz);
  lit += (Lf - Ln) * 0.9;                                   // the grain of the picture runs through the letters
  float a = cov * vis * on * (1.0 - 0.3 * hz);
  if (kind == 1) {
    // fog in front: thicker low in the picture, and over the far things that stand just in front of the type (a ridge in haze)
    float ridge = smoothstep(A.x - 0.02, A.x + 0.03, dep) * (1.0 - smoothstep(A.x + 0.05, A.x + 0.4, dep));
    float fog = B.x * (0.14 + 0.5 * smoothstep(0.1, 0.9, vy) + 0.45 * ridge);
    lit = mix(lit, air, clamp(fog * 0.7, 0.0, 1.0));
    a *= 1.0 - clamp(fog * 0.4, 0.0, 0.6);
  }
  return mix(col, lit, clamp(a, 0.0, 1.0));
}

// pl: the plane's coordinates (noise sticks to the surface), m: the surface's mask here, lx: 0-1 across the type (the paint-on wipe)
vec3 worldSurface(vec3 col, vec3 ink, float cov, vec3 film, vec3 near, vec3 locl, vec2 pl, float m, vec4 B,
                  float on, float intro, float lx) {
  float vis = smoothstep(0.35, 0.65, m);
  float lumLoc = dot(locl, LW), Lf = dot(film, LW), Ln = dot(near, LW);
  float wipe = smoothstep(lx - 0.18, lx + 0.02, intro * 1.3 - 0.1);
  float n = fbm(pl * 52.0) * 0.75 + (0.5 - (Lf - Ln) * 5.0) * 0.25;
  float th = 1.0 - B.y * 0.9;
  float worn = 1.0 - smoothstep(th - 0.1, th + 0.14, n) * step(0.001, B.y);
  float lightK = clamp(lumLoc / max(B.w, 0.03), 0.35, 1.5);
  vec3 paint = ink * mix(1.0, lightK, 0.9);
  float texK = clamp(Lf / max(Ln, 0.03), 0.55, 1.5);
  paint *= mix(1.0, texK * texK, B.z);
  float inkL = dot(ink, LW);
  vec3 bleed = inkL < 0.5 ? film * ink * 1.8 : 1.0 - (1.0 - film) * (1.0 - ink * 0.9);
  paint = mix(paint, bleed, 0.2 + 0.25 * B.z);
  paint += (Lf - Ln) * 0.8 * B.z;
  // paint does not stop in a clean vector edge: the grain of the surface ragged-edges every letter
  float rough = fbm(pl * 230.0 + Lf * 3.0);
  float thr = 0.45 + (rough - 0.5) * 0.5 * B.z;
  float edge = smoothstep(thr - 0.16, thr + 0.16, cov);
  float a = edge * vis * on * worn * wipe * 0.97;
  return mix(col, paint, clamp(a, 0.0, 1.0));
}
`;function V(a){const o=document.createElement("h2");o.className="ss-display",o.setAttribute("aria-hidden","true"),o.style.cssText="position:absolute;visibility:hidden;pointer-events:none;left:0;top:0;",o.innerHTML="A<em>b</em>",a.appendChild(o);const t=getComputedStyle(o),n=getComputedStyle(o.querySelector("em")),f=getComputedStyle(document.documentElement),p=(m,u)=>f.getPropertyValue(m).trim()||u,i=p("--ink","#f2efe9"),h=p("--bg","#0b0b0b"),c=m=>{const[u,v,x]=O(m);return .2126*u+.7152*v+.0722*x},[s,l]=c(i)>=c(h)?[i,h]:[h,i],r=parseFloat(t.fontSize)||64,e={family:t.fontFamily||"serif",weight:parseInt(t.fontWeight)||500,emItalic:n.fontStyle==="italic",emColor:n.color,accent:p("--accent",n.color),light:s,dark:l,ink:i,paper:h,tracking:(parseFloat(t.letterSpacing)||0)/r,lead:parseFloat(t.lineHeight)/r||1.02};return o.remove(),e}const M=document.createElement("canvas").getContext("2d");function O(a){M.fillStyle="#000",M.fillStyle=a;const o=M.fillStyle;if(o.startsWith("#")){const n=parseInt(o.slice(1),16);return[(n>>16&255)/255,(n>>8&255)/255,(n&255)/255]}const t=o.match(/[\d.]+/g)||["0","0","0"];return[+t[0]/255,+t[1]/255,+t[2]/255]}function U(a){const o=[];let t=!1;for(const n of a.split(/(<\/?em>)/i)){if(/^<em>$/i.test(n)){t=!0;continue}if(/^<\/em>$/i.test(n)){t=!1;continue}const f=n.replace(/<[^>]+>/g,"").replace(/&amp;/g,"&").replace(/&lt;/g,"<").replace(/&gt;/g,">").replace(/&nbsp;/g," ");for(const p of f.split(/\s+/))p&&o.push({text:p,em:t})}return o}function L(a,o,t,n){return`${t&&a.emItalic?"italic ":""}${o} ${n}px ${a.family}`}function N(a,o,t,n,f,p){const i=[];for(const c of o)a.font=L(t,n,c.em,100),b(a,f*100),i.push(a.measureText(p?c.text.toUpperCase():c.text).width+(A?0:f*100*c.text.length));a.font=L(t,n,!1,100),b(a,0);const h=a.measureText(" ").width+f*100;return{widths:i,space:h}}const A="letterSpacing"in CanvasRenderingContext2D.prototype;function b(a,o){A&&(a.letterSpacing=`${o}px`)}function R(a,o,t){const n=a.length;t=Math.min(t,n);const f=[0];for(const l of a)f.push(f[f.length-1]+l);const p=(l,r)=>f[r]-f[l]+o*(r-l-1),i=Array.from({length:t+1},()=>new Array(n+1).fill(1/0)),h=Array.from({length:t+1},()=>new Array(n+1).fill(0));i[0][0]=0;for(let l=1;l<=t;l++)for(let r=l;r<=n;r++)for(let e=l-1;e<r;e++){const m=Math.max(i[l-1][e],p(e,r));m<i[l][r]&&(i[l][r]=m,h[l][r]=e)}const c=[];let s=n;for(let l=t;l>=1;l--){const r=h[l][s];c.unshift([r,s]),s=r}return c}function _(a,o,t){const n=U(a),{widths:f,space:p}=N(M,n,o,t.weight,t.track,t.caps),i=o.lead*(t.caps?1.04:1);let h=null;for(const m of t.lines?[t.lines]:[1,2,3,4,5]){if(!t.lines&&m>n.length)break;const u=R(f,p,m),v=u.map(([y,w])=>n.slice(y,w)),x=Math.max(...u.map(([y,w])=>f.slice(y,w).reduce((S,k)=>S+k,0)+p*(w-y-1)))/100,d=t.size/x*i*v.length;if(t.lines||!h||d<=t.hMax)h={lines:v,maxW:x};else break}const c=h;let s=t.size/c.maxW;const l=s*i*c.lines.length;l>t.hMax&&(s*=t.hMax/l);const r=s*c.maxW,e=s*i*c.lines.length;return{lines:c.lines,fs:s,wPlane:r,hPlane:e,aspect:r/e}}const K=.1;function J(a,o=4096){const t=a.map(e=>{const m=Math.round(e.px*(1+2*K)),u=Math.round(m/e.layout.aspect);return{w:m,h:u}});let n=1;const f=()=>t.reduce((e,m)=>e+Math.ceil(m.h*n)+2,0),p=()=>Math.max(...t.map(e=>e.w))*n;for(;(f()>o||p()>o)&&n>.25;)n*=.9;const i=Math.ceil(p()),h=Math.max(2,Math.ceil(f())),c=document.createElement("canvas");c.width=i,c.height=h;const s=c.getContext("2d");s.textBaseline="middle";const l=[];let r=0;return a.forEach((e,m)=>{const u=Math.round(t[m].w*n),v=Math.round(t[m].h*n),x=u/(1+2*K),d=e.layout.fs/e.layout.wPlane*x,y=d*(e.st.lead*(e.caps?1.04:1)),w=(u-x)/2,S=(v-y*e.layout.lines.length)/2;e.layout.lines.forEach((k,D)=>{const H=g=>(s.font=L(e.st,e.weight,g.em,d),b(s,e.track*d),s.measureText(e.caps?g.text.toUpperCase():g.text).width+(A?0:e.track*d*g.text.length));s.font=L(e.st,e.weight,!1,d),b(s,0);const C=s.measureText(" ").width+e.track*d,T=k.map(H),E=T.reduce((g,z)=>g+z,0)+C*(k.length-1);let W=w+(e.align==="left"?0:e.align==="right"?x-E:(x-E)/2);const P=r+S+(D+.5)*y;k.forEach((g,z)=>{s.font=L(e.st,e.weight,g.em,d),b(s,e.track*d),s.fillStyle=e.colors(g.em);const $=e.caps?g.text.toUpperCase():g.text;if(A)s.fillText($,W,P);else{let F=W;for(const I of $)s.fillText(I,F,P),F+=s.measureText(I).width+e.track*d}W+=T[z]+C})}),l.push({x:0,y:r/h,w:u/i,h:v/h}),r+=v+2}),{canvas:c,cells:l}}function B(a,o){const t=l=>l<=.04045?l/12.92:Math.pow((l+.055)/1.055,2.4),[n,f,p]=O(a).map(t),i=.2126*n+.7152*f+.0722*p,h=Math.pow(o,2.2),c=Math.max(i,h)+.05,s=Math.min(i,h)+.05;return c/s}function j(a,o){return B(o.light,a)>=B(o.dark,a)?o.light:o.dark}function Q(a,o,t){return B(a,o)<2.2?j(o,t):a}export{K as P,G as W,Q as c,j as i,_ as l,V as p,J as r};
