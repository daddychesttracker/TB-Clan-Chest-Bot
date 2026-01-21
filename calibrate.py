import cv2
import pyautogui
import numpy as np
import time
import os

def calibrate():
    print("--- 📏 CALIBRATION MODE ---")
    print("1. Open your Game to the GIFTS PAGE (Make sure chests are visible).")
    print("2. I will wait 5 seconds, then take a screenshot.")
    time.sleep(5)

    if not os.path.exists("assets/btn_claim.png"):
        print("❌ Error: 'assets/btn_claim.png' is missing!")
        return

    # Take screenshot
    screenshot = pyautogui.screenshot()
    img_rgb = np.array(screenshot)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    
    # Find 'Claim' buttons
    template = cv2.imread("assets/btn_claim.png", 0)
    w, h = template.shape[::-1]
    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    loc = np.where(res >= 0.8) # 80% confidence
    
    # Draw boxes
    count = 0
    for pt in zip(*loc[::-1]):
        if count > 0: break # Only show the first one to keep it clean
        
        # --- ADJUST THESE NUMBERS IF THE BOX IS WRONG ---
        OFFSET_X = 520   # How far LEFT of the button to look
        WIDTH = 400      # How wide the text area is
        OFFSET_Y = 60    # Shift up/down
        HEIGHT = 90      # Height of text area
        # -----------------------------------------------

        # Green Box = Button
        cv2.rectangle(img_rgb, pt, (pt[0] + w, pt[1] + h), (0, 255, 0), 2)
        
        # Red Box = Text Area
        text_x = pt[0] - OFFSET_X
        text_y = pt[1] - OFFSET_Y
        cv2.rectangle(img_rgb, (text_x, text_y), (text_x + WIDTH, text_y + HEIGHT), (255, 0, 0), 2)
        
        count += 1

    # Show result
    # Resize for viewing
    scale = 0.7
    display_img = cv2.resize(img_rgb, (0,0), fx=scale, fy=scale)
    display_img = cv2.cvtColor(display_img, cv2.COLOR_RGB2BGR)
    
    cv2.imshow("Red Box = Text | Green Box = Button", display_img)
    print("Press ANY KEY on the image window to close it.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    calibrate()