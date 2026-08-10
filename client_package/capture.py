import pyautogui
import numpy as np
import cv2

def capture_screen():
    screenshot = pyautogui.screenshot()
    img = np.array(screenshot)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img
