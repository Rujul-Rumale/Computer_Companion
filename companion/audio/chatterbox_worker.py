"""
Persistent Chatterbox TTS worker.

Runs in the Python 3.11 Chatterbox venv and communicates with the main app
over newline-delimited JSON on stdin/stdout.
"""
import argparse
import contextlib
import json
import logging
import os
import sys


def _write(payload: dict):
    print(json.dumps(payload), flush=True)


def _load_model(model_name: str, device: str):
    import perth
    import torch

    if getattr(perth, "PerthImplicitWatermarker", None) is None:
        perth.PerthImplicitWatermarker = perth.DummyWatermarker

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    if model_name == "standard":
        from chatterbox.tts import ChatterboxTTS
        with contextlib.redirect_stdout(sys.stderr):
            model = ChatterboxTTS.from_pretrained(device=device)
    else:
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        with contextlib.redirect_stdout(sys.stderr):
            model = ChatterboxTurboTTS.from_pretrained(device=device)

    return model, device


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="turbo", choices=["turbo", "standard"])
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    parser.add_argument("--voice-prompt", default="")
    parser.add_argument("--exaggeration", type=float, default=0.15)
    parser.add_argument("--cfg-weight", type=float, default=0.0)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    logging.getLogger("chatterbox").setLevel(logging.ERROR)

    try:
        model, device = _load_model(args.model, args.device)
        if args.probe:
            _write({"ok": True, "device": device})
            return 0
        print(f"[Chatterbox] loaded {args.model} on {device}", file=sys.stderr, flush=True)
    except Exception as e:
        _write({"ok": False, "error": f"load failed: {e}"})
        return 1

    import torchaudio as ta

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if request.get("command") == "stop":
                _write({"ok": True, "stopped": True})
                break

            text = request["text"]
            output = request["output"]
            voice_prompt = request.get("voice_prompt") or args.voice_prompt or None

            with contextlib.redirect_stdout(sys.stderr):
                if args.model == "turbo":
                    wav = model.generate(
                        text,
                        audio_prompt_path=voice_prompt,
                        temperature=float(request.get("temperature", args.temperature)),
                    )
                else:
                    wav = model.generate(
                        text,
                        audio_prompt_path=voice_prompt,
                        exaggeration=float(request.get("exaggeration", args.exaggeration)),
                        cfg_weight=float(request.get("cfg_weight", args.cfg_weight)),
                        temperature=float(request.get("temperature", args.temperature)),
                    )
            ta.save(output, wav, model.sr)
            _write({"ok": True, "output": output})
        except Exception as e:
            _write({"ok": False, "error": str(e)})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
