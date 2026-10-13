# Pokémon recognition model

`pokemon_classifier.onnx` is a per-channel INT8 dynamic-quantized ONNX export of
[`skshmjn/Pokemon-classifier-gen9-1025`](https://huggingface.co/skshmjn/Pokemon-classifier-gen9-1025)
at revision `9e8d54de136b99afc212322eae13ddc07a6fd779`. The upstream model is
Apache-2.0 licensed and has 1,025 output classes. Quantization reduced the model
from 346,603,098 bytes to 90,050,846 bytes.

`pokemon_labels.json` keeps the model's output order and maps class names to the
IDs and names in this project's `pokemon.db`. It covers all 1,024 database
species. The upstream Pecharunt class has no database entry and maps to `null`.

The model takes a 224 × 224 RGB image normalized to [-1, 1]. It is loaded lazily
when the first photo is scanned and runs through ONNX Runtime's CPU provider.
The model card reports 92.2% validation accuracy, but that figure is from the
upstream evaluation set. Accuracy after quantization, accuracy on this camera's
target image types, and inference time and memory use on the Pi Zero 2 W have not
been measured.
