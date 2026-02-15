import math
import numpy as np
import DTW as DTW
from view_image import view_imageseries, showImage, showvideo
from save3D import save3D
import cv2
import argparse
import sys
import os
from typing import List, Tuple, Dict, Any, Optional

# Pairs of joint indices used as "features" (each pair defines a skeleton segment)
features: List[Tuple[int, int]] = [
    (5, 6), (6, 7),
    (12, 13), (13, 14),
    (18, 19), (19, 20),
    (22, 23), (23, 24),
    (5, 12),
]


def getVector(B, A):
    """
    Vector from point B to point A (A - B).
    """
    return [A[0] - B[0], A[1] - B[1], A[2] - B[2]]


def _safe_norm(v) -> float:
    return float(math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]))


def GetAngle(A, B):
    """
    Angle between 3D vectors A and B in radians, with numerical safety.
    Returns 0 when either vector has (near) zero length.
    """
    na = _safe_norm(A)
    nb = _safe_norm(B)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    dot = A[0] * B[0] + A[1] * B[1] + A[2] * B[2]
    cosv = dot / (na * nb)
    # Clamp for acos numerical stability
    cosv = 1.0 if cosv > 1.0 else (-1.0 if cosv < -1.0 else cosv)
    return math.acos(cosv)


def update(frame: int, bodies: List[Dict[str, Any]]):
    """
    Get all 32 body joint positions (x,y,z lists) for a body at a given frame.
    This assumes bodies[frame]['joints'] is a list indexed by joint index.
    """
    body = bodies[frame]
    joints = body['joints']
    x = [joint['position'][0] for joint in joints]
    y = [joint['position'][1] for joint in joints]
    z = [joint['position'][2] for joint in joints]
    return x, y, z


def getPosition(bodies: List[Dict[str, Any]], frame: int, idx: int):
    """
    Position (x,y,z) of a specific joint index at a given frame.
    """
    x, y, z = update(frame, bodies)
    return [x[idx], y[idx], z[idx]]


def IfOnSameSide(bodies: List[Dict[str, Any]], frame: int):
    """
    Detect whether both wrists are on the same side of the spine chest in x.
    Returns (True, feature_index_1, feature_index_2) to be "blinded" if so.
    """
    SPINE_CHEST = getPosition(bodies, frame, 2)
    WRIST_LEFT = getPosition(bodies, frame, 7)
    WRIST_RIGHT = getPosition(bodies, frame, 14)
    if (WRIST_RIGHT[0] - SPINE_CHEST[0]) * (WRIST_LEFT[0] - SPINE_CHEST[0]) > 0:
        # both on the same side in x
        if (WRIST_LEFT[2] - WRIST_RIGHT[2]) > 0:
            return True, 0, 1
        else:
            return True, 2, 3
    return False, -1, -1


def getAnglesVariation(bodies, features, interval: int):
    """
    Variation of segment direction across frames: angle between segment vectors
    at frame t and frame t+interval. Output in degrees.
    """
    if interval <= 0:
        raise ValueError("interval must be positive")
    n_frames = len(bodies) - interval
    angles = [[None] * len(features) for _ in range(n_frames)]
    for i, (f_1, f_2) in enumerate(features):
        for frame in range(n_frames):
            a_1 = getPosition(bodies, frame, f_1)
            b_1 = getPosition(bodies, frame, f_2)
            a_2 = getPosition(bodies, frame + interval, f_1)
            b_2 = getPosition(bodies, frame + interval, f_2)
            A = getVector(a_1, b_1)
            B = getVector(a_2, b_2)
            angles[frame][i] = int(GetAngle(A, B) / math.pi * 180)
    return angles


def getAnglesToZaxle(bodies, features):
    """
    Angle between each segment and the Z axis. Output in degrees.
    """
    z_axis = [0, 0, 1]  # Z axis
    angles = [[None] * len(features) for _ in range(len(bodies))]
    for i, (f_1, f_2) in enumerate(features):
        for frame in range(len(bodies)):
            a_1 = getPosition(bodies, frame, f_1)
            b_1 = getPosition(bodies, frame, f_2)
            A = getVector(a_1, b_1)
            angles[frame][i] = int(GetAngle(A, z_axis) / math.pi * 180)
    return angles


