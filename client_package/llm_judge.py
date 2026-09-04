"""
本地文本 LLM 判级（pluggable）。

默认尝试连接本地 ollama（text 模型，如 qwen2.5:1.5b）做 (进程, 标题, 站点) 语义判级；
不可用时回退到离线的“进程 + 站点声誉 + 关键词”启发式判级（零额外依赖，可直接运行）。

接口：TextJudge().judge(running_processes, title, site) -> (label, confidence, reason)
"""
import json
import logging
import urllib.request

try:
    from .config import ConfigManager
except Exception:
    from config import ConfigManager

try:
    from .http_client import urlopen
except Exception:
    from http_client import urlopen

try:
    from .classify import analyze_processes, analyze_title
except Exception:
    from classify import analyze_processes, analyze_title

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是青少年电脑使用监控系统的分类器。给定进程名列表、当前窗口标题、站点名，"
    "判断用户是在\"学习\"还是\"娱乐\"。只输出 JSON："
    "{\"label\":\"study|entertainment|idle\",\"confidence\":0到1之间的小数,"
    "\"reason\":\"简短中文理由\"}。"
)


class TextJudge:
    def __init__(self):
        self.cfg = ConfigManager()
        self.endpoint = self.cfg.get('text_llm_endpoint') or 'http://localhost:11434'
        self.model = self.cfg.get('text_llm_model') or 'qwen2.5:1.5b'

    def judge(self, running_processes=None, title='', site=None):
        try:
            return self._llm_judge(running_processes, title, site)
        except Exception as e:
            logger.warning(f"本地文本LLM不可用，回退启发式判级: {e}")
            return self._heuristic_judge(running_processes, title)

    def _heuristic_judge(self, running_processes, title):
        if running_processes:
            pcat, pconf, _ = analyze_processes(running_processes)
            if pconf > 0:
                return pcat, pconf, 'heuristic(process)'
        tcat, tconf, _, _ = analyze_title(title)
        return tcat, tconf, 'heuristic(title)'

    def _llm_judge(self, running_processes, title, site):
        prompt = (
            SYSTEM_PROMPT
            + f"\n进程: {running_processes}; 窗口标题: {title}; 站点: {site}。"
        )
        payload = {"model": self.model, "prompt": prompt, "format": "json", "stream": False}
        req = urllib.request.Request(
            self.endpoint.rstrip('/') + '/api/generate',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        out = json.loads(data.get('response', '{}'))
        label = out.get('label', 'idle')
        conf = float(out.get('confidence', 0.0))
        return label, conf, out.get('reason', '')
