import{e as I,c as y,g as F,s as G}from"../index.js";const N=`#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`,C=`#version 300 es
precision highp float;
in vec2 uv; out vec4 o;
uniform sampler2D imgA, depA, imgB, depB;
uniform vec2 scaleA, scaleB;      // cover-fit uv scale per image
uniform vec3 camA, camB;          // x, y offset and zoom per chapter
uniform float mixAB, strength, focusA, focusB;
uniform float grade;              // 0..1 vignette amount

vec3 sampleView(sampler2D img, sampler2D dep, vec2 sc, vec3 cam, float focus){
  vec2 c = (uv - .5) / (sc * cam.z) + .5;
  vec2 dir = cam.xy * strength;
  // solve uv' + (d(uv') - focus) * dir = c by fixed-point iteration: near pixels move further
  vec2 q = c;
  for (int i = 0; i < 6; i++) {
    float d = texture(dep, q).r;
    q = c - (d - focus) * dir;
  }
  return texture(img, clamp(q, vec2(.001), vec2(.999))).rgb;
}
void main(){
  vec3 a = sampleView(imgA, depA, scaleA, camA, focusA);
  vec3 b = mixAB > 0.001 ? sampleView(imgB, depB, scaleB, camB, focusB) : a;
  vec3 c = mix(a, b, mixAB);
  float v = smoothstep(1.15, .35, length((uv - .5) * vec2(1.1, 1.)));
  o = vec4(c * mix(1., v, grade), 1.);
}`,V={dolly:r=>[0,-.01+.02*r,1.04+.1*r],pan:r=>[-.03+.06*r,0,1.08],orbit:r=>[Math.sin((r-.5)*2.4)*.035,Math.cos((r-.5)*2.4)*.012-.01,1.07],rise:r=>[0,.03-.06*r,1.06+.03*r]},q=async(r,x)=>{const f=document.createElement("canvas");x.visual.appendChild(f);const e=f.getContext("webgl2",{antialias:!1,preserveDrawingBuffer:!0});if(!e)throw new Error("no webgl2");const p=[],_=(a,t)=>{const o=e.createShader(a);if(e.shaderSource(o,t),e.compileShader(o),!e.getShaderParameter(o,e.COMPILE_STATUS))throw new Error(e.getShaderInfoLog(o)||"shader");return o},n=e.createProgram();e.attachShader(n,_(e.VERTEX_SHADER,N)),e.attachShader(n,_(e.FRAGMENT_SHADER,C)),e.linkProgram(n),e.useProgram(n),e.bindBuffer(e.ARRAY_BUFFER,e.createBuffer()),e.bufferData(e.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),e.STATIC_DRAW);const P=e.getAttribLocation(n,"p");e.enableVertexAttribArray(P),e.vertexAttribPointer(P,2,e.FLOAT,!1,0,0);const i=a=>e.getUniformLocation(n,a),c={imgA:i("imgA"),depA:i("depA"),imgB:i("imgB"),depB:i("depB"),scaleA:i("scaleA"),scaleB:i("scaleB"),camA:i("camA"),camB:i("camB"),mixAB:i("mixAB"),strength:i("strength"),focusA:i("focusA"),focusB:i("focusB"),grade:i("grade")};e.uniform1i(c.imgA,0),e.uniform1i(c.depA,1),e.uniform1i(c.imgB,2),e.uniform1i(c.depB,3);function w(a){const t=e.createTexture();return e.bindTexture(e.TEXTURE_2D,t),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,a),e.generateMipmap(e.TEXTURE_2D),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR_MIPMAP_LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),t}let X=0;await Promise.all(r.chapters.map(async(a,t)=>{const[o,A]=await Promise.all([I(a.image),I(a.depth)]);p[t]={img:w(o),dep:w(A),w:o.naturalWidth,h:o.naturalHeight,focus:a.focus??.5,move:a.move||r.move||"dolly"},x.progress(++X/r.chapters.length)}));let v=1,g=1;function D(){const a=f.getBoundingClientRect(),t=Math.min(devicePixelRatio||1,2);v=f.width=Math.max(1,Math.round(a.width*t)),g=f.height=Math.max(1,Math.round(a.height*t)),e.viewport(0,0,v,g)}D();const M=a=>{const t=v/g,o=a.w/a.h;return t>o?[1,t/o]:[o/t,1]},h=r.chapters.map((a,t)=>a.step??t);let E=0,T=0;const d=(a,t)=>{e.activeTexture(e.TEXTURE0+a),e.bindTexture(e.TEXTURE_2D,t)};return{resize:D,update(a){let t=0;for(let u=0;u<h.length;u++)(a.steps[h[u]]??0)>0&&(t=u);t=Math.min(t,r.chapters.length-1);const o=y(a.steps[h[t]]??0),A=Math.max(0,t-1),U=t>0?G(0,.18,o):1,B=p[A],s=p[t];if(!s&&!B)return;E+=(a.mx-E)*.05,T+=(a.my-T)*.05;const S=(u,L)=>{const R=V[p[u]?.move||"dolly"](F(y(L)));return[R[0]+E*.02,R[1]+T*.012,R[2]]},m=s&&U>=1?s:B||s,l=s||B,b=m===s?t:A;d(0,m.img),d(1,m.dep),d(2,l.img),d(3,l.dep),e.uniform2fv(c.scaleA,M(m)),e.uniform2fv(c.scaleB,M(l)),e.uniform3fv(c.camA,S(b,b===t?o:1)),e.uniform3fv(c.camB,S(t,o)),e.uniform1f(c.mixAB,m===l?0:U),e.uniform1f(c.focusA,m.focus),e.uniform1f(c.focusB,l.focus),e.uniform1f(c.strength,r.strength??1),e.uniform1f(c.grade,r.vignette??.35),e.drawArrays(e.TRIANGLE_STRIP,0,4)}}};export{q as default};