def getAnglesToaxle(bodies, features, blind: bool = False):
    """
    Angle between each segment and the three axes (Z,Y,X).
    Output shape: [frames][3][features] in degrees.
    """
    z_axis = [0, 0, 1]  # Z
    y_axis = [0, 1, 0]  # Y
    x_axis = [1, 0, 0]  # X

    angles = [[[None for _ in range(len(features))] for _ in range(3)] for _ in range(len(bodies))]
    for i, (f_1, f_2) in enumerate(features):
        for frame in range(len(bodies)):
            a_1 = getPosition(bodies, frame, f_1)
            b_1 = getPosition(bodies, frame, f_2)
            A = getVector(a_1, b_1)
            angles[frame][0][i] = int(GetAngle(A, z_axis) / math.pi * 180)
            angles[frame][1][i] = int(GetAngle(A, y_axis) / math.pi * 180)
            angles[frame][2][i] = int(GetAngle(A, x_axis) / math.pi * 180)

    if blind:
        for frame in range(len(bodies)):
            T, A_1, A_2 = IfOnSameSide(bodies, frame)
            if T:
                for axis in range(3):
                    angles[frame][axis][A_1] = 0
                    angles[frame][axis][A_2] = 0
    return angles


def GaussianFilter(A: np.ndarray, sigma: float = 1.0):
    """
    Gaussian smoothing for each [axis, feature] channel over time.
    A shape: [frames, 3, n_features]
    """
    if sigma <= 0:
        return A
    B = np.zeros_like(A)
    for i in range(A.shape[1]):
        for j in range(A.shape[2]):
            column = A[:, i, j].astype(np.float32).reshape(-1, 1)
            # cv2 expects 2D; (0,0) lets it infer kernel size from sigma
            filtered = cv2.GaussianBlur(column, (0, 0), sigmaX=sigma, sigmaY=sigma)
            B[:, i, j] = filtered.reshape(-1)
    return B


def find_plane(vector1, vector2):
    vector1 = np.array(vector1)
    vector2 = np.array(vector2)
    normal_vector = np.cross(vector1, vector2)
    d = -np.dot(normal_vector, vector1)
    return normal_vector, d


def find_orthogonal_plane(normal_plane, vector_on_plane):
    orthogonal_normal = np.cross(normal_plane, vector_on_plane)
    d = -np.dot(orthogonal_normal, vector_on_plane)
    return orthogonal_normal, d


def getAngleFromPlane(norma_plane, vector):
    vector = np.array(vector)
    denom = float(np.sqrt(norma_plane @ norma_plane) * np.sqrt(vector @ vector))
    if denom < 1e-12:
        return 0.0
    a = float(norma_plane @ vector / denom)
    a = 1.0 if a > 1.0 else (-1.0 if a < -1.0 else a)
    return float(np.arccos(a))


def getFeatuesAnglesFromPlane(bodies, features, frame, plane_1, plane_2):
    angles = [[None] * len(features) for _ in range(2)]
    for i, (f_1, f_2) in enumerate(features):
        p_1 = getPosition(bodies, frame, f_1)
        p_2 = getPosition(bodies, frame, f_2)
        skleton = getVector(p_1, p_2)
        angles[0][i] = int(getAngleFromPlane(plane_1, skleton) / math.pi * 180)
        angles[1][i] = int(getAngleFromPlane(plane_2, skleton) / math.pi * 180)
    return angles


def getMostFeatures(BodiesAngles_From, BodiesAngles_TO, id_from, id_to):
    # Note: appears unused in current pipeline; kept for compatibility.
    Angles_From = BodiesAngles_From(id_from)
    Angles_To = BodiesAngles_TO(id_to)
    return Angles_From, Angles_To


def getBodiesFromFile(filename: str, n_joints: int = 32):
    """
    Parse 'output2.txt' produced by simple_3d_viewer.

    Robustness improvement:
    - joints are stored in a fixed-length list indexed by joint index
      so getPosition(..., idx) always works even if the file order changes.
    """
    with open(filename, 'r', encoding='utf-8', errors='ignore') as file:
        lines = file.readlines()

    bodies: List[Dict[str, Any]] = []
    current_body: Optional[Dict[str, Any]] = None
    joints: Optional[List[Dict[str, Any]]] = None

    for line in lines:
        line = line.strip()
        if line.startswith("Body ID:"):
            # flush previous
            if current_body is not None:
                current_body['joints'] = joints if joints is not None else [{'index': i, 'position': [0.0, 0.0, 0.0]} for i in range(n_joints)]
                bodies.append(current_body)
            current_body = {'id': int(line.split(":")[1].strip())}
            joints = [{'index': i, 'position': [0.0, 0.0, 0.0]} for i in range(n_joints)]
        elif line.startswith("Joint") and joints is not None:
            try:
                parts = line.split(":")
                joint_index = int(parts[0].split("[")[1].strip("]"))
                pos_str = parts[1].split("(")[1].split(")")[0]
                position = [float(coord.strip()) for coord in pos_str.split(",")]
                if 0 <= joint_index < n_joints:
                    joints[joint_index] = {'index': joint_index, 'position': position}
            except Exception:
                # Skip malformed joint line
                continue

    if current_body is not None:
        current_body['joints'] = joints if joints is not None else [{'index': i, 'position': [0.0, 0.0, 0.0]} for i in range(n_joints)]
        bodies.append(current_body)
    return bodies


