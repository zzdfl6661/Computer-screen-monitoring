import onnxruntime as ort
import numpy as np
import logging
import time
from .image_preprocessor import ImagePreprocessor

logger = logging.getLogger(__name__)

CLASS_LABELS = ['study', 'gaming', 'video', 'social', 'idle']


class ONNXClassifier:
    def __init__(self, model_path, session_options=None):
        self.model_path = model_path
        self.preprocessor = ImagePreprocessor()
        self.session = None
        self.input_name = None
        self.output_name = None
        self._load_model(session_options)

    def _load_model(self, session_options=None):
        try:
            if session_options is None:
                session_options = ort.SessionOptions()
                session_options.intra_op_num_threads = 4
                session_options.inter_op_num_threads = 2
                session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self.session = ort.InferenceSession(
                self.model_path,
                sess_options=session_options,
                providers=['CPUExecutionProvider']
            )

            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name

            input_shape = self.session.get_inputs()[0].shape
            logger.info(f"模型加载成功: {self.model_path}")
            logger.info(f"输入名称: {self.input_name}, 输入形状: {input_shape}")
            logger.info(f"输出名称: {self.output_name}")

        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise

    def predict(self, image):
        start_time = time.time()

        try:
            input_tensor = self.preprocessor.preprocess(image)

            outputs = self.session.run(
                [self.output_name],
                {self.input_name: input_tensor}
            )

            predictions = outputs[0]

            probabilities = self._softmax(predictions[0])

            predicted_class_index = np.argmax(probabilities)
            predicted_label = CLASS_LABELS[predicted_class_index]
            confidence = float(probabilities[predicted_class_index])

            inference_time = time.time() - start_time
            logger.info(f"推理完成: {predicted_label} (置信度: {confidence:.4f}, 耗时: {inference_time:.4f}s)")

            return {
                'label': predicted_label,
                'confidence': confidence,
                'probabilities': {label: float(prob) for label, prob in zip(CLASS_LABELS, probabilities)},
                'inference_time': inference_time
            }

        except Exception as e:
            logger.error(f"推理失败: {e}")
            return {
                'label': 'idle',
                'confidence': 0.0,
                'probabilities': {label: 0.2 for label in CLASS_LABELS},
                'inference_time': time.time() - start_time
            }

    def predict_from_file(self, file_path):
        input_tensor = self.preprocessor.preprocess_from_file(file_path)
        return self.predict(input_tensor)

    @staticmethod
    def _softmax(logits):
        exp_logits = np.exp(logits - np.max(logits))
        return exp_logits / np.sum(exp_logits)

    def close(self):
        if self.session is not None:
            del self.session
            self.session = None

    def __del__(self):
        self.close()
