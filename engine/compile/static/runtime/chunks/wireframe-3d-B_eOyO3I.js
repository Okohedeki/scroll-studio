import{I as wn,F as We,a as ve,b as Et,W as Sn,B as we,S as Qe,V as J,c as bn,d as Kt,U as Ze,e as tn,f as Jt,M as Qt,g as kt,L as Mn,h as En,i as zn,j as _n,k as An,l as Cn,P as Ln,H as Tn,D as Pn,m as Ie,G as ht,n as qe,E as He,o as Un,C as Bn,p as $n,q as kn,r as Dn,s as fe,t as Fn,u as On,R as Wn,v as In}from"./three.module-CD7Z97nq.js";import{a as Mt,c as qn,$ as Z,o as Hn,r as tt,h as Se,s as ye,b as Rn}from"./_kit-QzPxajoR.js";import"../index.js";/*! Scroll Studio runtime by Edeki Okoh: https://github.com/Okohedeki/scroll-studio. GNU AGPL-3.0 with the Scroll Studio Output Exception (see NOTICE.md); keep this notice. */const Re=new we,Gt=new J;class xe extends wn{constructor(){super(),this.isLineSegmentsGeometry=!0,this.type="LineSegmentsGeometry";const e=[-1,2,0,1,2,0,-1,1,0,1,1,0,-1,0,0,1,0,0,-1,-1,0,1,-1,0],o=[-1,2,1,2,-1,1,1,1,-1,-1,1,-1,-1,-2,1,-2],c=[0,2,1,2,3,1,2,4,3,4,5,3,4,6,5,6,7,5];this.setIndex(c),this.setAttribute("position",new We(e,3)),this.setAttribute("uv",new We(o,2))}applyMatrix4(e){const o=this.attributes.instanceStart,c=this.attributes.instanceEnd;return o!==void 0&&(o.applyMatrix4(e),c.applyMatrix4(e),o.needsUpdate=!0),this.boundingBox!==null&&this.computeBoundingBox(),this.boundingSphere!==null&&this.computeBoundingSphere(),this}setPositions(e){let o;e instanceof Float32Array?o=e:Array.isArray(e)&&(o=new Float32Array(e));const c=new ve(o,6,1);return this.setAttribute("instanceStart",new Et(c,3,0)),this.setAttribute("instanceEnd",new Et(c,3,3)),this.instanceCount=this.attributes.instanceStart.count,this.computeBoundingBox(),this.computeBoundingSphere(),this}setColors(e){let o;e instanceof Float32Array?o=e:Array.isArray(e)&&(o=new Float32Array(e));const c=new ve(o,6,1);return this.setAttribute("instanceColorStart",new Et(c,3,0)),this.setAttribute("instanceColorEnd",new Et(c,3,3)),this}fromWireframeGeometry(e){return this.setPositions(e.attributes.position.array),this}fromEdgesGeometry(e){return this.setPositions(e.attributes.position.array),this}fromMesh(e){return this.fromWireframeGeometry(new Sn(e.geometry)),this}fromLineSegments(e){const o=e.geometry;return this.setPositions(o.attributes.position.array),this}computeBoundingBox(){this.boundingBox===null&&(this.boundingBox=new we);const e=this.attributes.instanceStart,o=this.attributes.instanceEnd;e!==void 0&&o!==void 0&&(this.boundingBox.setFromBufferAttribute(e),Re.setFromBufferAttribute(o),this.boundingBox.union(Re))}computeBoundingSphere(){this.boundingSphere===null&&(this.boundingSphere=new Qe),this.boundingBox===null&&this.computeBoundingBox();const e=this.attributes.instanceStart,o=this.attributes.instanceEnd;if(e!==void 0&&o!==void 0){const c=this.boundingSphere.center;this.boundingBox.getCenter(c);let p=0;for(let l=0,g=e.count;l<g;l++)Gt.fromBufferAttribute(e,l),p=Math.max(p,c.distanceToSquared(Gt)),Gt.fromBufferAttribute(o,l),p=Math.max(p,c.distanceToSquared(Gt));this.boundingSphere.radius=Math.sqrt(p),isNaN(this.boundingSphere.radius)&&console.error("THREE.LineSegmentsGeometry.computeBoundingSphere(): Computed radius is NaN. The instanced position data is likely to have NaN values.",this)}}toJSON(){}applyMatrix(e){return console.warn("THREE.LineSegmentsGeometry: applyMatrix() has been renamed to applyMatrix4()."),this.applyMatrix4(e)}}Jt.line={worldUnits:{value:1},linewidth:{value:1},resolution:{value:new tn(1,1)},dashOffset:{value:0},dashScale:{value:1},dashSize:{value:1},gapSize:{value:1}};Kt.line={uniforms:Ze.merge([Jt.common,Jt.fog,Jt.line]),vertexShader:`
		#include <common>
		#include <color_pars_vertex>
		#include <fog_pars_vertex>
		#include <logdepthbuf_pars_vertex>
		#include <clipping_planes_pars_vertex>

		uniform float linewidth;
		uniform vec2 resolution;

		attribute vec3 instanceStart;
		attribute vec3 instanceEnd;

		attribute vec3 instanceColorStart;
		attribute vec3 instanceColorEnd;

		#ifdef WORLD_UNITS

			varying vec4 worldPos;
			varying vec3 worldStart;
			varying vec3 worldEnd;

			#ifdef USE_DASH

				varying vec2 vUv;

			#endif

		#else

			varying vec2 vUv;

		#endif

		#ifdef USE_DASH

			uniform float dashScale;
			attribute float instanceDistanceStart;
			attribute float instanceDistanceEnd;
			varying float vLineDistance;

		#endif

		void trimSegment( const in vec4 start, inout vec4 end ) {

			// trim end segment so it terminates between the camera plane and the near plane

			// conservative estimate of the near plane
			float a = projectionMatrix[ 2 ][ 2 ]; // 3nd entry in 3th column
			float b = projectionMatrix[ 3 ][ 2 ]; // 3nd entry in 4th column
			float nearEstimate = - 0.5 * b / a;

			float alpha = ( nearEstimate - start.z ) / ( end.z - start.z );

			end.xyz = mix( start.xyz, end.xyz, alpha );

		}

		void main() {

			#ifdef USE_COLOR

				vColor.xyz = ( position.y < 0.5 ) ? instanceColorStart : instanceColorEnd;

			#endif

			#ifdef USE_DASH

				vLineDistance = ( position.y < 0.5 ) ? dashScale * instanceDistanceStart : dashScale * instanceDistanceEnd;
				vUv = uv;

			#endif

			float aspect = resolution.x / resolution.y;

			// camera space
			vec4 start = modelViewMatrix * vec4( instanceStart, 1.0 );
			vec4 end = modelViewMatrix * vec4( instanceEnd, 1.0 );

			#ifdef WORLD_UNITS

				worldStart = start.xyz;
				worldEnd = end.xyz;

			#else

				vUv = uv;

			#endif

			// special case for perspective projection, and segments that terminate either in, or behind, the camera plane
			// clearly the gpu firmware has a way of addressing this issue when projecting into ndc space
			// but we need to perform ndc-space calculations in the shader, so we must address this issue directly
			// perhaps there is a more elegant solution -- WestLangley

			bool perspective = ( projectionMatrix[ 2 ][ 3 ] == - 1.0 ); // 4th entry in the 3rd column

			if ( perspective ) {

				if ( start.z < 0.0 && end.z >= 0.0 ) {

					trimSegment( start, end );

				} else if ( end.z < 0.0 && start.z >= 0.0 ) {

					trimSegment( end, start );

				}

			}

			// clip space
			vec4 clipStart = projectionMatrix * start;
			vec4 clipEnd = projectionMatrix * end;

			// ndc space
			vec3 ndcStart = clipStart.xyz / clipStart.w;
			vec3 ndcEnd = clipEnd.xyz / clipEnd.w;

			// direction
			vec2 dir = ndcEnd.xy - ndcStart.xy;

			// account for clip-space aspect ratio
			dir.x *= aspect;
			dir = normalize( dir );

			#ifdef WORLD_UNITS

				vec3 worldDir = normalize( end.xyz - start.xyz );
				vec3 tmpFwd = normalize( mix( start.xyz, end.xyz, 0.5 ) );
				vec3 worldUp = normalize( cross( worldDir, tmpFwd ) );
				vec3 worldFwd = cross( worldDir, worldUp );
				worldPos = position.y < 0.5 ? start: end;

				// height offset
				float hw = linewidth * 0.5;
				worldPos.xyz += position.x < 0.0 ? hw * worldUp : - hw * worldUp;

				// don't extend the line if we're rendering dashes because we
				// won't be rendering the endcaps
				#ifndef USE_DASH

					// cap extension
					worldPos.xyz += position.y < 0.5 ? - hw * worldDir : hw * worldDir;

					// add width to the box
					worldPos.xyz += worldFwd * hw;

					// endcaps
					if ( position.y > 1.0 || position.y < 0.0 ) {

						worldPos.xyz -= worldFwd * 2.0 * hw;

					}

				#endif

				// project the worldpos
				vec4 clip = projectionMatrix * worldPos;

				// shift the depth of the projected points so the line
				// segments overlap neatly
				vec3 clipPose = ( position.y < 0.5 ) ? ndcStart : ndcEnd;
				clip.z = clipPose.z * clip.w;

			#else

				vec2 offset = vec2( dir.y, - dir.x );
				// undo aspect ratio adjustment
				dir.x /= aspect;
				offset.x /= aspect;

				// sign flip
				if ( position.x < 0.0 ) offset *= - 1.0;

				// endcaps
				if ( position.y < 0.0 ) {

					offset += - dir;

				} else if ( position.y > 1.0 ) {

					offset += dir;

				}

				// adjust for linewidth
				offset *= linewidth;

				// adjust for clip-space to screen-space conversion // maybe resolution should be based on viewport ...
				offset /= resolution.y;

				// select end
				vec4 clip = ( position.y < 0.5 ) ? clipStart : clipEnd;

				// back to clip space
				offset *= clip.w;

				clip.xy += offset;

			#endif

			gl_Position = clip;

			vec4 mvPosition = ( position.y < 0.5 ) ? start : end; // this is an approximation

			#include <logdepthbuf_vertex>
			#include <clipping_planes_vertex>
			#include <fog_vertex>

		}
		`,fragmentShader:`
		uniform vec3 diffuse;
		uniform float opacity;
		uniform float linewidth;

		#ifdef USE_DASH

			uniform float dashOffset;
			uniform float dashSize;
			uniform float gapSize;

		#endif

		varying float vLineDistance;

		#ifdef WORLD_UNITS

			varying vec4 worldPos;
			varying vec3 worldStart;
			varying vec3 worldEnd;

			#ifdef USE_DASH

				varying vec2 vUv;

			#endif

		#else

			varying vec2 vUv;

		#endif

		#include <common>
		#include <color_pars_fragment>
		#include <fog_pars_fragment>
		#include <logdepthbuf_pars_fragment>
		#include <clipping_planes_pars_fragment>

		vec2 closestLineToLine(vec3 p1, vec3 p2, vec3 p3, vec3 p4) {

			float mua;
			float mub;

			vec3 p13 = p1 - p3;
			vec3 p43 = p4 - p3;

			vec3 p21 = p2 - p1;

			float d1343 = dot( p13, p43 );
			float d4321 = dot( p43, p21 );
			float d1321 = dot( p13, p21 );
			float d4343 = dot( p43, p43 );
			float d2121 = dot( p21, p21 );

			float denom = d2121 * d4343 - d4321 * d4321;

			float numer = d1343 * d4321 - d1321 * d4343;

			mua = numer / denom;
			mua = clamp( mua, 0.0, 1.0 );
			mub = ( d1343 + d4321 * ( mua ) ) / d4343;
			mub = clamp( mub, 0.0, 1.0 );

			return vec2( mua, mub );

		}

		void main() {

			#include <clipping_planes_fragment>

			#ifdef USE_DASH

				if ( vUv.y < - 1.0 || vUv.y > 1.0 ) discard; // discard endcaps

				if ( mod( vLineDistance + dashOffset, dashSize + gapSize ) > dashSize ) discard; // todo - FIX

			#endif

			float alpha = opacity;

			#ifdef WORLD_UNITS

				// Find the closest points on the view ray and the line segment
				vec3 rayEnd = normalize( worldPos.xyz ) * 1e5;
				vec3 lineDir = worldEnd - worldStart;
				vec2 params = closestLineToLine( worldStart, worldEnd, vec3( 0.0, 0.0, 0.0 ), rayEnd );

				vec3 p1 = worldStart + lineDir * params.x;
				vec3 p2 = rayEnd * params.y;
				vec3 delta = p1 - p2;
				float len = length( delta );
				float norm = len / linewidth;

				#ifndef USE_DASH

					#ifdef USE_ALPHA_TO_COVERAGE

						float dnorm = fwidth( norm );
						alpha = 1.0 - smoothstep( 0.5 - dnorm, 0.5 + dnorm, norm );

					#else

						if ( norm > 0.5 ) {

							discard;

						}

					#endif

				#endif

			#else

				#ifdef USE_ALPHA_TO_COVERAGE

					// artifacts appear on some hardware if a derivative is taken within a conditional
					float a = vUv.x;
					float b = ( vUv.y > 0.0 ) ? vUv.y - 1.0 : vUv.y + 1.0;
					float len2 = a * a + b * b;
					float dlen = fwidth( len2 );

					if ( abs( vUv.y ) > 1.0 ) {

						alpha = 1.0 - smoothstep( 1.0 - dlen, 1.0 + dlen, len2 );

					}

				#else

					if ( abs( vUv.y ) > 1.0 ) {

						float a = vUv.x;
						float b = ( vUv.y > 0.0 ) ? vUv.y - 1.0 : vUv.y + 1.0;
						float len2 = a * a + b * b;

						if ( len2 > 1.0 ) discard;

					}

				#endif

			#endif

			vec4 diffuseColor = vec4( diffuse, alpha );

			#include <logdepthbuf_fragment>
			#include <color_fragment>

			gl_FragColor = vec4( diffuseColor.rgb, alpha );

			#include <tonemapping_fragment>
			#include <colorspace_fragment>
			#include <fog_fragment>
			#include <premultiplied_alpha_fragment>

		}
		`};class en extends bn{static get type(){return"LineMaterial"}constructor(e){super({uniforms:Ze.clone(Kt.line.uniforms),vertexShader:Kt.line.vertexShader,fragmentShader:Kt.line.fragmentShader,clipping:!0}),this.isLineMaterial=!0,this.setValues(e)}get color(){return this.uniforms.diffuse.value}set color(e){this.uniforms.diffuse.value=e}get worldUnits(){return"WORLD_UNITS"in this.defines}set worldUnits(e){e===!0?this.defines.WORLD_UNITS="":delete this.defines.WORLD_UNITS}get linewidth(){return this.uniforms.linewidth.value}set linewidth(e){this.uniforms.linewidth&&(this.uniforms.linewidth.value=e)}get dashed(){return"USE_DASH"in this.defines}set dashed(e){e===!0!==this.dashed&&(this.needsUpdate=!0),e===!0?this.defines.USE_DASH="":delete this.defines.USE_DASH}get dashScale(){return this.uniforms.dashScale.value}set dashScale(e){this.uniforms.dashScale.value=e}get dashSize(){return this.uniforms.dashSize.value}set dashSize(e){this.uniforms.dashSize.value=e}get dashOffset(){return this.uniforms.dashOffset.value}set dashOffset(e){this.uniforms.dashOffset.value=e}get gapSize(){return this.uniforms.gapSize.value}set gapSize(e){this.uniforms.gapSize.value=e}get opacity(){return this.uniforms.opacity.value}set opacity(e){this.uniforms&&(this.uniforms.opacity.value=e)}get resolution(){return this.uniforms.resolution.value}set resolution(e){this.uniforms.resolution.value.copy(e)}get alphaToCoverage(){return"USE_ALPHA_TO_COVERAGE"in this.defines}set alphaToCoverage(e){this.defines&&(e===!0!==this.alphaToCoverage&&(this.needsUpdate=!0),e===!0?this.defines.USE_ALPHA_TO_COVERAGE="":delete this.defines.USE_ALPHA_TO_COVERAGE)}}const ue=new kt,je=new J,Ge=new J,F=new kt,O=new kt,ot=new kt,pe=new J,he=new En,W=new Mn,Ne=new J,Nt=new we,Vt=new Qe,at=new kt;let rt,wt;function Ve(f,e,o){return at.set(0,0,-e,1).applyMatrix4(f.projectionMatrix),at.multiplyScalar(1/at.w),at.x=wt/o.width,at.y=wt/o.height,at.applyMatrix4(f.projectionMatrixInverse),at.multiplyScalar(1/at.w),Math.abs(Math.max(at.x,at.y))}function jn(f,e){const o=f.matrixWorld,c=f.geometry,p=c.attributes.instanceStart,l=c.attributes.instanceEnd,g=Math.min(c.instanceCount,p.count);for(let m=0,E=g;m<E;m++){W.start.fromBufferAttribute(p,m),W.end.fromBufferAttribute(l,m),W.applyMatrix4(o);const S=new J,A=new J;rt.distanceSqToSegment(W.start,W.end,A,S),A.distanceTo(S)<wt*.5&&e.push({point:A,pointOnLine:S,distance:rt.origin.distanceTo(A),object:f,face:null,faceIndex:m,uv:null,uv1:null})}}function Gn(f,e,o){const c=e.projectionMatrix,l=f.material.resolution,g=f.matrixWorld,m=f.geometry,E=m.attributes.instanceStart,S=m.attributes.instanceEnd,A=Math.min(m.instanceCount,E.count),H=-e.near;rt.at(1,ot),ot.w=1,ot.applyMatrix4(e.matrixWorldInverse),ot.applyMatrix4(c),ot.multiplyScalar(1/ot.w),ot.x*=l.x/2,ot.y*=l.y/2,ot.z=0,pe.copy(ot),he.multiplyMatrices(e.matrixWorldInverse,g);for(let ct=0,Dt=A;ct<Dt;ct++){if(F.fromBufferAttribute(E,ct),O.fromBufferAttribute(S,ct),F.w=1,O.w=1,F.applyMatrix4(he),O.applyMatrix4(he),F.z>H&&O.z>H)continue;if(F.z>H){const Y=F.z-O.z,et=(F.z-H)/Y;F.lerp(O,et)}else if(O.z>H){const Y=O.z-F.z,et=(O.z-H)/Y;O.lerp(F,et)}F.applyMatrix4(c),O.applyMatrix4(c),F.multiplyScalar(1/F.w),O.multiplyScalar(1/O.w),F.x*=l.x/2,F.y*=l.y/2,O.x*=l.x/2,O.y*=l.y/2,W.start.copy(F),W.start.z=0,W.end.copy(O),W.end.z=0;const Ft=W.closestPointToPointParameter(pe,!0);W.at(Ft,Ne);const Ot=zn.lerp(F.z,O.z,Ft),N=Ot>=-1&&Ot<=1,mt=pe.distanceTo(Ne)<wt*.5;if(N&&mt){W.start.fromBufferAttribute(E,ct),W.end.fromBufferAttribute(S,ct),W.start.applyMatrix4(g),W.end.applyMatrix4(g);const Y=new J,et=new J;rt.distanceSqToSegment(W.start,W.end,et,Y),o.push({point:et,pointOnLine:Y,distance:rt.origin.distanceTo(et),object:f,face:null,faceIndex:ct,uv:null,uv1:null})}}}class Ye extends Qt{constructor(e=new xe,o=new en({color:Math.random()*16777215})){super(e,o),this.isLineSegments2=!0,this.type="LineSegments2"}computeLineDistances(){const e=this.geometry,o=e.attributes.instanceStart,c=e.attributes.instanceEnd,p=new Float32Array(2*o.count);for(let g=0,m=0,E=o.count;g<E;g++,m+=2)je.fromBufferAttribute(o,g),Ge.fromBufferAttribute(c,g),p[m]=m===0?0:p[m-1],p[m+1]=p[m]+je.distanceTo(Ge);const l=new ve(p,2,1);return e.setAttribute("instanceDistanceStart",new Et(l,1,0)),e.setAttribute("instanceDistanceEnd",new Et(l,1,1)),this}raycast(e,o){const c=this.material.worldUnits,p=e.camera;p===null&&!c&&console.error('LineSegments2: "Raycaster.camera" needs to be set in order to raycast against LineSegments2 while worldUnits is set to false.');const l=e.params.Line2!==void 0&&e.params.Line2.threshold||0;rt=e.ray;const g=this.matrixWorld,m=this.geometry,E=this.material;wt=E.linewidth+l,m.boundingSphere===null&&m.computeBoundingSphere(),Vt.copy(m.boundingSphere).applyMatrix4(g);let S;if(c)S=wt*.5;else{const H=Math.max(p.near,Vt.distanceToPoint(rt.origin));S=Ve(p,H,E.resolution)}if(Vt.radius+=S,rt.intersectsSphere(Vt)===!1)return;m.boundingBox===null&&m.computeBoundingBox(),Nt.copy(m.boundingBox).applyMatrix4(g);let A;if(c)A=wt*.5;else{const H=Math.max(p.near,Nt.distanceToPoint(rt.origin));A=Ve(p,H,E.resolution)}Nt.expandByScalar(A),rt.intersectsBox(Nt)!==!1&&(c?jn(this,o):Gn(this,p,o))}onBeforeRender(e){const o=this.material.uniforms;o&&o.resolution&&(e.getViewport(ue),this.material.uniforms.resolution.value.set(ue.z,ue.w))}}const me=Se("bg",657931),Xe=Se("ink",14278115),Nn=2830392,Vn=3817287,ge=Se("accent",5088255),$t=ye("accent","#4da3ff"),L=(f,e=0,o=1)=>Math.min(o,Math.max(e,f)),Yt=(f,e,o)=>f+(e-f)*o,Xt=f=>f*f*(3-2*f),u=(f,e,o)=>new J(f,e,o);function Zn(){const f=Mt("main section.wf-st");if(!f.length)return;const e=document.documentElement;let o;try{o=new _n({antialias:!0,powerPreference:"high-performance"})}catch(t){console.warn("[wireframe-3d] no WebGL; showing the static drawing sheets",t);return}e.classList.add("wf-live");const c=o.domElement;c.className="wf-canvas",c.setAttribute("aria-hidden","true"),document.body.prepend(c);const p=document.createElementNS("http://www.w3.org/2000/svg","svg");p.setAttribute("class","wf-hud"),p.setAttribute("aria-hidden","true"),document.body.appendChild(p),o.setClearColor(me,1);const l=new An;l.fog=new Cn(me,40,190);const g=new Ln(38,innerWidth/innerHeight,.1,600);l.add(new Tn(13162751,1711136,1.6));const m=new Pn(16777215,1.7);m.position.set(12,24,18),l.add(m);const E=[],S=(t,n,i=1)=>{const r=new en({color:t,linewidth:n,transparent:i<1,opacity:i,fog:!0});return E.push(r),r},A=S(Xe,1.35),H=S(ge,1.8),ct=S(Nn,1),Dt=S(Vn,1),zt=S(Xe,1,.55),Ft=S(ge,2),Ot=new Ie({color:me,polygonOffset:!0,polygonOffsetFactor:1,polygonOffsetUnits:1}),N=(t,n)=>{const i=new xe;return i.setPositions(t),new Ye(i,n)},mt=(t,n,i=24)=>{const r=new xe().fromEdgesGeometry(new Fn(t,i));return new Ye(r,n)},Y=(t,n=Ot)=>new Qt(t,n);function et(t,n,i){const r=new On,s=-t/2,h=-n/2;return r.moveTo(s+i,h),r.lineTo(s+t-i,h),r.quadraticCurveTo(s+t,h,s+t,h+i),r.lineTo(s+t,h+n-i),r.quadraticCurveTo(s+t,h+n,s+t-i,h+n),r.lineTo(s+i,h+n),r.quadraticCurveTo(s,h+n,s,h+n-i),r.lineTo(s,h+i),r.quadraticCurveTo(s,h,s+i,h),r}const be={},b=f.map(t=>{const n=t.dataset.wf||"intro",i=be[n]=(be[n]??-1)+1,r=t.querySelector(".wf-call");r&&(n==="intro"||n==="product"||n==="quote")&&r.classList.add("is-right");const s=Mt(".wf-plot",t).map(h=>({el:h,spans:qn(h),last:-1}));return{el:t,kind:n,call:r,plots:s,a:0,b:0,top:0,len:1,travel:0,occ:i,view:t.dataset.view||n,rows:Mt("[data-i]",t),dims:Mt(".wf-dim",t)}}),Zt=b.find(t=>t.kind==="features"),te=Zt?Math.max(1,Zt.rows.length):0,Me=b.find(t=>t.kind==="timeline"),Ee=Me?Math.max(1,Me.rows.length):3;{const t=[],n=[];for(let i=-140;i<=140;i+=4)(i%20===0?n:t).push(i,0,-140,i,0,140,-140,0,i,140,0,i);l.add(N(t,ct),N(n,Dt))}const R={w:7.2,h:15,y:8.1},I=[],ze=new ht;l.add(ze);{const t=new qe(13,.6,7),n=new ht;n.add(Y(t),mt(t,A)),n.position.set(0,.3,0),l.add(n);const i=["glass","display","board","battery","back"],r=Math.max(5,te),s=[.12,.2,.32,.38,.26];let h=.55;for(let y=0;y<r;y++){const d=y%5,x=s[d];h-=x+.02;const C=new ht,T=d===3?5.4:R.w-(d===1?.2:0),z=d===3?9.6:R.h-(d===1?.2:0),j=et(T,z,d===3?.35:1.1),$=new He(j,{depth:x,bevelEnabled:!1,curveSegments:6}),K=Y($),_=new Un({color:d===0?1843755:3817804,roughness:d===0?.25:.6,metalness:.45,transparent:!0,opacity:0}),k=new Qt($,_);k.renderOrder=2;const nt=mt($,A);C.add(K,k,nt);const gt=[],q=x+.01,it=(yt,st,a,v)=>{const M=yt-a/2,U=yt+a/2,G=st-v/2,lt=st+v/2;gt.push(M,G,q,U,G,q,U,G,q,U,lt,q,U,lt,q,M,lt,q,M,lt,q,M,G,q)};if(d===1&&it(0,.2,6.2,13.2),d===2&&(it(-1.6,4.6,2.2,2.2),it(1.4,5,2,1.2),it(1.4,3.4,2,1),it(0,-1.5,5,3.2),it(-2,-5.6,1.2,1.2),it(1.2,-5.6,3,.8)),d===3&&(it(0,0,4.4,8.6),gt.push(-.5,.6,q,.5,.6,q,0,.1,q,0,1.1,q,-.5,-.8,q,.5,-.8,q)),d===4){const yt=new He(et(2.8,2.8,.7),{depth:.3,bevelEnabled:!1,curveSegments:5}),st=new ht;st.add(Y(yt),mt(yt,A)),st.position.set(-1.6,5,-.3),C.add(st);for(const[a,v]of[[-2.2,5.6],[-1,4.4],[-2.2,4.4]]){const M=new Bn(.45,.45,.14,18);M.rotateX(Math.PI/2);const U=new ht;U.add(Y(M),mt(M,A,30)),U.position.set(a,v,-.36),C.add(U)}}gt.length&&C.add(N(gt,zt)),C.position.set(0,R.y,h),ze.add(C);const vt=Zt?.rows[y]?.querySelector("b")?.textContent?.trim();I.push({group:C,edges:nt,occ:K,solid:k,z0:h,t:x,name:(vt||i[d]).toUpperCase(),dims:`${T.toFixed(1)} × ${z.toFixed(1)} × ${x.toFixed(2)}`,idx:y,top:u(T/2,z/2,x)})}}const _e=new $n(Yn());_e.colorSpace=kn;const Ae=new Ie({map:_e,transparent:!0,opacity:0,toneMapped:!1,fog:!1}),Wt=new Qt(new Dn(6.2,13.2),Ae);Wt.position.set(0,.2,.13),I[0].group.add(Wt),Wt.renderOrder=3;const ft=new ht;{ft.add(N([-11/2,0,-5/2,11/2,0,-5/2,11/2,0,-5/2,11/2,0,5/2,11/2,0,5/2,-11/2,0,5/2,-11/2,0,5/2,-11/2,0,-5/2],H));const i=[];for(let r=-11/2;r<11/2;r+=.6)i.push(r,0,-5/2,Math.min(11/2,r+5),0,Math.min(5/2,-5/2+(11/2-r)));ft.add(N(i,S(ge,1,.35))),ft.visible=!1,l.add(ft)}const It=new Map;b.filter(t=>t.kind==="stats").forEach(t=>{const n=u(30,0,-6-t.occ*26),i=[],r=t.dims.map(h=>parseFloat(h.dataset.v||"")),s=Math.max(1e-6,...r.filter(h=>isFinite(h)));r.forEach((h,y)=>{const d=isFinite(h)?h===0?.25:1.6+11*(h/s):6,x=n.x+y*5.2,C=n.z,T=new qe(2.6,d,2.6),z=new ht;z.add(Y(T),mt(T,A)),z.position.set(x,d/2,C),l.add(z);const j=[];for(let k=1;k<d;k+=1)j.push(-1.3,k-d/2,1.31,1.3,k-d/2,1.31);j.length&&z.add(N(j,zt));const $=new ht,K=2.4,_=.35;$.add(N([0,0,0,0,d,0,-K+.2,0,0,.4,0,0,-K+.2,d,0,.4,d,0,-_,_*1.6,0,0,0,0,_,_*1.6,0,0,0,0,-_,d-_*1.6,0,0,d,0,_,d-_*1.6,0,0,d,0],H)),$.position.set(x+1.3+K,0,C+1.3),l.add($),i.push({dim:$,h:d,x:x+1.3+K,z:C+1.3})}),It.set(t,{at:n,towers:i})});const _t=(t,n)=>7*Math.exp(-((t-62)**2+(n-14)**2)/260)+5*Math.exp(-((t-86)**2+(n-44)**2)/220)+3*Math.exp(-((t-44)**2+(n-42)**2)/160);{const t=[];for(let y=.6;y<8;y+=.8)for(let d=26;d<110;d+=1.2)for(let x=0;x<70;x+=1.2){const C=[_t(d,x),_t(d+1.2,x),_t(d+1.2,x+1.2),_t(d,x+1.2)],T=[[d,x],[d+1.2,x],[d+1.2,x+1.2],[d,x+1.2]],z=[];for(let j=0;j<4;j++){const $=C[j],K=C[(j+1)%4];if($<y!=K<y){const _=(y-$)/(K-$),k=T[j],nt=T[(j+1)%4];z.push([Yt(k[0],nt[0],_),Yt(k[1],nt[1],_)])}}z.length>=2&&t.push(z[0][0],y,z[0][1],z[1][0],y,z[1][1]),z.length===4&&t.push(z[2][0],y,z[2][1],z[3][0],y,z[3][1])}l.add(N(t,Dt))}const At=new fe([u(38,0,6),u(50,0,22),u(62,0,30),u(72,0,18),u(84,0,28),u(92,0,52)],!1,"centripetal").getSpacedPoints(160).map(t=>u(t.x,_t(t.x,t.z)+.15,t.z)),Ce=[],Le=[];At.forEach((t,n)=>{if(!n)return;const i=At[n-1];Ce.push(i.x,i.y,i.z,t.x,t.y,t.z),n%2&&Le.push(i.x,i.y,i.z,t.x,t.y,t.z)});const nn=N(Le,zt);l.add(nn);const Te=N(Ce,Ft);l.add(Te);const Ct=[];for(let t=0;t<Ee;t++){const n=At[Math.round((t+.5)/Ee*(At.length-1))],i=[];for(let r=0;r<20;r++){const s=r/20*Math.PI*2,h=(r+1)/20*Math.PI*2;i.push(n.x+Math.cos(s)*1.1,n.y+5,n.z+Math.sin(s)*1.1,n.x+Math.cos(h)*1.1,n.y+5,n.z+Math.sin(h)*1.1)}l.add(N([n.x,n.y,n.z,n.x,n.y+5,n.z,...i],A)),Ct.push(u(n.x,n.y+5,n.z))}const qt=u(0,R.y,0),St=(t,n,i,r)=>{const s=n.clone().applyAxisAngle(u(0,1,0),i*28*Math.PI/180);return{pos:t.clone().add(s),target:t.clone(),fov:r}},sn=(t,n,i,r)=>{const s=r/2/Math.tan(i*Math.PI/360);return{pos:t.clone().add(n.clone().normalize().multiplyScalar(s)),target:t.clone(),fov:i}},P=[],on=u(0,R.y,-1+(Math.max(5,te)-1)*1.2);b.forEach(t=>{switch(t.a=P.length,t.kind){case"hero":P.push(St(qt,u(15,4.5,27),t.occ,38));break;case"intro":P.push(sn(qt.clone().add(u(0,0,0)),u(0,.08,1),9,21));break;case"features":{const n=Math.max(1,te);for(let i=0;i<n;i++)P.push(St(on,u(-26,6,18).applyAxisAngle(u(0,1,0),(i-(n-1)/2)*.12),t.occ,40));break}case"product":P.push(St(u(1.5,R.y+.2,0),u(9,2.5,27),t.occ,34));break;case"stats":{const n=Math.max(1,t.dims.length),i=It.get(t).at;P.push({pos:u(i.x+(n-1)*5.2/2+1.5,6,i.z).add(u(4,7,30+n*2)),target:u(i.x+(n-1)*5.2/2+1.5,6,i.z),fov:38});break}case"timeline":Ct.forEach(n=>P.push({pos:n.clone().add(u(-10,9,16)),target:n.clone().add(u(0,-2,0)),fov:42}));break;case"quote":P.push(St(u(-1.4,R.y+4.6,-.6),u(-9,3,-16),t.occ,36));break;case"faq":P.push({pos:u(30,112,24),target:u(30,0,20),fov:40});break;case"cta":P.push(St(u(-3,R.y-.5,0),u(17,6,31),t.occ,36));break;default:P.push(St(u(-26,4,20),u(10,8,22),t.occ,40))}t.b=P.length-1});const ee=new fe(P.map(t=>t.pos),!1,"centripetal",.5),Pe=new fe(P.map(t=>t.target),!1,"centripetal",.5);P.length===1&&(ee.points.push(P[0].pos.clone()),Pe.points.push(P[0].target.clone()));const an=Math.max(2,ee.points.length);let X=innerWidth,V=innerHeight,Ht=!1,Lt=1;function ne(){X=innerWidth,V=innerHeight,Ht=X<=760,o.setPixelRatio(Math.min(devicePixelRatio||1,Ht?1.5:1.75)),o.setSize(X,V,!1),g.aspect=X/V,Lt=X/V<1?Math.pow(1/(X/V),.7):1,Ht?g.setViewOffset(X,V,0,V*.2,X,V):g.clearViewOffset(),g.updateProjectionMatrix(),E.forEach(t=>t.resolution.set(X,V)),p.setAttribute("viewBox",`0 0 ${X} ${V}`),b.forEach((t,n)=>{const i=t.b-t.a+1,r=t.kind==="hero"?1.3:t.kind==="faq"?1.8:t.kind==="stats"?1.7:t.kind==="product"?1.9:t.kind==="cta"?1.7:1.3+(i-1)*.65;t.el.style.setProperty("--len",r.toFixed(2)),t.travel=n===0?0:Math.min(.42,.75/r)}),b.forEach(t=>{const n=t.el.getBoundingClientRect();t.top=n.top+scrollY,t.len=Math.max(1,n.height)}),Mt(".wf-head").forEach(t=>{t.style.fontSize="";let n=parseFloat(getComputedStyle(t).fontSize),i=0;for(;t.offsetHeight>V*(Ht?.26:.4)&&n>24&&i++<30;)n*=.93,t.style.fontSize=n+"px"}),Ut=!0}function rn(t){let n=0;for(let T=0;T<b.length;T++)t>=b[T].top-1&&(n=T);const i=b[n],r=L((t-i.top)/i.len),s=i.b-i.a+1,h=n>0?b[n-1].b:i.a;if(r<i.travel){const T=r/i.travel;return tt?{u:T<.5?h:i.a,si:T<.5?n-1:n,q:r,stop:0,arrived:T<.5?1:0}:{u:Yt(h,i.a,Xt(T)),si:n,q:r,stop:0,arrived:T}}const y=(r-i.travel)/Math.max(1e-6,1-i.travel)*s,d=Math.min(s-1,Math.floor(y)),x=y-d;let C=i.a+d;return d>0&&x<.35&&!tt&&(C=i.a+d-1+Xt(x/.35)),{u:C,si:n,q:r,stop:d,arrived:1}}const ie=new Wn,Ue=new tn(-9,-9),cn=new In(u(0,1,0),0);let Q=null,Rt=!1,se=0,oe=0,Tt=0,Pt=0;const Be=Z("[data-probe]");addEventListener("pointermove",t=>{Ue.set(t.clientX/X*2-1,-(t.clientY/V)*2+1),Rt&&(Tt=L(Tt-(t.clientX-se)*.004,-.4,.4),Pt=L(Pt+(t.clientY-oe)*.003,-.25,.25),se=t.clientX,oe=t.clientY),ae=!0,Ut=!0},{passive:!0}),c.addEventListener("pointerdown",t=>{t.pointerType==="mouse"&&(Rt=!0,se=t.clientX,oe=t.clientY)}),addEventListener("pointerup",()=>{Rt=!1});let ae=!1;function ln(){if(!ae)return;ae=!1,ie.setFromCamera(Ue,g);const t=ie.intersectObjects(I.map(r=>r.occ),!1)[0],n=t&&I.find(r=>r.occ===t.object)||null;n!==Q&&(Q&&(Q.edges.material=A),Q=n,Ut=!0);const i=new J;Be&&ie.ray.intersectPlane(cn,i)&&(Be.textContent=`X ${i.x.toFixed(2)} · Z ${i.z.toFixed(2)}`)}const ut={view:Z('[data-tb="view"]'),scale:Z('[data-tb="scale"]'),sheet:Z('[data-tb="sheet"]'),rev:Z('[data-tb="rev"]')},$e=Mt(".wf-bar__views [data-k]"),dn=Z(".wf-gizmo .ax-x"),fn=Z(".wf-gizmo .ax-y"),un=Z(".wf-gizmo .ax-z"),pn=Z(".wf-gizmo .t-x"),hn=Z(".wf-gizmo .t-y"),mn=Z(".wf-gizmo .t-z");function ke(t){const n=b[t];return n?n.top+n.len*n.travel+2:0}function De(t){const n=scrollY,i=performance.now(),r=Math.min(1700,500+Math.abs(t-n)*.06),s=h=>{const y=L((h-i)/r);scrollTo(0,n+(t-n)*Xt(y)),y<1&&requestAnimationFrame(s)};requestAnimationFrame(s)}$e.forEach(t=>t.addEventListener("click",n=>{n.preventDefault(),n.stopImmediatePropagation(),De(ke(+(t.dataset.k||0)))},!0)),addEventListener("click",t=>{const n=t.target.closest?.("a[href^='#']");if(!n||n.closest(".wf-bar__views"))return;const i=n.getAttribute("href"),r=i.length>1?b.findIndex(s=>"#"+s.el.id===i):0;r<0||(t.preventDefault(),t.stopImmediatePropagation(),De(i.length>1?ke(r):0))},!0);const gn=performance.now(),vn=scrollY<10;let Ut=!0,Fe=-1,re=-1,ce=0;const jt=new J,Bt=t=>(jt.copy(t).project(g),[(jt.x*.5+.5)*X,(-jt.y*.5+.5)*V,jt.z<1]);function le(t){const n=performance.now(),i=!tt&&vn?L((n-gn-200)/1700):1,r=!Rt&&(Math.abs(Tt)>1e-4||Math.abs(Pt)>1e-4);if(t===Fe&&!Ut&&i>=1&&!r&&ce<=0)return;Fe=t,Ut=!1,r&&(Tt*=.9,Pt*=.9);const s=rn(t),h=b[s.si];if(tt){const a=Math.round(s.u);a!==re&&(re>=0&&(ce=1,c.style.transition="none",c.style.opacity="0",requestAnimationFrame(()=>{c.style.transition="opacity .2s linear",c.style.opacity="1"})),re=a),ce=0}const y=s.u/Math.max(1,an-1),d=ee.getPoint(L(y)),x=Pe.getPoint(L(y)),C=Math.floor(s.u),T=Math.min(P.length-1,C+1);g.fov=Yt(P[Math.min(C,P.length-1)].fov,P[T].fov,s.u-C);const z=d.clone().sub(x).multiplyScalar(Lt).applyAxisAngle(u(0,1,0),Tt);z.length()<15*Lt&&z.setLength(15*Lt);const j=u(0,1,0).cross(z).normalize();z.applyAxisAngle(j,Pt),g.position.copy(x).add(z);{const a=g.position.clone().sub(qt),v=13*Lt;a.length()<v&&g.position.copy(qt).add(a.setLength(v))}g.lookAt(x),g.updateProjectionMatrix();let $=0;b.forEach((a,v)=>{a.kind==="features"&&(v===s.si&&($=Math.max($,tt?1:L((s.q-a.travel*.4)/(a.travel*.6+.08)))),v===s.si-1&&($=Math.max($,tt?0:1-Xt(L(s.q/Math.max(.01,b[s.si].travel))))))});const K=I.length;I.forEach((a,v)=>{a.group.position.z=a.z0+$*(K-1-v)*2.5});let _=0;b.forEach((a,v)=>{a.kind!=="product"&&a.kind!=="cta"||(v===s.si&&(_=Math.max(_,tt?1:L((s.q-a.travel*.7)/.22))),v===s.si-1&&a.kind==="product"&&(_=Math.max(_,tt?0:1-L(s.q/Math.max(.01,b[s.si].travel*.6)))))}),I.forEach(a=>{a.solid.material.opacity=_,a.solid.visible=_>.001}),Ae.opacity=_,Wt.visible=_>.001,A.opacity=1-_*.62,A.transparent=_>0,zt.opacity=.55*(1-_*.7);const k=b.findIndex(a=>a.kind==="intro");if(ft.visible=k>=0&&(s.si===k||s.si===k+1&&s.q<b[s.si].travel*.5),ft.visible){const a=s.si===k?L((s.q-b[k].travel)/(1-b[k].travel)):1;ft.position.set(0,R.y+R.h/2-.5-a*(R.h-1),0)}b.forEach((a,v)=>{const M=It.get(a);if(!M)return;const U=tt?s.si>=v?1:0:v===s.si?L((s.q-a.travel*.8)/.25):v<s.si?1:0;M.towers.forEach((G,lt)=>{G.dim.scale.y=Math.max(.001,L(U*1.4-lt*.12))})});const nt=b.findIndex(a=>a.kind==="timeline");let gt=0;if(nt>=0){const a=b[nt];gt=s.si>nt?1:s.si<nt?0:L((s.u-a.a+.5)/(a.b-a.a+1))}Te.geometry.instanceCount=Math.round(gt*(At.length-1));const q=b.findIndex(a=>a.kind==="features"),it=Q?Q.idx:s.si===q?s.stop:-1;I.forEach((a,v)=>{a.edges.material=v===it?H:A}),o.render(l,g);let vt="";if(b.forEach((a,v)=>{let M=0;v===s.si&&(M=tt?1:L((s.q-a.travel*.86)/Math.max(.03,a.travel*.14+.03))),v===0&&s.si===0&&(M=Math.min(M||1,i)),v===s.si-1&&!tt&&(M=1-L(s.q/Math.max(.01,b[s.si].travel*.3)));const U=M>.01,G=a.call;if(G&&(G.classList.toggle("is-on",U),U&&(G.style.opacity=(a.kind==="stats"?1:L(M*2)).toFixed(3),G.style.clipPath=M>=1||a.kind==="stats"?"":`inset(0 ${((1-L(M*1.6))*100).toFixed(1)}% 0 0)`)),a.plots.forEach(w=>{const B=L((M-.15)/.65);if(B===w.last)return;w.last=B;const D=w.spans.length;w.spans.forEach((dt,xt)=>{const pt=L(B*D*1.15-xt*1.15+1);dt.style.clipPath=pt>=1?"":`inset(0 ${((1-pt)*100).toFixed(0)}% 0 0)`}),w.el.classList.toggle("is-filled",B>=1)}),!U){a.dims.forEach(w=>{w.style.visibility="hidden"});return}const lt=G?.dataset.anchor,Oe=lt?yn(lt,s.stop):null;if(G&&Oe&&M>.6){const[w,B,D]=Bt(Oe);D&&(vt+=xn(G.getBoundingClientRect(),w,B,a.kind==="features"))}if(a.kind==="features"){a.rows.forEach((w,B)=>w.classList.toggle("is-on",B===s.stop&&v===s.si));for(let w=0;w<Math.min(a.rows.length,I.length);w++){const B=I[w],[D,dt,xt]=Bt(B.group.localToWorld(B.top.clone()));if(!xt)continue;const pt=w===s.stop&&v===s.si,bt=D+34,de=dt-26-w*4;vt+=`<path class="${pt?"acc":""}" d="M${D} ${dt} L${bt-10} ${de}"/><circle class="dot" cx="${D}" cy="${dt}" r="2"/><circle class="bal${pt?" is-on":""}" cx="${bt}" cy="${de}" r="11"/><text class="baltext${pt?" is-on":""}" x="${bt}" y="${de+4}">${w+1}</text>`}}a.kind==="timeline"&&(a.rows.forEach((w,B)=>{w.classList.toggle("is-on",B===s.stop),w.classList.toggle("is-ahead",B>s.stop)}),Ct.forEach((w,B)=>{const[D,dt,xt]=Bt(w);xt&&(vt+=`<text x="${D+10}" y="${dt-8}" ${B===s.stop?`style="fill:${$t}"`:""}>WP${String(B+1).padStart(2,"0")}</text>`)})),a.kind==="stats"&&a.dims.forEach((w,B)=>{const D=It.get(a)?.towers[B];if(!D){w.style.visibility="hidden";return}const[dt,xt,pt]=Bt(u(D.x,D.h*Math.max(.001,D.dim.scale.y)*.5,D.z)),bt=pt&&D.dim.scale.y>.3;w.style.visibility=bt?"":"hidden",bt&&(w.style.transform=`translate(${(dt+14).toFixed(1)}px, ${(xt-w.offsetHeight/2).toFixed(1)}px)`),w.style.opacity=L((D.dim.scale.y-.3)/.5).toFixed(3)})}),Q){const[a,v,M]=Bt(Q.group.localToWorld(u(-3.6,R.h/2,Q.t)));M&&(vt+=`<path class="acc" d="M${a} ${v} L${a-30} ${v-30} H${a-60}"/><text x="${a-64}" y="${v-36}" text-anchor="end" style="fill:${$t}">${Q.name} · ${Q.dims}</text>`)}p.innerHTML=vt,ut.view&&(ut.view.textContent=h.view),ut.sheet&&(ut.sheet.textContent=`${s.si+1} OF ${b.length}`),ut.scale&&(ut.scale.textContent="1:"+(g.position.distanceTo(x)/10).toFixed(1)),ut.rev&&(ut.rev.textContent="ABCDEFGHJKLMNP"[Math.min(13,s.si)]),$e.forEach(a=>a.classList.toggle("is-on",+(a.dataset.k||-1)===s.si));const yt=g.quaternion.clone().invert(),st=(a,v,M)=>{const U=a.applyQuaternion(yt);v?.setAttribute("x2",(U.x*18).toFixed(1)),v?.setAttribute("y2",(-U.y*18).toFixed(1)),M?.setAttribute("x",(U.x*23-3).toFixed(1)),M?.setAttribute("y",(-U.y*23+3).toFixed(1))};st(u(1,0,0),dn,pn),st(u(0,1,0),fn,hn),st(u(0,0,1),un,mn)}function yn(t,n){switch(t){case"top":return u(R.w*.25,R.y+R.h/2,I[0].group.position.z+.2);case"cut":return ft.position.clone().add(u(5.5,0,2.5));case"screen":return I[0].group.localToWorld(u(2.2,-1,.2));case"p0":{const i=I[Math.min(n,I.length-1)];return i.group.localToWorld(u(-7.2/2,0,i.t))}case"w0":return Ct[Math.min(n,Ct.length-1)]||null;case"bump":return I[Math.min(4,I.length-1)].group.localToWorld(u(-1.6,5,-.5));case"plan":return u(0,.6,3.5)}return null}function xn(t,n,i,r){const s=n>t.right,h=n<t.left,y=s?t.right:h?t.left:t.left+t.width/2,d=s||h?L(i,t.top+20,t.bottom-20):i<t.top?t.top:t.bottom,x=s?y+28:h?y-28:y,C=s||h?d:d+(i<t.top?-24:24);return`<path class="${r?"acc":""}" d="M${y} ${d} L${x} ${C} L${n} ${i}"/><circle class="dot" cx="${n}" cy="${i}" r="3"/><circle cx="${n}" cy="${i}" r="7" style="fill:none"/>`}ne(),addEventListener("resize",()=>{ne(),le(scrollY)}),document.fonts?.ready.then(()=>{ne(),le(scrollY)}),Hn(({y:t})=>{ln(),le(t)})}function Yn(){const f=document.createElement("canvas");f.width=620,f.height=1320;const e=f.getContext("2d");e.fillStyle="#0d1015",e.fillRect(0,0,f.width,f.height);const o=document.querySelector("[data-device] .ss-app"),c=E=>o?.querySelector(E)?.textContent?.trim()||"",p=(E,S,A="Archivo, sans-serif")=>`${E} ${S}px ${A}`;e.fillStyle=ye("ink","#d9dde3"),e.font=p(500,26,"JetBrains Mono, monospace"),e.fillText("9:41",40,64);let l=150;e.fillStyle=$t,e.font=p(500,26,"JetBrains Mono, monospace"),e.fillText((c(".ss-app__name")||"APP").toUpperCase(),40,l),l+=76,e.fillStyle="#ffffff",e.font=p(700,60),l=Ke(e,c(".ss-app__title")||"Your screen",40,l,540,66)+30,e.fillStyle="#9aa3ad",e.font=p(500,24,"JetBrains Mono, monospace"),e.fillText((c(".ss-app__label")||"").toUpperCase(),40,l),l+=44,e.fillStyle="#c9ced6",e.font=p(400,28),l=Ke(e,c(".ss-app__note"),40,l,540,38)+34;const g=o?[...o.querySelectorAll(".ss-app__opt")]:[];(g.length?g:[null,null,null]).forEach(E=>{const S=!!E?.classList.contains("is-on");e.strokeStyle=S?$t:"#3a3f47",e.lineWidth=S?4:2,e.fillStyle=S?Rn("accent","#4da3ff",.12):"rgba(255,255,255,.03)",Je(e,40,l,540,130,22),e.fill(),e.stroke(),e.fillStyle=S?ye("accent2","#9cc9ff"):"#e6e9ee",e.font=p(600,36),e.fillText(E?.querySelector("b")?.textContent||"—",70,l+58),e.fillStyle="#8f98a3",e.font=p(400,26),e.fillText(E?.querySelector("small")?.textContent||"",70,l+100),l+=152});const m=c(".ss-app__btn");return m&&(e.fillStyle=$t,Je(e,40,f.height-190,540,110,55),e.fill(),e.fillStyle="#04101f",e.font=p(700,34),e.textAlign="center",e.fillText(m,310,f.height-122),e.textAlign="left"),f}function Ke(f,e,o,c,p,l){if(!e)return c;const g=e.split(/\s+/);let m="";for(const E of g){const S=m?m+" "+E:E;f.measureText(S).width>p&&m?(f.fillText(m,o,c),m=E,c+=l):m=S}return m&&(f.fillText(m,o,c),c+=l),c}function Je(f,e,o,c,p,l){f.beginPath(),f.moveTo(e+l,o),f.arcTo(e+c,o,e+c,o+p,l),f.arcTo(e+c,o+p,e,o+p,l),f.arcTo(e,o+p,e,o,l),f.arcTo(e,o,e+c,o,l),f.closePath()}export{Zn as default};
