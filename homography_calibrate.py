import cv2
import numpy as np

# Load your parking lot snapshot
image_path = "tester.jpg"
image = cv2.imread(image_path)

if image is None:
    print("Could not load image. Check file path.")
    exit()

# Resize (optional, so window fits screen)
scale = 0.7
image = cv2.resize(image, None, fx=scale, fy=scale)

# Store clicked points
points = []

def click_event(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        cv2.circle(image, (x, y), 5, (0, 255, 0), -1)
        cv2.imshow("Select 4 Corners", image)

# Step 1: Select 4 points
cv2.imshow("Select 4 Corners", image)
cv2.setMouseCallback("Select 4 Corners", click_event)

print("👉 Click 4 points in order (top-left, top-right, bottom-right, bottom-left)")
cv2.waitKey(0)
cv2.destroyAllWindows()

if len(points) != 4:
    print(f"You selected {len(points)} points. Need 4.")
    exit()

# Step 2: Define output size (your “bird’s-eye” view)
width, height = 1600, 1200

dst_points = np.array([
    [0, 0],
    [width - 1, 0],
    [width - 1, height - 1],
    [0, height - 1]
], dtype="float32")

# Step 3: Compute homography
M = cv2.getPerspectiveTransform(np.array(points, dtype="float32"), dst_points)

# Step 4: Warp image
warped = cv2.warpPerspective(image, M, (width, height))

# Step 5: Show and save
cv2.imshow("Warped (Top-Down View)", warped)
cv2.imwrite("warped_view.jpg", warped)
print("Saved warped image as warped_view.jpg")

cv2.waitKey(0)
cv2.destroyAllWindows()
