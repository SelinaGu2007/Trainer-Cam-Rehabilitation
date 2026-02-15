import os
import cv2
import numpy as np

frame_duration = 150  # Duration in milliseconds to display each frame

value = 10000  # 阈值

def onMouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            # Check if the left mouse button is clicked
            print("Left mouse button clicked")


def view_imageseries(path,elementdistance, folder1_path, folder2_path, folder1_path_3d, plot_path):

# mkdir for saving the analyse outcome
    save_folder = f'{folder1_path}\\analyse'
    if not os.path.exists(save_folder):
        os.mkdir(save_folder)


    folder1_image_files = sorted([
        file for file in os.listdir(folder1_path)
        if file.endswith((".jpg", ".png"))
    ], key=lambda x: int(x.split("idx_")[1].split(".")[0]))

    folder2_image_files = sorted([
        file for file in os.listdir(folder2_path)
        if file.endswith((".jpg", ".png"))
    ], key=lambda x: int(x.split("idx_")[1].split(".")[0]))

    folder13D_image_files = sorted([
        file for file in os.listdir(folder1_path_3d)
        if file.endswith((".jpg", ".png"))
    ], key=lambda x: int(x.split("idx_")[1].split(".")[0]))

    plot_file = sorted([
        file for file in os.listdir(plot_path)
        if file.endswith((".jpg", ".png"))
    ])

    pause = False

    # Iterate over the path and display the corresponding images
    for index, (a, b) in enumerate(path):
        folder1_image = None
        folder2_image = None
        folder13D_image = None

        # Load image from folder1 if available
        if 0 <= a < len(folder1_image_files):
            folder1_image_path = os.path.join(folder1_path, folder1_image_files[a])
            folder1_image = cv2.imread(folder1_image_path)

        # Load image from folder2 if available
        if 0 <= b < len(folder2_image_files):
            folder2_image_path = os.path.join(folder2_path, folder2_image_files[b])
            folder2_image = cv2.imread(folder2_image_path)


        # Load image from folder13D if available
        if 0 <= a < len(folder13D_image_files):
            folder13D_image_path = os.path.join(folder1_path_3d, folder13D_image_files[a])
            folder13D_image = cv2.imread(folder13D_image_path)

        plot_image_path = os.path.join(plot_path, plot_file[0])
        plot_image = cv2.imread(plot_image_path)

        height, width, _ = folder13D_image.shape
        width = width +150
        folder2_image= cv2.resize(folder2_image, (width, height+40))
        folder13D_image = cv2.resize(folder13D_image, (width, height-40))
        folder1_image= cv2.resize(folder1_image, (width, height+40))
        plot_image = cv2.resize(plot_image, (width, height-40))
        if(elementdistance[index]>=value):
            center_coordinates = (width // 2, (height+40) // 2)
            radius = min(width, height+40) // 4
            color = (0, 0, 255)  # Red in BGR
            thickness = 2
            folder1_image = cv2.circle(folder1_image, center_coordinates, radius, color, thickness)


        channels_a = cv2.split(folder1_image)
        channels_b = cv2.split(folder2_image)
        channels_c = cv2.split(folder13D_image)
        channels_d = cv2.split(plot_image)

        img_a = cv2.merge(channels_a)
        img_b = cv2.merge(channels_b)
        img_c = cv2.merge(channels_c)
        img_d = cv2.merge(channels_d)

        # Combine images into a 2x2 grid
        combined_image = np.vstack([np.hstack([img_b, img_a]), np.hstack([img_d, img_c])])


        save_filename = f"combined_image_{index}.jpg"
        save_path = os.path.join(save_folder, save_filename)
        cv2.imwrite(save_path, combined_image)
        # Display the combined image
        cv2.namedWindow('Ananlse_outcome', cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        cv2.setMouseCallback('Ananlse_outcome', onMouse)
        #cv2.setWindowProperty('Ananlse_outcome', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        cv2.imshow('Ananlse_outcome', combined_image)
                        # Wait for the 'Esc' key press or the specified frame duration
        key = cv2.waitKey(frame_duration)
        if key == 27 or cv2.getWindowProperty('Ananlse_outcome', cv2.WND_PROP_VISIBLE) < 1:
            break 
        elif key == 32:  # Spacebar key
            cv2.waitKey(0)
            pause = not pause

    # Close the OpenCV window
    cv2.destroyAllWindows()



def showvideo(folder_path):
        folder1_image_files = sorted([
        file for file in os.listdir(folder_path)
        if file.endswith((".jpg"))
    ], key=lambda x: int(x.split("image_")[1].split(".")[0]))
        
        pause =False

        for image_file in folder1_image_files:
            image_path = os.path.join(folder_path, image_file)
            image = cv2.imread(image_path)
            cv2.namedWindow('Ananlse_outcome', cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
            cv2.setMouseCallback('Ananlse_outcome', onMouse)
           #cv2.setWindowProperty('Ananlse_outcome', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            cv2.imshow('Ananlse_outcome', image)
            key = cv2.waitKey(frame_duration)
            if key == 27 or cv2.getWindowProperty('Ananlse_outcome', cv2.WND_PROP_VISIBLE) < 1:
            # 'Esc' key or window closed
                break
            elif key == 32:  # Spacebar key
                cv2.waitKey(0)
                pause = not pause

        cv2.destroyAllWindows()

def showImage(folder_path1,folder_path2):
    '''
    show two images
    '''
    image1 = cv2.imread(folder_path1)
    image2 = cv2.imread(folder_path2)
    cv2.imshow('image1',image1)
    cv2.imshow('image2',image2)
    cv2.waitKey(frame_duration)

    # Close the window
    cv2.destroyAllWindows()

