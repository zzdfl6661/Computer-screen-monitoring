"""Functional smoke test for the bundled EfficientNet-B0 ONNX checkpoint."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import cv2


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client_package.efficientnet_classifier import EfficientNetB0Probe  # noqa: E402


DEFAULT_IMAGE = ROOT / "eval" / "fixtures" / "synthetic_gameplay.png"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        print(json.dumps({"functional_pass": False, "error": f"cannot read {args.image}"}, ensure_ascii=False))
        return 1

    result = EfficientNetB0Probe().inspect(image, top_k=args.top_k).to_dict()
    result.update({
        "functional_pass": True,
        "test_image": str(args.image.resolve()),
        "ground_truth": "game",
        "game_accuracy": None,
        "accuracy_note": (
            "One image is a functional smoke test, not an accuracy evaluation; "
            "the ImageNet checkpoint has no game/non-game output head."
        ),
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