def getScore(element_distance, good=30.0, bad=120.0):
    """
    Stable 0-100 score from element-wise DTW distances.

    - element_distance: list/array of nonnegative distances
    - good: typical RMS distance for a good match (score ~ 90-100)
    - bad: RMS distance for a poor match (score ~ 0-20)

    Returns: float in [0, 100]
    """
    if element_distance is None or len(element_distance) == 0:
        return 0.0

    d = np.asarray(element_distance, dtype=np.float32)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return 0.0

    rms = float(np.sqrt(np.mean(d)))

    # Outlier penalty: fraction of frames above "bad" threshold
    out_frac = float(np.mean(np.sqrt(d) > bad))

    # Map rms into [0,1] then to [0,100]
    # Clamp for stability
    t = (rms - good) / max(bad - good, 1e-6)
    t = min(max(t, 0.0), 1.0)

    score = 100.0 * (1.0 - t)

    # Apply mild outlier penalty (max -15 points)
    score -= 15.0 * out_frac

    return max(0.0, min(100.0, score))



def getargs(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='two folder', add_help=True)
    parser.add_argument("--folder_tutor", default="NULL", help='tutor session folder')
    parser.add_argument("--folder_customer", default="NULL", help='customer session folder')
    parser.add_argument("--function", default='NULL', help='select from showVideos,score,showMaxDiffetence')
    return parser.parse_args(args)


def main():
    args = getargs(sys.argv[1:])
    folder_tutor = args.folder_tutor
    folder_customer = args.folder_customer
    function = args.function

    if folder_tutor == "NULL" or folder_customer == "NULL":
        raise ValueError("Please provide --folder_tutor and --folder_customer")

    output_tutor = os.path.join(folder_tutor, "output2.txt")
    output_customer = os.path.join(folder_customer, "output2.txt")
    if not os.path.exists(output_tutor):
        raise FileNotFoundError(output_tutor)
    if not os.path.exists(output_customer):
        raise FileNotFoundError(output_customer)

    analyse_folder = os.path.join(folder_customer, "analyse")
    if os.path.exists(analyse_folder) and os.listdir(analyse_folder):
        # If analysis already exists, just show it
        showvideo(analyse_folder)
        return 0

    bodies_A = getBodiesFromFile(output_tutor)
    bodies_B = getBodiesFromFile(output_customer)

    Angle_A = np.array(getAnglesToaxle(bodies_A, features, blind=False), dtype=np.float32)
    Angle_B = np.array(getAnglesToaxle(bodies_B, features, blind=False), dtype=np.float32)

    # Smooth to reduce noise before DTW
    Angle_A = GaussianFilter(Angle_A, sigma=3)
    Angle_B = GaussianFilter(Angle_B, sigma=3)

    # Constrain DTW warping to a reasonable band for speed + stability
    paths = DTW.getPath(Angle_B, Angle_A, window=30)

    element_distance = DTW.get_elementwise_distances(Angle_B, Angle_A, paths)
    min_paths, min_distance = DTW.getMinPath_Distance(paths, element_distance)

    # Use a short window so we find the worst *segment* (less noisy than a single frame)
    max_Index, max_Item = DTW.getMaxIndex_Item(min_distance, 10)


    if function == 'score':
        score = getScore(min_distance)
        print(score)

    elif function == "showVideos":
        plot_folder = os.path.join(folder_customer, "plot")
        if not os.path.exists(plot_folder):
            os.mkdir(plot_folder)
        # Example plot channel (kept consistent with your original code)
        DTW.plotWrap(Angle_B[:, 0, 1], Angle_A[:, 0, 1], os.path.join(plot_folder, "wrap.jpg"))
        save3D(folder=folder_customer)
        view_imageseries(
            path=min_paths,
            elementdistance=min_distance,
            folder1_path=folder_customer,
            folder2_path=folder_tutor,
            folder1_path_3d=os.path.join(folder_customer, "3D"),
            plot_path=plot_folder
        )

    elif function == "showMaxDiffetence":
        showImage(
            os.path.join(folder_customer, f"imamge_idx_{min_paths[max_Index][0]}.jpg"),
            os.path.join(folder_tutor, f"imamge_idx_{min_paths[max_Index][1]}.jpg"),
        )
    else:
        raise ValueError("Unknown --function. Use: score, showVideos, showMaxDiffetence")

    return 0


if __name__ == "__main__":
    main()
