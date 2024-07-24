import cv2
import os

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
import numpy as np
from tensorflow.keras.models import load_model
import imutils
from func_timeout import func_timeout, FunctionTimedOut


input_size = 48
model = None


# Load the model once
def load_model_once():
    global model
    if model is None:
        model_path = "models/model-OCR.h5"
        model = load_model(model_path)


# Find an empty cell in the Sudoku board
def find_empty(board):
    for i in range(len(board)):
        for j in range(len(board[0])):
            if board[i][j] == 0:
                return (i, j)
    return None


# Check if placing a number is valid
def valid(board, num, pos):
    for i in range(len(board[0])):
        if board[pos[0]][i] == num and pos[1] != i:
            return False
    for i in range(len(board)):
        if board[i][pos[1]] == num and pos[0] != i:
            return False
    box_x = pos[1] // 3
    box_y = pos[0] // 3
    for i in range(box_y * 3, box_y * 3 + 3):
        for j in range(box_x * 3, box_x * 3 + 3):
            if board[i][j] == num and (i, j) != pos:
                return False
    return True


# Solve the Sudoku board
def solve(board):
    find = find_empty(board)
    if not find:
        return True
    else:
        row, col = find
    for i in range(1, 10):
        if valid(board, i, (row, col)):
            board[row][col] = i
            if solve(board):
                return True
            board[row][col] = 0
    return False


# Get the solved board
def get_board(bo):
    if solve(bo):
        return bo
    else:
        raise ValueError("No solution exists")


# Resize the image if necessary
def resize_image(image, max_dim=640):
    h, w = image.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized_image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return resized_image
    return image


# Apply a perspective transformation to an image
def get_perspective(img, location, height=900, width=900):
    pts1 = np.float32([location[0], location[3], location[1], location[2]])
    pts2 = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
    matrix = cv2.getPerspectiveTransform(pts1, pts2)
    result = cv2.warpPerspective(img, matrix, (width, height))
    return result


# Apply the inverse perspective transformation
def get_InvPerspective(img, masked_num, location, height=900, width=900):
    pts1 = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
    pts2 = np.float32([location[0], location[3], location[1], location[2]])
    matrix = cv2.getPerspectiveTransform(pts1, pts2)
    result = cv2.warpPerspective(masked_num, matrix, (img.shape[1], img.shape[0]))
    return result


# Find the Sudoku board in the image
def find_board(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bfilter = cv2.bilateralFilter(gray, 13, 20, 20)
    edged = cv2.Canny(bfilter, 30, 180)
    keypoints = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = imutils.grab_contours(keypoints)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]
    location = None
    for contour in contours:
        approx = cv2.approxPolyDP(contour, 15, True)
        if len(approx) == 4:
            location = approx
            break
    if location is None:
        print("No board found.")
    result = get_perspective(img, location)
    return result, location


# Split the Sudoku board into individual boxes
def split_boxes(board):
    rows = np.vsplit(board, 9)
    boxes = []
    for r in rows:
        cols = np.hsplit(r, 9)
        for box in cols:
            box = cv2.resize(box, (input_size, input_size)) / 255.0
            boxes.append(box)
    return boxes


# Display the numbers on the image
def displayNumbers(img, numbers, color=(0, 255, 0)):
    W = int(img.shape[1] / 9)
    H = int(img.shape[0] / 9)
    for i in range(9):
        for j in range(9):
            if numbers[(j * 9) + i] != 0:
                cv2.putText(
                    img,
                    str(numbers[(j * 9) + i]),
                    (i * W + int(W / 2) - int((W / 4)), int((j + 0.7) * H)),
                    cv2.FONT_HERSHEY_COMPLEX,
                    2,
                    color,
                    2,
                    cv2.LINE_AA,
                )
    return img


# Solve Sudoku from the image bytes
def solve_sudoku_image(image_bytes):
    load_model_once()  
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print("Error decoding image")
        return None

    img = resize_image(img)
    board, location = find_board(img)

    if board is not None:
        gray = cv2.cvtColor(board, cv2.COLOR_BGR2GRAY)
        rois = split_boxes(gray)
        rois = np.array(rois).reshape(-1, input_size, input_size, 1)
        prediction = model.predict(rois)

        predicted_numbers = [np.argmax(i) for i in prediction]
        board_num = np.array(predicted_numbers).astype("uint8").reshape(9, 9)

        try:
            solved_board_nums = func_timeout(20, get_board, args=(board_num,))
            binArr = np.where(np.array(predicted_numbers) > 0, 0, 1)
            flat_solved_board_nums = solved_board_nums.flatten() * binArr

            mask = np.zeros_like(board)
            solved_board_mask = displayNumbers(mask, flat_solved_board_nums)
            inv = get_InvPerspective(img, solved_board_mask, location)
            combined = cv2.addWeighted(img, 0.7, inv, 1, 0)
            _, buffer = cv2.imencode(".jpg", combined)
            solved_image_bytes = buffer.tobytes()

            return solved_image_bytes
        except FunctionTimedOut:
            print("Solving the Sudoku puzzle timed out.")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None
    return None
