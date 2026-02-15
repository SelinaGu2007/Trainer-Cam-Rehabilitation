import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation
import os


def save3D(folder):
    # Define connection relationships
    connections = [
        (0, 1), (1, 2), (2, 3), (3, 4), (3, 11),  # Spine
        (2, 4), (4, 5), (5, 6), (6, 7), (7, 8),  # Left arm
        (2, 11), (11, 12), (12, 13), (13, 14), (14, 15),  # Right arm
        (0, 18), (18, 19), (19, 20), (20, 21),  # Left leg
        (0, 22), (22, 23), (23, 24), (24, 25)  # Right leg
    ]

    output_folder = f'{folder}\\3D'
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    
    if   os.listdir(output_folder):
        return 0

    def update(frame):
        ax1.cla()  # Clear the previous figure

        body = bodies[frame]

        x = [joint['position'][0] for joint in body['joints']]
        y = [joint['position'][1] for joint in body['joints']]
        z = [joint['position'][2] for joint in body['joints']]

        ax1.scatter(x, y, z, marker='o')

        for connection in connections:
            joint1 = connection[0]
            joint2 = connection[1]
            x_segment = [x[joint1], x[joint2]]
            y_segment = [y[joint1], y[joint2]]
            z_segment = [z[joint1], z[joint2]]
            ax1.plot(x_segment, y_segment, z_segment, color='blue')

        ax1.set_xlabel('X')
        ax1.set_ylabel('Y')
        ax1.set_zlabel('Z')
        ax1.view_init(elev=-75, azim=-90)

        # Save the frame as an image
        frame_filename = os.path.join(output_folder, f'3D_idx_{frame}.jpg')
        fig.savefig(frame_filename, format='jpg', bbox_inches='tight')


    fig = plt.figure()

    # Create two subplots for different viewpoints
    ax1 = fig.add_subplot(111, projection='3d')



    # Parse the file and store body data
    with open(os.path.join(folder,'output2.txt'), 'r') as file:
        lines = file.readlines()

    bodies = []
    current_body = {}
    for line in lines:
        if line.startswith("Body ID:"):
            if current_body:
                bodies.append(current_body)
                current_body = {}
            current_body['id'] = int(line.split(":")[1].strip())
            current_body['joints'] = []
        elif line.startswith("Joint"):
            parts = line.split(":")
            joint_index = int(parts[0].split("[")[1].strip("]"))
            position = [float(coord.strip()) for coord in parts[1].split("(")[1].split(")")[0].split(",")]
            current_body['joints'].append({'index': joint_index, 'position': position})

    bodies.append(current_body)  # Add the last body

    # Create the animation
    animation = FuncAnimation(fig, update, frames=len(bodies), interval=150)
    for frame in range(len(bodies)):
        update(frame)  # Manually call update for each frame
        plt.close(fig)

