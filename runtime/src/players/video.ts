/** film: a short-GOP video scrubbed by scroll progress. The whole file is downloaded first, so seeking is
 * instant and never waits on the network mid-scroll. */
import type { PlayerFactory } from "../lib/types";
import { fetchBlobURL, follow, isMobile, reducedMotion } from "../lib/util";

const factory: PlayerFactory = async (cfg, ctx) => {
  // reveal: the film drawn through a shader that brings colour into tracked regions (engine/reveal.py), and the pointer's
  // lens or light (`pointer:`, lib/pointer.ts) drawn by the same shader; without WebGL2 (or if anything about it fails) the
  // colour film plays as it is, below
  if (cfg.reveal || ctx.section.querySelector(":scope > .ss-pointer")) {
    try {
      const player = await (await import("./reveal")).default(cfg, ctx);
      if (player) return player;
    } catch (err) { console.warn("[scroll-studio] reveal failed, playing the colour film", err); }
  }
  // the one-take page (engine/journey.py): with reduced motion the stops are stills with their blocks (no film is fetched)
  if (cfg.journey && reducedMotion) return { update() {} };
  // world: titles set inside the film (engine/world.py): the film drawn through a shader that occludes, tracks and paints type;
  // without WebGL2, with reduced motion or if anything fails the film plays as it is and the titles are ordinary captions
  if (cfg.world && !cfg.reveal) {
    try {
      const player = await (await import("./world")).default(cfg, ctx);
      if (player) return player;
    } catch (err) { console.warn("[scroll-studio] world failed, playing the plain film", err); }
  }
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.preload = "auto";
  ctx.visual.appendChild(video);
  const url = isMobile() && cfg.videoMobile ? cfg.videoMobile : cfg.video;
  try {
    video.src = await fetchBlobURL(url, (f) => ctx.progress(f * 0.95), "video/mp4");
  } catch {
    video.src = url;   // e.g. opened from file://: fall back to streaming
  }
  await new Promise<void>((resolve) => {
    if (video.readyState >= 2) return resolve();
    video.addEventListener("loadeddata", () => resolve(), { once: true });
    video.addEventListener("error", () => resolve(), { once: true });
  });
  video.currentTime = 0.001;
  let duration = video.duration || 0, current = 0;
  video.addEventListener("loadedmetadata", () => { duration = video.duration; });
  // iOS only decodes frames for seeking after a user gesture touches the element
  addEventListener("touchstart", () => { video.play().then(() => video.pause()).catch(() => {}); }, { once: true, passive: true });

  const jy = cfg.journey ? (await import("./journey")).attach(cfg.journey, ctx, video) : null;
  return {
    update(s) {
      if (jy) jy.update(s.p);
      if (!duration) return;
      const target = jy ? Math.min(jy.time(s.p), duration - 0.05) : s.p * (duration - 0.05);
      current += (target - current) * follow;
      if (!video.seeking && Math.abs(video.currentTime - current) > 0.01) video.currentTime = current;
    },
  };
};
export default factory;
