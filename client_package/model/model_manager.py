import os
import json
import logging
import hashlib
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'models')
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_MODEL_DIR, 'model_config.json')


class ModelManager:
    def __init__(self, model_dir=None, config_file=None):
        self.model_dir = model_dir or DEFAULT_MODEL_DIR
        self.config_file = config_file or DEFAULT_CONFIG_FILE
        self.config = self._load_config()
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.model_dir, exist_ok=True)

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                return self._get_default_config()
        return self._get_default_config()

    def _get_default_config(self):
        return {
            'model_name': 'mobilenetv3-lite',
            'version': '1.0.0',
            'download_url': 'https://trae-api-cn.mchost.guru/api/ide/v1/model_download/',
            'model_filename': 'mobilenetv3-lite.onnx',
            'checksum': '',
            'labels': ['study', 'gaming', 'video', 'social', 'idle'],
            'input_size': [224, 224],
            'mean': [0.485, 0.456, 0.406],
            'std': [0.229, 0.224, 0.225]
        }

    def get_model_path(self):
        return os.path.join(self.model_dir, self.config.get('model_filename', 'model.onnx'))

    def model_exists(self):
        model_path = self.get_model_path()
        return os.path.exists(model_path) and os.path.getsize(model_path) > 0

    def get_current_version(self):
        version_file = os.path.join(self.model_dir, 'version.json')
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('version', 'unknown')
            except Exception as e:
                logger.error(f"读取版本文件失败: {e}")
        return 'unknown'

    def _compute_checksum(self, file_path, hash_algorithm='sha256'):
        hash_obj = hashlib.new(hash_algorithm)
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    def _verify_checksum(self, file_path):
        expected_checksum = self.config.get('checksum', '')
        if not expected_checksum:
            return True
        actual_checksum = self._compute_checksum(file_path)
        return actual_checksum == expected_checksum

    def download_model(self, progress_callback=None):
        model_path = self.get_model_path()
        download_url = urljoin(self.config['download_url'], self.config['model_filename'])

        logger.info(f"开始下载模型: {download_url}")

        try:
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(model_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = (downloaded_size / total_size) * 100
                            progress_callback(progress)

            logger.info(f"模型下载完成: {model_path}")

            if not self._verify_checksum(model_path):
                logger.warning("模型校验和不匹配，可能下载不完整")

            self._save_version()

            return True

        except requests.RequestException as e:
            logger.error(f"模型下载失败: {e}")
            if os.path.exists(model_path):
                os.remove(model_path)
            return False

    def _save_version(self):
        version_file = os.path.join(self.model_dir, 'version.json')
        version_data = {
            'version': self.config.get('version', '1.0.0'),
            'download_time': None,
            'model_name': self.config.get('model_name', '')
        }
        try:
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(version_data, f, indent=2)
        except Exception as e:
            logger.error(f"保存版本信息失败: {e}")

    def check_for_update(self):
        config_url = urljoin(self.config['download_url'], 'model_config.json')
        try:
            response = requests.get(config_url, timeout=10)
            response.raise_for_status()
            remote_config = response.json()

            local_version = self.get_current_version()
            remote_version = remote_config.get('version', '0.0.0')

            if self._version_compare(remote_version, local_version) > 0:
                logger.info(f"检测到新版本: {remote_version} (当前: {local_version})")
                return remote_config
            else:
                logger.info(f"当前版本已是最新: {local_version}")
                return None

        except requests.RequestException as e:
            logger.warning(f"检查更新失败: {e}")
            return None

    def update_model(self):
        remote_config = self.check_for_update()
        if remote_config:
            self.config = remote_config
            self._save_config()
            return self.download_model()
        return False

    def _save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    @staticmethod
    def _version_compare(v1, v2):
        parts1 = list(map(int, v1.split('.')))
        parts2 = list(map(int, v2.split('.')))
        max_len = max(len(parts1), len(parts2))
        parts1 += [0] * (max_len - len(parts1))
        parts2 += [0] * (max_len - len(parts2))
        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        return 0

    def ensure_model(self, auto_update=True):
        if not self.model_exists():
            logger.info("模型文件不存在，开始下载...")
            return self.download_model()

        if auto_update:
            remote_config = self.check_for_update()
            if remote_config:
                logger.info("发现新版本，开始更新...")
                return self.update_model()

        return True
