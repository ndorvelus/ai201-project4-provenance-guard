"""Run reference image-metadata inputs through the image signals and scorer (stretch: multi-modal).

Usage:  .venv/bin/python scripts/eval_images.py              (prints the table)
        .venv/bin/python scripts/eval_images.py --json NAME  (prints one input as a /submit body)
All metadata below is synthetic.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image_signals import run_all_image  # noqa: E402
from scoring import combine  # noqa: E402

INPUTS = {
    "midjourney_png": {
        "filename": "neon_city.png", "format": "PNG", "width": 1024, "height": 1024,
        "exif": {"software": "Midjourney v6"},
        "description": "A neon-lit city street at night in the rain.",
    },
    "a1111_params_png": {
        "filename": "portrait_0042.png", "format": "PNG", "width": 832, "height": 1216,
        "png_text": {"parameters": "portrait of an old fisherman, dramatic light\nNegative "
                     "prompt: blurry\nSteps: 30, Sampler: DPM++ 2M Karras, CFG scale: 7, "
                     "Seed: 1234567, Model: sdxl_base_1.0"},
    },
    "phone_photo_jpeg": {
        "filename": "IMG_4821.JPG", "format": "JPEG", "width": 4032, "height": 3024,
        "exif": {"make": "Apple", "model": "iPhone 15", "software": "17.4.1",
                 "date_time_original": "2026:10:03 18:22:41", "iso": 64, "f_number": 1.8,
                 "exposure_time": "1/120", "focal_length": 6.86,
                 "lens_model": "iPhone 15 back dual wide camera 6.86mm f/1.6",
                 "gps_latitude": 38.92, "gps_longitude": -77.02},
        "description": "My dog at the park after the rain.",
    },
    "stripped_screenshot": {
        "filename": "Screenshot 2026-11-09.png", "format": "PNG", "width": 1170, "height": 2532,
        "description": "A watercolor of a lighthouse I painted last week.",
    },
    "firefly_composite": {
        "filename": "beach_edit.jpg", "format": "JPEG", "width": 6000, "height": 4000,
        "exif": {"make": "Canon", "model": "Canon EOS R6", "iso": 100, "f_number": 8,
                 "exposure_time": "1/250", "software": "Adobe Photoshop 26.0"},
        "c2pa": {"claim_generator": "Adobe Photoshop",
                 "digital_source_type": "http://cv.iptc.org/newscodes/digitalsourcetype/"
                                        "compositeWithTrainedAlgorithmicMedia"},
    },
}


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--json":
        print(json.dumps({"content_type": "image", "creator_id": "demo-artist",
                          "image": INPUTS[sys.argv[2]]}))
        return
    header = f"{'input':<22}{'gen':>6}{'capt':>6}{'llm':>6}{'ai_lik':>8}{'conf':>6}  attribution"
    print(header)
    print("-" * len(header))
    for name, meta in INPUTS.items():
        sig = run_all_image(meta)
        res = combine(sig, content_type="image")
        llm = sig["llm"]["score"]
        print(
            f"{name:<22}{sig['generator']['score']:>6.2f}{sig['capture']['score']:>6.2f}"
            f"{'n/a' if llm is None else f'{llm:.2f}':>6}"
            f"{res['ai_likelihood']:>8.3f}{res['confidence']:>6.2f}  {res['attribution']}"
            + ("  (signals disagree)" if res["scoring_notes"]["signals_disagree"] else "")
        )
        if llm is None:
            print("    llm error:", sig["llm"]["details"].get("error"))


if __name__ == "__main__":
    main()
