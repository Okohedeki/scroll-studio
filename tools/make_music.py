"""Generate a music bed locally with MusicGen (stereo large) on the GPU. No API keys.

  D:i\musicgen-venv\Scripts\python.exe tools/make_music.py "<prompt>" out.wav --seconds 40 --seed 3

(The venv reuses system torch but carries a newer mistral_common; the system one breaks transformers' imports.)

MusicGen is trained on 30 s clips, so longer beds are made by continuation: a 30 s seed, then the
model continues from the seed's last 10 s until the target length is reached. Model weights cache to
HF_HOME (default D:\\ai\\hf). Note: the MusicGen weights are licensed CC-BY-NC 4.0 (non-commercial).
"""
import argparse
import os

os.environ.setdefault("HF_HOME", r"D:\ai\hf")

import numpy as np
import soundfile as sf
import torch
from transformers.models.musicgen import MusicgenForConditionalGeneration, MusicgenProcessor

MODEL = os.environ.get("MUSICGEN_MODEL", "facebook/musicgen-stereo-large")
TOKENS_PER_S = 50
SEED_S, CONTEXT_S = 30, 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--guidance", type=float, default=3.0)
    a = ap.parse_args()

    torch.manual_seed(a.seed)
    proc = MusicgenProcessor.from_pretrained(MODEL)
    model = MusicgenForConditionalGeneration.from_pretrained(MODEL, torch_dtype=torch.float16).to("cuda")
    sr = model.config.audio_encoder.sampling_rate
    gen = dict(do_sample=True, guidance_scale=a.guidance, top_k=250)

    first = min(SEED_S, a.seconds)
    inputs = proc(text=[a.prompt], padding=True, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        audio = model.generate(**inputs, max_new_tokens=int(first * TOKENS_PER_S), **gen)[0].float().cpu().numpy()
    print(f"seed: {audio.shape[-1] / sr:.1f}s")

    while audio.shape[-1] / sr < a.seconds:
        ctx = audio[:, -CONTEXT_S * sr:]
        need = min(SEED_S - CONTEXT_S, a.seconds - audio.shape[-1] / sr + 0.5)
        inputs = proc(audio=[ctx], sampling_rate=sr, text=[a.prompt],
                      padding=True, return_tensors="pt")
        inputs = {k: v.to("cuda", torch.float16 if v.dtype.is_floating_point else v.dtype) for k, v in inputs.items()}
        with torch.inference_mode():
            out = model.generate(**inputs, max_new_tokens=int(need * TOKENS_PER_S), **gen)[0].float().cpu().numpy()
        new = out[:, ctx.shape[-1]:]
        audio = np.concatenate([audio, new], axis=-1)
        print(f"continued: {audio.shape[-1] / sr:.1f}s")

    audio = audio[:, : int(a.seconds * sr)]
    peak = np.abs(audio).max() or 1.0
    audio = audio / peak * 0.89                       # about -1 dBFS
    sf.write(a.out, audio.T, sr)
    print(f"wrote {a.out} ({audio.shape[-1] / sr:.1f}s, {sr} Hz, {audio.shape[0]} ch)")


if __name__ == "__main__":
    main()
