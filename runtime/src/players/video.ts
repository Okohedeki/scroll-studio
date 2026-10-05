/** film: a short-GOP video scrubbed by scroll progress. */
import type { PlayerFactory } from "../lib/types";
import { follow, isMobile } from "../lib/util";

const factory: PlayerFactory = async (cfg, ctx) => {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.preload = "auto";
  video.src = isMobile() && cfg.videoMobile ? cfg.videoMobile : cfg.video;
  ctx.visual.appendChild(video);

  let duration = 0, current = 0;
  video.addEventListener("loadedmetadata", () => { duration = video.duration; });
  video.addEventListener("loadeddata", () => { video.currentTime = 0.001; });
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
