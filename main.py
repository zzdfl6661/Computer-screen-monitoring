import time
from collections import deque
import logging

from client_package import (
    ConfigManager,
    multimodal_fusion_analysis,
    send_to_server,
    show_popup,
)
from database import DatabaseManager
from logger import setup_logger
from client_package.single_instance import SingleInstance

logger = setup_logger('main')
config_manager = ConfigManager()
local_db = DatabaseManager('client_activity_logs.db')


def main():
    logger.info("学习辅助监控系统启动中...")

    instance = SingleInstance()
    if not instance.acquire():
        logger.warning("监控客户端已在运行，本次启动已取消")
        return

    result_queue = deque(maxlen=5)

    logger.info("使用配置文件启动...")

    check_interval = config_manager.get('check_interval')
    logger.info(f"学习辅助监控系统已启动，检查间隔: {check_interval}秒，按Ctrl+C停止...")

    try:
        while True:
            logger.info("开始新一轮检查...")

            activity_type, meta = multimodal_fusion_analysis(return_meta=True)

            logger.info(f"活动分析结果: {activity_type} (conf={meta['confidence']}, "
                        f"source={meta['decision_source']}, reason={meta['reason']}, "
                        f"process={meta.get('process')!r}, title={meta.get('title')!r})")

            result_queue.append(activity_type)

            should_trigger = False
            if len(result_queue) >= 3:
                recent_3 = list(result_queue)[-3:]
                if all(r == recent_3[0] for r in recent_3):
                    should_trigger = True
                    logger.info(f"连续3次结果一致: {recent_3[0]}")

            response = send_to_server(
                activity_type,
                confidence=meta['confidence'],
                decision_source=meta['decision_source'],
                reason=meta['reason'],
                process=meta.get('process'),
                title=meta.get('title'),
            )
            logger.info(f"响应: {response}")

            # 弹窗只用于"连续 3 次判定娱乐"时友好提醒；
            # 误报/漏报按钮已移除——小孩不会给出准确的反馈，且极易报复性乱选。
            # 后端 /api/feedback 与 Feedback 表保留，供家长端或程序化使用。
            if should_trigger and response.get("status") == "warning":
                logger.info(f"显示警告提示: {response['message']}")
                show_popup(response["message"], activity_type)

            logger.info(f"等待 {check_interval} 秒...")
            time.sleep(check_interval)
    except KeyboardInterrupt:
        logger.info("监控系统已停止")
        local_db.close()
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)
        local_db.close()
    finally:
        instance.release()


if __name__ == "__main__":
    main()
