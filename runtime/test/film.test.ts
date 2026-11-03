/** Film helpers: a video scrubbed rather than played, and a group of videos seeked to the same frame and drawn only when all have landed. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/lib/util", async (orig) => ({ ...(await orig<typeof import("../src/lib/util")>()), fetchBlobURL: vi.fn() }));
import { fetchBlobURL } from "../src/lib/util";
import { beatFocusAt, beatIndexAt, focusCss, loadVideo, makeVideo, PairedSeeker, type FilmBeat } from "../src/lib/film";

/** A video that records the times it was told to seek to, and lands only when the test says so. */
class FakeVideo extends EventTarget {
  writes: number[] = [];
  private t = 0;
  get currentTime() { return this.t; }
  set currentTime(v: number) { this.t = v; this.writes.push(v); }
  land() { this.dispatchEvent(new Event("seeked")); }
}
const fake = (n: number) => Array.from({ length: n }, () => new FakeVideo());
const asVideos = (v: FakeVideo[]) => v as unknown as HTMLVideoElement[];

describe("makeVideo", () => {
  it("is muted, inline and preloading: it is scrubbed, never played", () => {
    const v = makeVideo();
    expect(v.muted).toBe(true);
    expect(v.playsInline).toBe(true);
    expect(v.preload).toBe("auto");
  });
});

describe("PairedSeeker", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("seeks every video to the middle of the frame, and reports only once all have landed", () => {
    const vids = fake(2), landed: number[] = [];
    const s = new PairedSeeker(asVideos(vids), 24, (f) => landed.push(f));
    s.seek(12);
    expect(vids.map((v) => v.writes)).toEqual([[12.5 / 24], [12.5 / 24]]);
    expect(s.busy).toBe(true);
    vids[0].land();
    expect(landed).toEqual([]);
    expect(s.busy).toBe(true);
    vids[1].land();
    expect(landed).toEqual([12]);
    expect(s.busy).toBe(false);
    expect(s.shown).toBe(12);
  });

  it("a video already on the frame lands without a seek", async () => {
    const [v] = fake(1), landed: number[] = [];
    v.currentTime = 3.5 / 24; v.writes.length = 0;
    const s = new PairedSeeker(asVideos([v]), 24, (f) => landed.push(f));
    s.seek(3);
    expect(v.writes).toEqual([]);
    await Promise.resolve();
    expect(landed).toEqual([3]);
  });

  it("a newer seek replaces an older one: the old frame is never reported", () => {
    const vids = fake(1), landed: number[] = [];
    const s = new PairedSeeker(asVideos(vids), 10, (f) => landed.push(f));
    s.seek(1);
    s.seek(5);
    vids[0].land();       // both listeners fire; only the newest seek may finish
    expect(landed).toEqual([5]);
    expect(s.shown).toBe(5);
  });

  it("never deadlocks on a seek that does not report: after 800 ms the frame counts as landed", () => {
    const vids = fake(2), landed: number[] = [];
    const s = new PairedSeeker(asVideos(vids), 24, (f) => landed.push(f));
    s.seek(7);
    vi.advanceTimersByTime(799);
    expect(s.busy).toBe(true);
    vi.advanceTimersByTime(2);
    expect(landed).toEqual([7]);
    expect(s.busy).toBe(false);
    vids[0].land(); vids[1].land();     // a late report does not report twice
    expect(landed).toEqual([7]);
  });

  it("reports once even when the timeout and the last landing both come", () => {
    const vids = fake(1), landed: number[] = [];
    const s = new PairedSeeker(asVideos(vids), 24, (f) => landed.push(f));
    s.seek(2);
    vids[0].land();
    vi.advanceTimersByTime(2000);
    expect(landed).toEqual([2]);
  });
});

describe("loadVideo", () => {
  const video = () => document.createElement("video");

  it("sets the source to a blob URL of the whole file, and waits for the first frame", async () => {
    vi.mocked(fetchBlobURL).mockResolvedValue("blob:film");
    const v = video(), progress = vi.fn();
    let done = false;
    const p = loadVideo(v, "/film.mp4", progress).then(() => { done = true; });
    await vi.waitFor(() => expect(v.getAttribute("src")).toBe("blob:film"));
    expect(fetchBlobURL).toHaveBeenCalledWith("/film.mp4", progress, "video/mp4");
    await Promise.resolve();
    expect(done).toBe(false);
    v.dispatchEvent(new Event("loadeddata"));
    await p;
    expect(done).toBe(true);
  });

  it("falls back to streaming the URL when the download fails (opened from file://)", async () => {
    vi.mocked(fetchBlobURL).mockRejectedValue(new Error("nope"));
    const v = video();
    const p = loadVideo(v, "film.mp4", () => {});
    await vi.waitFor(() => expect(v.getAttribute("src")).toBe("film.mp4"));
    v.dispatchEvent(new Event("error"));       // a video that cannot load does not hold the page up either
    await p;
  });

  it("resolves at once for a video that already has data", async () => {
    vi.mocked(fetchBlobURL).mockResolvedValue("blob:x");
    const v = video();
    Object.defineProperty(v, "readyState", { value: 4 });
    await loadVideo(v, "/a.mp4", () => {});
  });
});

describe("beats of a story film", () => {
  const b = (id: string, p0: number, p1: number, focus: [number, number] | null): FilmBeat => ({ id, p0, p1, focus, still: id + ".jpg" });

  it("no beat with a focus: no crop point at all, so the film stays as it was", () => {
    expect(beatFocusAt([b("a", 0, 0.5, null), b("b", 0.5, 1, null)], 0.3)).toBeNull();
    expect(beatFocusAt([], 0.3)).toBeNull();
  });

  it("a beat without its own focus looks at the centre", () => {
    expect(beatFocusAt([b("a", 0, 0.5, [0.9, 0.1]), b("b", 0.5, 1, null)], 0.7)).toEqual([0.5, 0.5]);
  });

  it("a hard cut jumps from one point to the next", () => {
    const beats = [b("a", 0, 0.5, [0.9, 0.5]), b("b", 0.5, 1, [0.1, 0.5])];
    expect(beatFocusAt(beats, 0.4999)).toEqual([0.9, 0.5]);
    expect(beatFocusAt(beats, 0.5)).toEqual([0.1, 0.5]);
  });

  it("through a dissolve the point eases from one beat's to the next", () => {
    const beats = [b("a", 0, 0.6, [1, 0]), b("b", 0.4, 1, [0, 1])];
    expect(beatFocusAt(beats, 0.4)).toEqual([1, 0]);
    const mid = beatFocusAt(beats, 0.5)!;
    expect(mid[0]).toBeCloseTo(0.5, 9);
    expect(mid[1]).toBeCloseTo(0.5, 9);
    expect(beatFocusAt(beats, 0.6)).toEqual([0, 1]);
    const early = beatFocusAt(beats, 0.42)![0];
    expect(early).toBeGreaterThan(0.95);               // eased: it leaves slowly
  });

  it("the still on screen is the last beat that has begun", () => {
    const beats = [b("a", 0, 0.4, null), b("b", 0.35, 0.7, null), b("c", 0.7, 1, null)];
    expect([0, 0.34, 0.35, 0.69, 0.7, 1].map((p) => beatIndexAt(beats, p))).toEqual([0, 0, 1, 1, 2, 2]);
  });

  it("a point as CSS object-position", () => {
    expect(focusCss([0.25, 0.755])).toBe("25.0% 75.5%");
  });
});
