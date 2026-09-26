# EfficientNet-B0 model source

This directory contains Qualcomm AI Hub's pre-exported float ONNX asset for
EfficientNet-B0 v0.62.2. It is based on TorchVision's
`EfficientNet_B0_Weights.IMAGENET1K_V1` checkpoint.

- Source model: https://github.com/qualcomm/ai-hub-models/tree/v0.62.2/src/qai_hub_models/models/efficientnet_b0
- Export metadata: https://huggingface.co/qualcomm/EfficientNet-B0
- Source asset: `efficientnet_b0-onnx-float.zip`
- Archive SHA-256: `50CABE0A4E9AD5ABED7329778B345753CB7B452F0D81A8539CEC102C12C1B63A`
- Input: RGB float32 `[1, 3, 224, 224]`, value range `[0, 1]`
- Output: 1000 ImageNet logits

The bundled `efficientnet_b0_opencv.onnx` is a deterministic compatibility copy
of that source asset. It adds the `kernel_shape` attribute inferred from each
Conv weight tensor because OpenCV 4.12 requires that attribute explicitly, and
embeds the source asset's external weights into one file to avoid an OpenCV
external-data parsing incompatibility. Operations and values are unchanged.

This is a generic ImageNet object classifier, not a trained game detector. It
is bundled as a lightweight backbone and smoke-testable inference path. A
fine-tuned binary head and a labeled validation set are required before its
output can influence `study` / `entertainment` decisions.
