import time
import typing as t
from functools import cached_property

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.framework.formats import landmark_pb2


class BaseLandmarkerApp:
    landmarks_type = None

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.cap = cv2.VideoCapture(0)
        self.history = []

    @cached_property
    def landmarker(
        self,
    ) -> mp.tasks.vision.PoseLandmarker | mp.tasks.vision.FaceLandmarker:
        raise NotImplementedError(
            "landmarker property must be implemented in subclasses"
        )

    @cached_property
    def connections_list(self) -> t.List[t.FrozenSet[t.Tuple[int, int]]]:
        raise NotImplementedError(
            "connections_list property must be implemented in subclasses"
        )

    @cached_property
    def drawing_specs_list(
        self,
    ) -> t.List[t.Dict[str, mp.solutions.drawing_utils.DrawingSpec]]:
        raise NotImplementedError(
            "drawing_specs property must be implemented in subclasses"
        )

    def run(self, streamlit_mode: bool = False) -> np.ndarray | None:
        t0 = time.time()
        while self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                break

            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)

            detection_result = self.landmarker.detect(image)
            landmark_list_raw = getattr(detection_result, self.landmarks_type)
            landmark_list = landmark_list_raw[0] if landmark_list_raw else []

            t = time.time() - t0
            self.history.append(
                {"time": t, "landmarks": landmark_list},
            )

            annotated_image = image.numpy_view()
            self.annotate_time(image=annotated_image, timestamp=t)
            self.annotate_landmarks(
                image=annotated_image,
                connections_list=self.connections_list,
                landmark_list=landmark_list,
                drawing_specs_list=self.drawing_specs_list,
            )

            if streamlit_mode:
                yield annotated_image
            else:
                cv2.imshow("Landmarker", annotated_image)

            if cv2.waitKey(1) & 0xFF == ord("\x1b"):
                break

        self.cap.release()
        cv2.destroyAllWindows()

    @classmethod
    def normalize_landmark_list(
        cls, landmark_list: mp.tasks.vision.PoseLandmarkerResult
    ) -> landmark_pb2.NormalizedLandmarkList:
        normalized_landmark_list = landmark_pb2.NormalizedLandmarkList()
        normalized_landmark_list.landmark.extend(
            [
                landmark_pb2.NormalizedLandmark(
                    x=landmark.x,
                    y=landmark.y,
                    z=landmark.z,
                )
                for landmark in landmark_list
            ]
        )
        return normalized_landmark_list

    @classmethod
    def annotate_landmarks(
        cls,
        image: np.ndarray,
        connections_list: t.List[t.FrozenSet[t.Tuple[int, int]]],
        landmark_list: mp.tasks.vision.PoseLandmarkerResult
        | mp.tasks.vision.FaceLandmarkerResult,
        drawing_specs_list: t.List[t.Dict[str, mp.solutions.drawing_utils.DrawingSpec]],
    ) -> None:
        if not landmark_list:
            return image
        normalized_landmark_list = cls.normalize_landmark_list(landmark_list)

        for connections, drawing_specs in zip(connections_list, drawing_specs_list):
            mp.solutions.drawing_utils.draw_landmarks(
                image=image,
                landmark_list=normalized_landmark_list,
                connections=connections,
                **drawing_specs,
            )

    @classmethod
    def annotate_time(cls, image: np.ndarray, timestamp: float):
        cv2.putText(
            img=image,
            text=f"{timestamp:.3f}s",
            org=(10, 60),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=2,
            color=(0, 0, 0),
            thickness=3,
            lineType=cv2.LINE_AA,
        )
