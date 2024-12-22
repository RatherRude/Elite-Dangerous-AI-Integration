from re import sub
import time
from typing import Literal, final
import cv2
import numpy as np
import glob
import os

from lib.Actions import screenshot

@final
class ScreenReader:
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

        def detect_lhs_screen_tab(self):
            pil_img = screenshot(new_height=1080)
            game_img_color = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            # get features from scene image
            game_features = self.getFeatures(img=game_img_color)
            
            
            header_pattern = cv2.imread('src/assets/screen_lhs_header.png')
            header_features = self.getFeatures(header_pattern)
            
            # detect features on test image
            header_image, corners = self.detectFeatures(game_img_color, game_features, header_features)
            if header_image is None or corners is None:
                print("Header not found")
                return None
            
            # save image to disk
            cv2.imwrite('header_match.png', header_image)
            
            section_offsets = [(0,50),(50,326),(326,604),(604,880)]
            section_brightness = []
            # split the header into 4 sections, and take the average brightness of each section
            for (start_x, end_x) in section_offsets:
                section = header_image[:,start_x:end_x]
                brightness = np.mean(cv2.cvtColor(section, cv2.COLOR_BGR2GRAY))
                section_brightness.append(brightness)
            
            # find the index with the highest brightness
            max_brightness_idx = np.argmax(section_brightness)
            
            return ['system', 'navigation', 'transactions', 'contacts'][max_brightness_idx]
            

        def main(self):
            # Scene image
            scene_files = sorted(glob.glob("game/*.*"))
            for scene_file in scene_files:
                scene_img_color = cv2.imread(scene_file)
                if scene_img_color is None:
                    raise IOError(f"Could not load scene image: {scene_file}")
                scene_img_color = cv2.resize(scene_img_color, (1920,1080), interpolation= cv2.INTER_LINEAR)
                scene_img_gray = cv2.cvtColor(scene_img_color, cv2.COLOR_BGR2GRAY)
                # get features from scene image
                scene_features = self.getFeatures(img=scene_img_color)
                
                # Get all pattern images
                pattern_files = sorted(glob.glob("src/assets/screen_*.png"))
                
                colors = [(0, 0, 255), (0, 128, 255), (0, 255, 0), (0, 255, 128), (255, 0, 0), (255, 0, 128), (255, 255, 0), (255, 255, 255)]
                color_idx = -1
                
                # get train features
                for pattern in pattern_files:
                    print("Detecting screen", pattern)
                    color_idx += 1
                    screen_pattern = cv2.imread(pattern)
                    train_features = self.getFeatures(screen_pattern)
                    
                    # detect features on test image
                    screen_image, corners = self.detectFeatures(scene_img_color, scene_features, train_features)
                    if screen_image is None or corners is None:
                        print("Screen not found", pattern)
                        continue
                    
                    button_files = sorted(glob.glob("src/assets/button_*.png"))
                    
                    for button in button_files:
                        #print("Detecting button", button)
                        # get features from scene image
                        subimage_features = self.getFeatures(img=screen_image.copy())
                        button_pattern = cv2.imread(button)
                        button_features = self.getFeatures(button_pattern.copy())
                        button_image, button_corners = self.detectFeatures(screen_image.copy(), subimage_features, button_features)
                        
                        if button_image is None or button_corners is None:
                            print("Button not found", button)
                            continue
                        #cv2.imshow("Button "+str(button), button_image.copy())
                        print("Button found", button)
                        # draw rotated bounding box
                        #cv2.polylines(screen_image, [np.int32(button_corners)], True, colors[color_idx % len(colors)], 3)
                        #cv2.putText(subimage, button, (10,30*color_idx+30), cv2.FONT_HERSHEY_SIMPLEX, 1, colors[color_idx % len(colors)], 2)
                        
                    # display the image
                    #cv2.imshow("Preview", screen_image.copy())

                    # wait for window close
                    #try:
                    #    while cv2.getWindowProperty("Preview", cv2.WND_PROP_VISIBLE) >= 1:
                    #        cv2.waitKey(50)
                    #except KeyboardInterrupt:
                    #    pass
                    #finally:
                    #    cv2.destroyAllWindows()

if __name__ == "__main__":
    while True:
        menu = ScreenReader().detect_lhs_screen_tab()
        print(menu)
        time.sleep(1)