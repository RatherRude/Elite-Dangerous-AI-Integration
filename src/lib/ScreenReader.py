import platform
from time import sleep
from typing import final

import cv2
from cv2.typing import MatLike
import numpy as np

from .Config import get_asset_path
from .Logger import log

def read_asset(filename:str) -> MatLike:
    path = get_asset_path(filename)
    
    image_data = open(path, 'rb').read()
    return cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)

@final
class ScreenReader:
        def __init__(self):
            self.templates = {
                "screen_lhs_header": self.getFeatures(read_asset('screen_lhs_header.png')),
                "screen_lhs_navigation": self.getFeatures(read_asset('screen_lhs_navigation.png'))
            }

        def calculate_colorfulness(self, image):
            # Convert the image to the hsv color space
            hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

            # Split into H, S and V channels
            H, S, V = cv2.split(hsv_image)

            # Calculate the chroma as sqrt(S^2 + V^2)
            chroma = np.sqrt(S.astype('float32') ** 2 + V.astype('float32') ** 2)

            # Calculate the average chroma as the colorfulness measure
            colorfulness_score = np.mean(chroma)
            return colorfulness_score

        def angle_between_vectors(self, u, v):
            """
            Returns the angle in degrees between vectors u and v.
            """
            dot = np.dot(u, v)               # dot product
            mag_u = np.linalg.norm(u)
            mag_v = np.linalg.norm(v)
            if mag_u == 0 or mag_v == 0:
                # Avoid division by zero; return None or 0
                return None
            cos_angle = dot / (mag_u * mag_v)
            
            # Numerical issues can make cos_angle slightly out of [-1, 1]
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            
            angle_radians = np.arccos(cos_angle)
            angle_degrees = np.degrees(angle_radians)
            return angle_degrees

        def check_right_angles(self, scene_corners, angle_tolerance=15):
            """
            Given the 4 corners (scene_corners) of a quadrilateral,
            checks if each corner is within `angle_tolerance` degrees of 90°.
            
            Returns:
            angles: list of the 4 angles [angle0, angle1, angle2, angle3]
            all_right: True if all angles are within the tolerance of 90°, False otherwise
            """
            
            # scene_corners is shape (4,1,2) - reshape to (4,2)
            corners_2d = scene_corners.reshape(-1, 2)
            
            angles = []
            for i in range(4):
                # Indices of the previous and next corners (wrap around using % 4)
                prev_i = (i - 1) % 4
                next_i = (i + 1) % 4
                
                # Current corner
                c_current = corners_2d[i]
                # Previous corner
                c_prev = corners_2d[prev_i]
                # Next corner
                c_next = corners_2d[next_i]
                
                # Vector from current corner to previous corner
                vec_prev = c_prev - c_current
                # Vector from current corner to next corner
                vec_next = c_next - c_current
                
                angle_deg = self.angle_between_vectors(vec_prev, vec_next)
                angles.append(angle_deg)
            
            # Check if each angle is within 15° of 90°
            all_right = all(abs(a - 90) <= angle_tolerance for a in angles if a is not None)
            
            return angles, all_right

        def createDetector(self):
            detector = cv2.SIFT.create()
            return detector

        def getFeatures(self, img):
            kernel = np.array(  [[0,-1,0],
                                                            [-1, 5,-1],
                                                            [0,-1,0]], np.float32)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            #img = cv2.filter2D(img, -1, kernel)
            #img = cv2.equalizeHist(img)
            #_, img = cv2.threshold(img, 110, 255, cv2.THRESH_BINARY)
            
            detector = self.createDetector()
            kps, descs = detector.detectAndCompute(img, None)
            return kps, descs, img.shape

        def detectFeatures(self, scene_img, scene_features, train_features):
            train_kps, train_descs, shape = train_features
            # get features from input image
            kps, descs, _ = scene_features
            # check if keypoints are extracted
            if not kps:
                return None, None
            
            # now we need to find matching keypoints in two sets of descriptors (from sample image, and from current image)
            # knnMatch uses k-nearest neighbors algorithm for that
            bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
            matches = bf.knnMatch(train_descs, descs, k=2)
            good = []
            
            # apply ratio test to matches of each keypoint
            # idea is if train KP have a matching KP on image, it will be much closer than next closest non-matching KP,
            # otherwise, all KPs will be almost equally far
            for m, n in matches:
                if m.distance < 0.7 * n.distance:
                    #print(m.distance)
                    good.append(m)
            # stop if we didn't find enough matching keypoints
            if len(good) < 0.1 * len(train_kps) or len(good) < 10:
                #print("Not enough matches", len(good), 'out of', len(train_kps))
                return None, None
            
            #print("Matches found", len(good), 'out of', len(train_kps))
            # estimate a transformation matrix which maps keypoints from train image coordinates to sample image
            src_pts = np.float32([train_kps[m.queryIdx].pt for m in good]).reshape(-1,1,2)
            dst_pts = np.float32([kps[m.trainIdx].pt for m in good]).reshape(-1,1,2)
            
            # Find homography from pattern to scene
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            if H is None:
                #print("Homography not found.")
                return None, None

            h, w = shape  # pattern's height and width in pixels (or some known units)

            # PROJECT the pattern corners into the scene
            pattern_corners = np.float32([[0,0],[w,0],[w,h],[0,h]]).reshape(-1, 1, 2)
            scene_corners = cv2.perspectiveTransform(pattern_corners, H)
            
            # calulate the angles at each corner
            angles, ok = self.check_right_angles(scene_corners)
            #print("Angles:", angles)
            #print("Right angles:", ok)
            if not ok:
                #print("Not all angles are right angles")
                return None, None

            # return perspective corrected image
            corrected_img = cv2.warpPerspective(scene_img.copy(), np.linalg.inv(H), (w,h))
            return corrected_img, scene_corners

        def get_screen(self):
            pil_img = self.screenshot(new_height=1080)
            if not pil_img:
                return None
            game_img_color = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            # get features from scene image
            game_features = self.getFeatures(img=game_img_color)
            return game_img_color, game_features

        def get_template_match(self, feature: str):
            game_img_color, game_features = self.get_screen()
            features = self.templates[feature]

            # detect features on test image
            header_image, corners = self.detectFeatures(game_img_color, game_features, features)
            if header_image is None or corners is None:
                #print("Header not found")
                return None
            return header_image

        def detect_lhs_screen_tab(self):
            header_match = self.get_template_match("screen_lhs_header")
            if isinstance(header_match, np.ndarray):
                log('debug', 'tab detection header match')
                section_offsets = [(10,10+38),(54,54+38),(330,330+38),(608,608+38)]
                section_colors = []
                # split the header into 4 sections, and take the average colorfulness of each section
                for (start_x, end_x) in section_offsets:
                    section = header_match[:,start_x:end_x]
                    color = self.calculate_colorfulness(section)
                    log('debug', 'tab color amount',color)
                    section_colors.append(color)

                # find the index with the highest brightness
                max_color_idx = np.argmax(section_colors)
            
                return ['system', 'navigation', 'transactions', 'contacts'][max_color_idx]

            navigation_match = self.get_template_match("screen_lhs_navigation")
            if isinstance(navigation_match, np.ndarray):
                log('debug', 'tab detection navigation match')
                return 'navigation'

            return None

        def get_game_window_handle(self):
            if platform.system() != 'Windows':
                return None
            import win32gui

            handle = win32gui.FindWindow(0, "Elite - Dangerous (CLIENT)")
            return handle

        def setGameWindowActive(self):
            if platform.system() != 'Windows':
                return None
            handle = self.get_game_window_handle()
            import win32gui

            if handle:
                try:
                    win32gui.SetForegroundWindow(handle)  # give focus to ED
                    sleep(.15)
                    log("debug", "Set game window as active")
                except:
                    log("error", "Failed to set game window as active")
            else:
                log("info", "Unable to find Elite game window")

        def screenshot(self, new_height: int = 720):
            if platform.system() != 'Windows':
                return None
            handle = self.get_game_window_handle()
            import win32gui
            import pyautogui
            from PIL import Image
            if handle:
                self.setGameWindowActive()
                x, y, x1, y1 = win32gui.GetClientRect(handle)
                x, y = win32gui.ClientToScreen(handle, (x, y))
                x1, y1 = win32gui.ClientToScreen(handle, (x1, y1))
                width = x1 - x
                height = y1 - y
                im = pyautogui.screenshot(region=(x, y, width, height))

                # Convert the screenshot to a PIL image
                im = im.convert("RGB")

                # Resize to height 720 while maintaining aspect ratio
                aspect_ratio = width / height
                new_width = int(new_height * aspect_ratio)
                im = im.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Crop the center to a 16:9 aspect ratio
                target_aspect_ratio = 16 / 9
                target_width = int(new_height * target_aspect_ratio)
                left = (new_width - target_width) / 2
                top = 0
                right = left + target_width
                bottom = new_height
                im = im.crop((left, top, right, bottom))

                return im
            else:
                log("error", 'Window not found!')
                return None


if __name__ == "__main__":
    while True:
        menu = ScreenReader().detect_lhs_screen_tab()
        print(menu)
        sleep(1)