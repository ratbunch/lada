from operator import itemgetter
from typing import Optional

from lada.lib.ultralytics_utils import disable_ultralytics_telemetry, convert_yolo_boxes
from lada.lib.scene_utils import box_overlap
from lada.lib import Image, Box
from ultralytics import YOLO
import random

disable_ultralytics_telemetry()

MALE_GENITALIA_EXPOSED = 14
FEMALE_GENITALIA_EXPOSED = 4

NSFW_CLASS_IDS = (MALE_GENITALIA_EXPOSED, FEMALE_GENITALIA_EXPOSED)

class NudeNetNsfwDetector:
    def __init__(self, model: YOLO, device):
        self.model = model
        self.device = device

    def detect(self, images:list[Image], boxes:Optional[list[Box]]=None, max_samples=20, min_confidence=0.2, min_positive_detections=4, batch_size=4) -> tuple[bool, bool, bool]:
        if boxes:
            indices_of_nsfw_elements = list(range(len(images)))
            indices_of_nsfw_elements = random.sample(indices_of_nsfw_elements, min(len(images), max_samples))
            samples = itemgetter(*indices_of_nsfw_elements)(images)
            samples_boxes = itemgetter(*indices_of_nsfw_elements)(boxes)
        else:
            samples = random.sample(images, min(len(images), max_samples))
            samples_boxes = None

        batches = [samples[i:i + batch_size] for i in range(0, len(samples), batch_size)]
        positive_detections = 0
        positive_male_detections = 0
        positive_female_detections = 0
        for batch_idx, batch in enumerate(batches):
            batch_prediction_results = self.model.predict(source=batch, stream=False, verbose=False, device=self.device, conf=min_confidence)
            for result_idx, results in enumerate(batch_prediction_results):
                sample_idx = batch_idx * batch_size + result_idx
                detections = results.boxes.conf.size(dim=0)
                if detections == 0:
                    continue
                cls = results.boxes.cls.tolist()
                indices_of_nsfw_elements = [i for i in range(len(cls)) if cls[i] in NSFW_CLASS_IDS]
                if len(indices_of_nsfw_elements) == 0:
                    continue
                conf = results.boxes.conf.tolist()
                detection_boxes = convert_yolo_boxes(results.boxes, results.orig_shape)

                single_image_nsfw_male_detected = False
                single_image_nsfw_female_detected = False
                for i in indices_of_nsfw_elements:
                    if conf[i] > min_confidence and (not samples_boxes or box_overlap(detection_boxes[i], samples_boxes[sample_idx])):
                        if not single_image_nsfw_male_detected:
                            single_image_nsfw_male_detected = cls[i] == MALE_GENITALIA_EXPOSED
                        if not single_image_nsfw_female_detected:
                            single_image_nsfw_female_detected = cls[i] == FEMALE_GENITALIA_EXPOSED
                single_image_nsfw_detected = single_image_nsfw_male_detected or single_image_nsfw_female_detected
                if single_image_nsfw_detected:
                    positive_detections += 1
                if single_image_nsfw_male_detected:
                    positive_male_detections += 1
                if single_image_nsfw_female_detected:
                    positive_female_detections += 1
        nsfw_detected = positive_detections > min_positive_detections
        nsfw_male_detected = positive_male_detections > min_positive_detections
        nsfw_female_detected = positive_female_detections > min_positive_detections
        #print(f"nudenet nsfw detector: nsfw {nsfw_detected}, detected {positive_detections}/{len(samples)}")
        return nsfw_detected, nsfw_male_detected, nsfw_female_detected