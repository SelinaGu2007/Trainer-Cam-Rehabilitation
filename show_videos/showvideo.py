import os
import cv2
import sys
import argparse
import time 

frame_duration = 150  # Duration in milliseconds to display each frame


def onMouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            # Check if the left mouse button is clicked
            print("Left mouse button clicked")

def view_imageseries(folder1_path):
    '''
    show imagesseries with the speed decided by frame_duration
    Args:
        folder1_path: the folder containning target images
    '''
    # Get the list of image files in folder1
    folder1_image_files = sorted([
        file for file in os.listdir(folder1_path)
        if file.endswith((".jpg"))
    ], key=lambda x: int(x.split("idx_")[1].split(".")[0]))

    cv2.namedWindow("Tutor",cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.setMouseCallback('Tutor', onMouse)
    # Iterate over the path and display the corresponding images
    pause =False
    for filename in folder1_image_files:
        image_path = os.path.join(folder1_path, filename)

        folder1_image = cv2.imread(image_path)

        # Display image from folder1
        if folder1_image is not None:
            cv2.imshow("Tutor", folder1_image)

        # Wait indefinitely until a key is pressed
        key = cv2.waitKey(frame_duration)

        # Break the loop if the user presses the 'ESC' key
        key = cv2.waitKey(frame_duration)
        if key == 27 or cv2.getWindowProperty('Tutor', cv2.WND_PROP_VISIBLE) < 1:
            break 
        elif key == 32:  # Spacebar key
            cv2.waitKey(0)
            pause = not pause

    # Close the OpenCV windows
    cv2.destroyAllWindows()

def view_imageseriesWihtReocrding(folder1_path):
    '''
    show imagesseries with the speed decided by frame_duration
    Args:
        folder1_path: the folder containning target images
    '''
    filePath = os.path.join(folder1_path,"startvideo.txt")
  
  # Get the list of image files in folder1
    folder1_image_files = sorted([
        file for file in os.listdir(folder1_path)
        if file.endswith((".jpg"))
    ], key=lambda x: int(x.split("idx_")[1].split(".")[0]))

    cv2.namedWindow("Tutor",cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.setMouseCallback('Tutor', onMouse)
   # dispaly the first image
    image_path = os.path.join(folder1_path, folder1_image_files[0])
    folder1_image = cv2.imread(image_path)
    if folder1_image is not None:
            cv2.imshow("Tutor", folder1_image)
            cv2.waitKey(100)


    for i in range(0,10):
            if(os.path.exists(filePath)):
                break
            cv2.waitKey(1000)

    pause =False

    # Iterate over the path and display the corresponding images
    for filename in folder1_image_files:
        image_path = os.path.join(folder1_path, filename)

        folder1_image = cv2.imread(image_path)

        # Display image from folder1
        if folder1_image is not None:
            cv2.imshow("Tutor", folder1_image)

        # Wait indefinitely until a key is pressed
        key = cv2.waitKey(frame_duration)
        # esc or close  to close the window
        if key == 27 or cv2.getWindowProperty('Tutor', cv2.WND_PROP_VISIBLE) < 1:
            break 
        elif key == 32:  # Spacebar key  to pause
            cv2.waitKey(0)
            pause = not pause

    # Close the OpenCV windows
    cv2.destroyAllWindows()


def getArgs(args=sys.argv[1:]):
    paraser =argparse.ArgumentParser(description='the floder saving the images',add_help=True,usage='')
    paraser.add_argument("--folder",default='NULL',help='the folder saving video images')
    paraser.add_argument("--mode",default="single",help="selected between single or withRecording")
    return paraser.parse_args()

if __name__ =="__main__":
    args1 = getArgs(sys.argv[1:])
    folder =args1.folder
    mode =args1.mode
    if(mode == "single"):
        view_imageseries(folder)
    elif(mode=="withRecording"):
        view_imageseriesWihtReocrding(folder)