import{c as I,l as y,e as L,s as F}from"../index.js";const G=`#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x * .5 + .5, .5 - p.y * .5); gl_Position = vec4(p, 0., 1.); }`,N=`#version 300 es
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
}`,C={dolly:r=>[0,-.01+.02*r,1.04+.1*r],pan:r=>[-.03+.06*r,0,1.08],orbit:r=>[Math.sin((r-.5)*2.4)*.035,Math.cos((r-.5)*2.4)*.012-.01,1.07],rise:r=>[0,.03-.06*r,1.06+.03*r]},O=async(r,_)=>{const l=document.createElement("canvas");_.visual.appendChild(l);const e=l.getContext("webgl2",{antialias:!1,preserveDrawingBuffer:!0});if(!e)throw new Error("no webgl2");const p=[],w=(a,t)=>{const o=e.createShader(a);if(e.shaderSource(o,t),e.compileShader(o),!e.getShaderParameter(o,e.COMPILE_STATUS))throw new Error(e.getShaderInfoLog(o)||"shader");return o},n=e.createProgram();e.attachShader(n,w(e.VERTEX_SHADER,G)),e.attachShader(n,w(e.FRAGMENT_SHADER,N)),e.linkProgram(n),e.useProgram(n),e.bindBuffer(e.ARRAY_BUFFER,e.createBuffer()),e.bufferData(e.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,1,1]),e.STATIC_DRAW);const D=e.getAttribLocation(n,"p");e.enableVertexAttribArray(D),e.vertexAttribPointer(D,2,e.FLOAT,!1,0,0);const i=a=>e.getUniformLocation(n,a),c={imgA:i("imgA"),depA:i("depA"),imgB:i("imgB"),depB:i("depB"),scaleA:i("scaleA"),scaleB:i("scaleB"),camA:i("camA"),camB:i("camB"),mixAB:i("mixAB"),strength:i("strength"),focusA:i("focusA"),focusB:i("focusB"),grade:i("grade")};e.uniform1i(c.imgA,0),e.uniform1i(c.depA,1),e.uniform1i(c.imgB,2),e.uniform1i(c.depB,3);function P(a){const t=e.createTexture();return e.bindTexture(e.TEXTURE_2D,t),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,a),e.generateMipmap(e.TEXTURE_2D),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MIN_FILTER,e.LINEAR_MIPMAP_LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_MAG_FILTER,e.LINEAR),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_S,e.CLAMP_TO_EDGE),e.texParameteri(e.TEXTURE_2D,e.TEXTURE_WRAP_T,e.CLAMP_TO_EDGE),t}for(let a=0;a<r.chapters.length;a++){const t=r.chapters[a],o=async()=>{const[s,v]=await Promise.all([y(t.image),y(t.depth)]);p[a]={img:P(s),dep:P(v),w:s.naturalWidth,h:s.naturalHeight,focus:t.focus??.5,move:t.move||r.move||"dolly"}};a===0?await o():o()}let h=1,g=1;function M(){const a=l.getBoundingClientRect(),t=Math.min(devicePixelRatio||1,2);h=l.width=Math.max(1,Math.round(a.width*t)),g=l.height=Math.max(1,Math.round(a.height*t)),e.viewport(0,0,h,g)}M();const U=a=>{const t=h/g,o=a.w/a.h;return t>o?[1,t/o]:[o/t,1]},E=_.data.steps.map((a,t)=>a.intro?-1:t).filter(a=>a>=0);let T=0,B=0;const A=(a,t)=>{e.activeTexture(e.TEXTURE0+a),e.bindTexture(e.TEXTURE_2D,t)};return{resize:M,update(a){let t=0;for(let f=0;f<E.length;f++)(a.steps[E[f]]??0)>0&&(t=f);t=Math.min(t,r.chapters.length-1);const o=I(a.steps[E[t]]??0),s=Math.max(0,t-1),v=t>0?F(0,.18,o):1,R=p[s],m=p[t];if(!m&&!R)return;T+=(a.mx-T)*.05,B+=(a.my-B)*.05;const S=(f,X)=>{const x=C[p[f]?.move||"dolly"](L(I(X)));return[x[0]+T*.02,x[1]+B*.012,x[2]]},u=m&&v>=1?m:R||m,d=m||R,b=u===m?t:s;A(0,u.img),A(1,u.dep),A(2,d.img),A(3,d.dep),e.uniform2fv(c.scaleA,U(u)),e.uniform2fv(c.scaleB,U(d)),e.uniform3fv(c.camA,S(b,b===t?o:1)),e.uniform3fv(c.camB,S(t,o)),e.uniform1f(c.mixAB,u===d?0:v),e.uniform1f(c.focusA,u.focus),e.uniform1f(c.focusB,d.focus),e.uniform1f(c.strength,r.strength??1),e.uniform1f(c.grade,r.vignette??.35),e.drawArrays(e.TRIANGLE_STRIP,0,4)}}};export{O as default};
