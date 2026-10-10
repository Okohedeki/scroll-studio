/**
 * Heading and number effects. Text nodes are split in place (inline markup such as <em> and <br> is kept), and
 * the effect plays on the element's "fx:seen" event (first time on screen).
 *
 *   kinetic   each letter is wrapped (.fx-ch, --i = its index) inside words that clip; CSS raises them
 *   flap      each character becomes a split-flap tile that cycles through the board's alphabet, then settles
 *   scramble  characters decode from random glyphs, left to right
 */
const BOARD = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
const GLYPHS = "!<>-_\\/[]{}=+*^?#%&$01";

function eachText(el: HTMLElement, fn: (text: string) => Node) {
  const walk = (node: Node) => {
    if (node.nodeType === 3) node.parentNode!.replaceChild(fn(node.textContent || ""), node);
    else if (!(node as HTMLElement).matches?.("sup")) [...node.childNodes].forEach(walk);
  };
  [...el.childNodes].forEach(walk);
}

function kinetic(el: HTMLElement) {
  let i = 0;
  eachText(el, (text) => {
    const frag = document.createDocumentFragment();
    text.split(/(\s+)/).forEach((part) => {
      if (!part) return;
      if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
      const word = document.createElement("span");
      word.className = "fx-word";
      for (const ch of part) {
        const s = document.createElement("span");
        s.className = "fx-ch";
        s.style.setProperty("--i", String(i++));
        s.textContent = ch;
        word.appendChild(s);
      }
      frag.appendChild(word);
    });
    return frag;
  });
  el.setAttribute("aria-label", el.textContent || "");
}

function tiles(el: HTMLElement): { s: HTMLElement; ch: string }[] {
  const out: { s: HTMLElement; ch: string }[] = [];
  const label = el.textContent || "";
  eachText(el, (text) => {
    // tiles are grouped per word (no wrapping inside a word); the spaces between words stay breakable
    const frag = document.createDocumentFragment();
    text.split(/(\s+)/).forEach((part) => {
      if (!part) return;
      if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
      const word = document.createElement("span");
      word.className = "fx-word";
      for (const ch of part) {
        const s = document.createElement("span");
        s.className = "fx-flap";
        s.textContent = ch;
        word.appendChild(s);
        out.push({ s, ch });
      }
      frag.appendChild(word);
    });
    return frag;
  });
  el.setAttribute("aria-label", label);
  return out;
}

function flap(el: HTMLElement) {
  const cells = tiles(el);
  el.addEventListener("fx:seen", () => {
    cells.forEach(({ s, ch }, i) => {
      const up = ch.toUpperCase(), target = BOARD.indexOf(up);
      // each tile runs a few flips (more for letters further along the alphabet), staggered left to right
      const flips = 2 + (target >= 0 ? target % 4 : 1) + (i % 2);
      let k = 0;
      setTimeout(function step() {
        if (k >= flips) { s.textContent = ch; s.classList.remove("fx-flip"); return; }
        s.textContent = BOARD[(Math.max(0, target) - flips + k + BOARD.length * 2) % BOARD.length];
        s.classList.remove("fx-flip"); void s.offsetWidth; s.classList.add("fx-flip");
        k++;
        setTimeout(step, 55);
      }, i * 18);
    });
  }, { once: true });
}

function scramble(el: HTMLElement) {
  const cells: { s: HTMLElement; ch: string }[] = [];
  const label = el.textContent || "";
  eachText(el, (text) => {
    const frag = document.createDocumentFragment();
    text.split(/(\s+)/).forEach((part) => {
      if (!part) return;
      if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
      const word = document.createElement("span");
      word.style.whiteSpace = "nowrap";
      for (const ch of part) {
        const s = document.createElement("span");
        s.textContent = ch;
        word.appendChild(s);
        cells.push({ s, ch });
      }
      frag.appendChild(word);
    });
    return frag;
  });
  el.setAttribute("aria-label", label);
  cells.forEach(({ s }) => { s.style.opacity = "0"; });
  el.addEventListener("fx:seen", () => {
    const t0 = performance.now(), dur = 500 + cells.length * 22;
    const tick = (now: number) => {
      const done = (now - t0) / dur;
      cells.forEach(({ s, ch }, i) => {
        const at = i / cells.length;
        if (done > at + 0.25) { s.textContent = ch; s.style.opacity = "1"; }
        else if (done > at) { s.textContent = GLYPHS[(Math.random() * GLYPHS.length) | 0]; s.style.opacity = "1"; }
      });
      if (done < 1.3) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, { once: true });
}

export function prepare(kind: string, heads: HTMLElement[], nums: HTMLElement[]) {
  const fn = kind === "kinetic" ? kinetic : kind === "flap" ? flap : kind === "scramble" ? scramble : null;
  if (!fn) return;
  const targets = kind === "kinetic" ? heads : [...heads, ...nums];
  targets.forEach((el) => {
    if (el.dataset.fxDone) return;
    el.dataset.fxDone = "1";
    const seen = el.classList.contains("fx-seen");
    fn(el);
    if (seen && kind !== "kinetic") el.dispatchEvent(new CustomEvent("fx:seen"));
  });
  if (kind === "kinetic") {
    // headings already seen before the split still get to rise: drop the class, add it back a frame later
    heads.forEach((h) => h.classList.remove("fx-seen"));
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      requestAnimationFrame(() => requestAnimationFrame(() => e.target.classList.add("fx-seen")));
    }), { threshold: 0.2 });
    heads.forEach((h) => io.observe(h));
  }
}
