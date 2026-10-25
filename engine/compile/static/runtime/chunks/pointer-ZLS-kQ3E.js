import{c as l}from"../index.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */const C={lens:{radius:.2,strength:1},light:{radius:.32,strength:.85}};function P(o){let r=o.replace("#","");return r.length===3&&(r=[...r].map(e=>e+e).join("")),[0,2,4].map(e=>parseInt(r.slice(e,e+2),16)/255)}function D(o,r,e="mono"){const n=o.querySelector(":scope > .ss-pointer");if(!n)return null;let t;try{t=JSON.parse(n.textContent||"{}")}catch{return null}const s=t.mode==="light"?"light":"lens",h=t.layer==="picture"?"picture":"colour",u=C[s];return{mode:s,layer:h,base:s==="light"?"none":t.base??(h==="colour"?e:"none"),radius:t.radius??u.radius,softness:l(t.softness??.35),strength:l(t.strength??u.strength),color:P(t.color||"#ffd7a8"),rest:[l(t.rest?.[0]??.62),l(t.rest?.[1]??.42)],layers:Array.isArray(r?.pointer?.layers)?r.pointer.layers:[]}}function A(o,r,e){const n=(o-e.left)/Math.max(1,e.width),t=(r-e.top)/Math.max(1,e.height);return{u:n,v:t,inside:n>=0&&n<=1&&t>=0&&t<=1}}const M=(o,r)=>o*Math.min(r.width,r.height);function E(o,r){return(M(o,r)+12)/Math.max(1,r.height)}function I(o,r,e){if(!e)return[r[0],r[1]];const n=Math.PI*2/9;return[l(r[0]+.05*Math.sin(o*n)),l(r[1]+.035*Math.sin(o*n*2+.6))]}function R(o,r,e,n){if(!n)return{x:o,y:r,shownH:e.height};const t=Math.max(e.width/n.w,e.height/n.h);return{x:(o-.5)*e.width/(n.w*t)+.5,y:(r-.5)*e.height/(n.h*t)+.5,shownH:n.h*t}}function k(o,r,e,n){const t=R(o[0],o[1],e,n),s=n?n.w/n.h:e.width/Math.max(1,e.height);return{centre:[t.x,t.y],radius:M(r,e)/Math.max(1,t.shownH),aspect:s}}function z(o,r,e){const n=e.target??window,t=[r.rest[0],r.rest[1]];let s=null,h=-1,u=!0;const d=[],f=(c,a)=>{n.addEventListener(c,a,{passive:!0}),d.push(()=>n.removeEventListener(c,a))};if(!e.reduced){f("pointermove",a=>{a.pointerType!=="touch"&&(s={x:a.clientX,y:a.clientY,touch:!1})}),f("pointerout",a=>{!a.relatedTarget&&s&&!s.touch&&(s=null)});const c=a=>{const i=a.touches[0];s=i?{x:i.clientX,y:i.clientY,touch:!0}:null};f("touchstart",c),f("touchmove",c),f("touchend",c),f("touchcancel",()=>{s=null})}function L(c){if(s){const a=o.getBoundingClientRect(),i=A(s.x,s.y,a);if(s.touch)return[l(i.u),l(i.v-E(r.radius,a))];if(i.inside)return[i.u,i.v]}return I(c,r.rest,!e.hover&&!e.reduced)}return{pos:t,update(c){const a=h<0?1:l(c-h,0,.1);if(h=c,e.reduced){const S=u;return u=!1,S}const[i,p]=L(c),m=s?1-Math.exp(-a*18):1-Math.exp(-a*4),g=t[0]+(i-t[0])*m,v=t[1]+(p-t[1])*m,x=Math.abs(i-g)<2e-4&&Math.abs(p-v)<2e-4,w=x?i:g,y=x?p:v,b=u||w!==t[0]||y!==t[1];return t[0]=w,t[1]=y,u=!1,b},dirty(){u=!0},dispose(){d.forEach(c=>c())}}}function F(){return{reduced:matchMedia("(prefers-reduced-motion: reduce)").matches,hover:matchMedia("(hover: hover) and (pointer: fine)").matches}}function $(o){if(o==="mono")return"vec3(dot(c, vec3(0.2126, 0.7152, 0.0722)))";if(o==="dim")return"mix(c, vec3(dot(c, vec3(0.2126, 0.7152, 0.0722))), 0.55) * 0.55";if(o==="blur")return"bl";if(/^#[0-9a-f]{3,6}$/i.test(o)){const[r,e,n]=P(o).map(t=>t.toFixed(4));return`ptrTint(c, vec3(${r}, ${e}, ${n}))`}return"c"}const j=`
uniform vec2 uPtrC; uniform float uPtrR, uPtrAsp, uPtrSoft, uPtrStr; uniform vec3 uPtrCol;
float ptrDist(vec2 p) { return length((p - uPtrC) * vec2(uPtrAsp, 1.0)) / max(uPtrR, 1e-4); }
float ptrLens(vec2 p) { float a = 1.0 - max(uPtrSoft, 0.01); return 1.0 - smoothstep(a, 1.0, ptrDist(p)); }
float ptrFalloff(float d) {
  float s = max(uPtrSoft, 0.01);
  float edge = 1.0 - smoothstep(1.0 - s, 1.0 + s, d);
  float m = min(d, 1.0);
  return max(edge * (1.0 - 0.35 * m * m), 0.45 / (1.0 + 6.0 * d * d));
}
// the lens's rim: a hairline of light at its edge and a faint shadow just outside, so it reads as a lens even where the two
// layers are alike (a grey wall is grey in both)
vec3 ptrRim(vec3 c, vec2 p) {
  float d = ptrDist(p), w = fwidth(d) * 1.2;
  float ring = 1.0 - smoothstep(0.0, w, abs(d - 1.0));
  float shade = smoothstep(1.0, 1.0 + w * 2.0, d) * (1.0 - smoothstep(1.0 + w * 2.0, 1.0 + w * 14.0, d));
  return c * (1.0 - 0.18 * shade) + 0.28 * ring * (1.0 - c);
}
vec3 ptrTint(vec3 c, vec3 t) { float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); return l < 0.5 ? t * (l * 2.0) : t + (1.0 - t) * (l * 2.0 - 1.0); }
vec3 ptrLight(vec3 col, vec2 p, float dep, vec2 grad) {
  float d = ptrDist(p);
  float I = ptrFalloff(d);
  float amb = 1.0 - 0.92 * uPtrStr;
  // the lamp hangs a little in front of the picture, above the pointer; a surface's slope (from the depth gradient) turns it
  // towards or away from the lamp, so light rakes across shapes, and farther things get less of it
  vec3 n = normalize(vec3(-grad / (1.0 + length(grad)), 1.0));     // softly limited: a depth jump (an outline) is not a slope
  vec3 toL = vec3((uPtrC - p) * vec2(uPtrAsp, 1.0), uPtrR * 0.9 + (1.0 - dep) * 0.35);
  vec3 L = normalize(toL);
  float lam = max(dot(n, L), 0.0);
  float shape = clamp(lam / max(L.z, 0.2), 0.0, 1.8);    // 1 on a surface facing the viewer, more where it faces the lamp
  float reach = mix(0.45, 1.0, dep);
  float spec = pow(max(dot(reflect(-L, n), vec3(0.0, 0.0, 1.0)), 0.0), 24.0) * (1.0 - n.z) * 6.0;
  vec3 lit = uPtrCol * I * reach * mix(1.0, shape, 0.7);
  return col * (amb + lit * 1.15) + uPtrCol * clamp(spec, 0.0, 1.0) * I * reach * 0.22;
}
`;export{j as P,$ as b,F as p,D as r,z as t,k as u};
