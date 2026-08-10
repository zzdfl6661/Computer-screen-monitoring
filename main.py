import pytesseract
import numpy as np
import time
from collections import deque
import logging

from client_package import (
    ConfigManager,
    multimodal_fusion_analysis,
    send_to_server,
    show_popup,
    send_feedback
)
from database import DatabaseManager
from logger import setup_logger

logger = setup_logger('main')
config_manager = ConfigManager()
local_db = DatabaseManager('client_activity_logs.db')


def main():
    logger.info("学习辅助监控系统启动中...")
    
    tesseract_available = False
    try:
        test_img = np.zeros((100, 100, 3), dtype=np.uint8)
        test_text = pytesseract.image_to_string(test_img)
        tesseract_available = True
        logger.info("Tesseract-OCR 初始化成功，使用多模态融合识别模式")
    except Exception as e:
        logger.warning(f"Tesseract-OCR 初始化失败: {e}")
        logger.info("将使用降级模式（进程+窗口标题检测）继续运行")
    
    result_queue = deque(maxlen=5)
    
    logger.info("使用配置文件启动...")
    
    check_interval = config_manager.get('check_interval')
    logger.info(f"学习辅助监控系统已启动，检查间隔: {check_interval}秒，按Ctrl+C停止...")
    
    try:
        while True:
            logger.info("开始新一轮检查...")
            
            activity_type = multimodal_fusion_analysis(tesseract_available)
            
            logger.info(f"活动分析结果: {activity_type}")
            
            result_queue.append(activity_type)
            
            should_trigger = False
            if len(result_queue) >= 3:
                recent_3 = list(result_queue)[-3:]
                if all(r == recent_3[0] for r in recent_3):
                    should_trigger = True
                    logger.info(f"连续3次结果一致: {recent_3[0]}")
            
            response = send_to_server(activity_type)
            logger.info(f"响应: {response}")

            if should_trigger and response.get("status") == "warning":
                logger.info(f"显示警告提示: {response['message']}")
                feedback_result = show_popup(response["message"], activity_type)
                
                if feedback_result.get('type'):
                    logger.info(f"用户提交反馈: {feedback_result['type']}, 检测活动: {activity_type}")
                    
                    if feedback_result['type'] == 'false_positive':
                        actual_activity = 'study'
                    elif feedback_result['type'] == 'false_negative':
                        actual_activity = 'entertainment'
                    else:
                        actual_activity = activity_type
                    
                    feedback_response = send_feedback(
                        detected_activity=activity_type,
                        actual_activity=actual_activity,
                        feedback_type=feedback_result['type']
                    )
                    logger.info(f"反馈提交结果: {feedback_response}")
            
            logger.info(f"等待 {check_interval} 秒...")
            time.sleep(check_interval)
    except KeyboardInterrupt:
        logger.info("监控系统已停止")
        local_db.close()
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)
        local_db.close()


if __name__ == "__main__":
    main()
