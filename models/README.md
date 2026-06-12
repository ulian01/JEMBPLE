# Models

The object/obstacle demos need a TFLite SSD-MobileNet COCO model plus its label
map. They aren't checked in (binary). Download them here:

```bash
cd models

# Quantized SSD MobileNet V2, COCO (≈6 MB, CPU-friendly on the Pi 5)
wget -O ssd_mobilenet_v2_coco_quant.tflite \
  https://storage.googleapis.com/download.tensorflow.org/models/tflite/coco_ssd_mobilenet_v1_1.0_quant_2018_06_29.zip
# (the file above is a zip; unzip and rename detect.tflite if needed)
# Alternatively use any TFLite SSD model with [boxes, classes, scores, count] outputs.
```

If you have the **Raspberry Pi AI Kit (Hailo-8L)**, set
`object_detection.backend: hailo` in `config.yaml` and implement the HailoRT
pipeline in `sightline/detector.py` (a stub is provided). The Hailo path runs
YOLO-class models at 30+ FPS instead of the CPU's handful.

`coco_labels.txt` (the 80-class COCO label map, one label per line) is included
alongside this file.
