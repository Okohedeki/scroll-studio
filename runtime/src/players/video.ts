/** film: a short-GOP video scrubbed by scroll progress. The whole file is downloaded first, so seeking is
 * instant and never waits on the network mid-scroll. */
import type { PlayerFactory } from "../lib/types";
import { fetchBlobURL, follow, isMobile } from "../lib/util";

const factory: PlayerFactory = async (cfg, ctx) => {
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

  return {
    update(s) {
      if (!duration) return;
      const target = s.p * (duration - 0.05);
      current += (target - current) * follow;
      if (!video.seeking && Math.abs(video.currentTime - current) > 0.01) video.currentTime = current;
    },
  };
};
export default factory;
