import cv2
import numpy as np


class ImagePreprocessor:
    def __init__(self, input_size=(224, 224), mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)):
        self.input_size = input_size
        self.mean = np.array(mean, dtype=np.float32)
        self.std = np.array(std, dtype=np.float32)

    def preprocess(self, image):
        if isinstance(image, np.ndarray):
            img = image.copy()
        else:
            img = np.array(image)

        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

        img = cv2.resize(img, self.input_size, interpolation=cv2.INTER_LINEAR)

        img = img.astype(np.float32) / 255.0

        img = (img - self.mean) / self.std

        img = np.transpose(img, (2, 0, 1))

        img = np.expand_dims(img, axis=0)

        return img

    def preprocess_from_file(self, file_path):
        img = cv2.imread(file_path)
        if img is None:
            raise ValueError(f"无法读取图像文件: {file_path}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return self.preprocess(img)
