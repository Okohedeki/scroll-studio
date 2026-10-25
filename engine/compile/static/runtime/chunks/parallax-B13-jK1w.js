import{g as G,a as J,c as q,j as Q,s as N}from"../index.js";import{p as Z,l as ee,r as te,i as oe,c as ae,W as ne,P as re}from"./worldText-C7zi4fQu.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */const ie=`#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`,se=`#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
#define PAD ${re.toFixed(3)}
${ne}
uniform sampler2D imgA, depA, imgB, depB, mskA, mskB, uText;
uniform vec2 scaleA, scaleB;      // cover-fit uv scale per image
uniform vec3 camA, camB;          // x, y offset and zoom per chapter
uniform float mixAB, strength, focusA, focusB;
uniform float grade;              // 0..1 vignette amount
// the title of each view's chapter, if it has one (type in the world)
uniform float uOnT[2], uInT[2];
uniform int uKindT[2];
uniform mat3 uMT[2];
uniform vec4 uBoxT[2], uCellT[2], uAT[2], uBT[2];

vec3 sampleView(sampler2D img, sampler2D dep, sampler2D msk, vec2 sc, vec3 cam, float focus, int v){
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
  return col;
}
void main(){
  vec3 a = sampleView(imgA, depA, mskA, scaleA, camA, focusA, 0);
  vec3 b = mixAB > 0.001 ? sampleView(imgB, depB, mskB, scaleB, camB, focusB, 1) : a;
  vec3 c = mix(a, b, mixAB);
  float v = smoothstep(1.15, .35, length((uv - .5) * vec2(1.1, 1.)));
  o = vec4(c * mix(1., v, grade), 1.);
}`,ce={dolly:c=>[0,-.01+.02*c,1.04+.1*c],pan:c=>[-.03+.06*c,0,1.08],orbit:c=>[Math.sin((c-.5)*2.4)*.035,Math.cos((c-.5)*2.4)*.012-.01,1.07],rise:c=>[0,.03-.06*c,1.06+.03*c]},le={behind:0,sky:1,surface:2};function me(c){const[p,f,e,x,y,v,B,i,s]=c,b=y*s-v*i,D=-(x*s-v*B),A=x*i-y*B,M=p*b+f*D+e*A;if(Math.abs(M)<1e-12)return null;const d=1/M;return[b*d,-(f*s-e*i)*d,(f*v-e*y)*d,D*d,(p*s-e*B)*d,-(p*v-e*x)*d,A*d,-(p*i-f*B)*d,(p*y-f*x)*d]}const de=async(c,p)=>{const f=document.createElement("canvas");p.visual.appendChild(f);const e=f.getContext("webgl2",{antialias:!1,preserveDrawingBuffer:!0});if(!e)throw new Error("no webgl2");const x=[],y=(t,a)=>{const n=e.createShader(t);if(e.shaderSource(n,a),e.compileShader(n),!e.getShaderParameter(n,e.COMPILE_STATUS))throw new Error(e.getShaderInfoLog(n)||"shader");return n},v=e.createProgram();e.attachShader(v,y(e.VERTEX_SHADER,ie)),e.attachShader(v,y(e.FRAGMENT_SHADER,se)),e.linkProgram(v),e.useProgram(v),e.bindBuffer(e.ARRAY_BUFFER,e.createBuffer()),e.bufferData(e.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),e.STATIC_DRAW);const B=e.getAttribLocation(v,"p");e.enableVertexAttribArray(B),e.vertexAttribPointer(B,2,e.FLOAT,!1,0,0);const i=t=>e.getUniformLocation(v,t),s={imgA:i("imgA"),depA:i("depA"),imgB:i("imgB"),depB:i("depB"),scaleA:i("scaleA"),scaleB:i("scaleB"),camA:i("camA"),camB:i("camB"),mixAB:i("mixAB"),strength:i("strength"),focusA:i("focusA"),focusB:i("focusB"),grade:i("grade"),mskA:i("mskA"),mskB:i("mskB"),uText:i("uText"),on:i("uOnT[0]"),inn:i("uInT[0]"),kind:i("uKindT[0]"),m:i("uMT[0]"),box:i("uBoxT[0]"),cell:i("uCellT[0]"),A:i("uAT[0]"),B:i("uBT[0]")};e.uniform1i(s.imgA,0),e.uniform1i(s.depA,1),e.uniform1i(s.imgB,2),e.uniform1i(s.depB,3),e.uniform1i(s.mskA,4),e.uniform1i(s.mskB,5),e.uniform1i(s.uText,6);function b(t){const a=e.createTexture();return e.bindTexture(e.TEXTURE_2D,a),t?e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,t):e.texImage2D(e.TEXTURE_2D,0,e.RGBA,1,1,0,e.RGBA,e.UNSIGNED_BYTE,new Uint8Array([255,255,255,255])),e.generateMipmap(e.TEXTURE_2D),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR_MIPMAP_LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),a}let D=0;await Promise.all(c.chapters.map(async(t,a)=>{const[n,o,r]=await Promise.all([G(t.image),G(t.depth),t.world?.mask?G(t.world.mask):Promise.resolve(null)]);x[a]={img:b(n),dep:b(o),msk:b(r),w:n.naturalWidth,h:n.naturalHeight,focus:t.focus??.5,move:t.move||c.move||"dolly"},p.progress(++D/c.chapters.length)}));const A=[],M=!J&&c.chapters.some(t=>t.world);let d=null;const u=M?Z(p.section):null;if(M&&u){try{await document.fonts.ready,await document.fonts.load(`${u.weight} 64px ${u.family}`),await document.fonts.load(`italic ${u.weight} 64px ${u.family}`)}catch{}const t=[...p.section.querySelectorAll(".ss-step")];c.chapters.forEach((n,o)=>{const r=n.world,T=p.data.steps[n.step??o];if(!r||!T||!r.m)return;const l=ee(T.title,u,{size:r.box[2],hMax:.3*r.plane[1],lines:r.style.lines??void 0,caps:r.style.caps,track:r.style.track,weight:r.style.weight??u.weight,align:r.style.align});A.push({ch:o,w:r,lay:l,cell:{x:0,y:0,w:0,h:0},enabled:!0,el:t[n.step??o]||null})});const a=(n,o)=>{const r=n.w.style,T=n.w.tone??.5,l=r.color==="ink"?u.ink:r.color==="paper"?u.paper:r.color==="accent"?u.accent:/^#|^rgb/i.test(r.color)?r.color:oe(T,u);return!o||r.color!=="auto"?l:ae(u.emColor,T,u)};if(A.length){const n=te(A.map(o=>({layout:o.lay,px:Math.min(2600,Math.max(256,o.lay.wPlane*2200)),colors:r=>a(o,r),weight:o.w.style.weight??u.weight,track:o.w.style.track,caps:o.w.style.caps,align:o.w.style.align,st:u})));A.forEach((o,r)=>{o.cell=n.cells[r]}),d=n.canvas}}const V=e.createTexture();d&&(e.activeTexture(e.TEXTURE6),e.bindTexture(e.TEXTURE_2D,V),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!0),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,d),e.generateMipmap(e.TEXTURE_2D),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR_MIPMAP_LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),e.pixelStorei(e.UNPACK_PREMULTIPLY_ALPHA_WEBGL,!1));const Y=new Map(A.map(t=>[t.ch,t])),m={on:new Float32Array(2),inn:new Float32Array(2),kind:new Int32Array(2),m:new Float32Array(18),box:new Float32Array(8),cell:new Float32Array(8),A:new Float32Array(8),B:new Float32Array(8)};let U=1,I=1;const L=t=>{const a=U/I,n=t.w/t.h;return a>n?[1,a/n]:[n/a,1]};function K(){for(const t of A){const a=x[t.ch];if(!a)continue;const[n,o]=L(a),r=.5/(n*1.12),T=.5/(o*1.12),l=me(t.w.m);let R=!!l;if(l){const[h,g]=[t.w.box[0],t.w.box[1]],w=t.lay.wPlane/2,k=t.lay.hPlane/2;for(const[_,C]of[[h-w,g-k],[h+w,g-k],[h+w,g+k],[h-w,g+k]]){const z=l[6]*_+l[7]*C+l[8],H=(l[0]*_+l[1]*C+l[2])/z,j=(l[3]*_+l[4]*C+l[5])/z;(Math.abs(H-.5)>r-.01||Math.abs(j-.5)>T-.01)&&(R=!1)}}const E=f.getBoundingClientRect().width*(n>1?n:1);t.lay.fs*E<22&&(R=!1),t.enabled=R,t.el?.classList.toggle("ss-world-on",R)}}function O(){const t=f.getBoundingClientRect(),a=Math.min(devicePixelRatio||1,2);U=f.width=Math.max(1,Math.round(t.width*a)),I=f.height=Math.max(1,Math.round(t.height*a)),e.viewport(0,0,U,I),K()}O(),(window.__ssWorld||={}).live=A;const S=c.chapters.map((t,a)=>t.step??a);let X=0,F=0;const P=(t,a)=>{e.activeTexture(e.TEXTURE0+t),e.bindTexture(e.TEXTURE_2D,a)},$=t=>N(.04,.22,t)*(1-N(.9,1,t));function W(t,a,n){const o=Y.get(a);if(m.on[t]=0,!o||!o.enabled)return;const r=$(n);if(r<.002)return;m.on[t]=r,m.inn[t]=q(n/.35),m.kind[t]=le[o.w.kind],m.m.set([o.w.m[0],o.w.m[3],o.w.m[6],o.w.m[1],o.w.m[4],o.w.m[7],o.w.m[2],o.w.m[5],o.w.m[8]],t*9),m.box.set([o.w.box[0],o.w.box[1],o.lay.wPlane,o.lay.hPlane],t*4),m.cell.set([o.cell.x,o.cell.y,o.cell.w,o.cell.h],t*4);const T=Math.log2(Math.max(1,1+(o.w.blur??(o.w.kind==="surface"?.8:0))*(f.width/1920)*.7));m.A.set([o.w.depth??0,o.w.soft??.04,o.w.style.haze,T],t*4),m.B.set([o.w.style.fog,o.w.style.wear,o.w.style.relief,o.w.tone??.5],t*4)}return{resize:O,update(t){let a=0;for(let w=0;w<S.length;w++)(t.steps[S[w]]??0)>0&&(a=w);a=Math.min(a,c.chapters.length-1);const n=q(t.steps[S[a]]??0),o=Math.max(0,a-1),r=a>0?N(0,.18,n):1,T=x[o],l=x[a];if(!l&&!T)return;X+=(t.mx-X)*.05,F+=(t.my-F)*.05;const R=(w,k)=>{const _=ce[x[w]?.move||"dolly"](Q(q(k)));return[_[0]+X*.02,_[1]+F*.012,_[2]]},E=l&&r>=1?l:T||l,h=l||T,g=E===l?a:o;P(0,E.img),P(1,E.dep),P(2,h.img),P(3,h.dep),P(4,E.msk),P(5,h.msk),e.uniform2fv(s.scaleA,L(E)),e.uniform2fv(s.scaleB,L(h)),e.uniform3fv(s.camA,R(g,g===a?n:1)),e.uniform3fv(s.camB,R(a,n)),e.uniform1f(s.mixAB,E===h?0:r),e.uniform1f(s.focusA,E.focus),e.uniform1f(s.focusB,h.focus),e.uniform1f(s.strength,c.strength??1),e.uniform1f(s.grade,c.vignette??.35),A.length&&(W(0,g,g===a?n:1),W(1,a,n),e.uniform1fv(s.on,m.on),e.uniform1fv(s.inn,m.inn),e.uniform1iv(s.kind,m.kind),e.uniformMatrix3fv(s.m,!1,m.m),e.uniform4fv(s.box,m.box),e.uniform4fv(s.cell,m.cell),e.uniform4fv(s.A,m.A),e.uniform4fv(s.B,m.B)),e.drawArrays(e.TRIANGLE_STRIP,0,4)}}};export{de as default};
