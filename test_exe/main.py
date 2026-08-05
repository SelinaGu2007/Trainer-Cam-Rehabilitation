import math
import json
import logging
import numpy as np
import DTW as DTW
import argparse
import sys
import os
from pathlib import Path
from typing import List, Tuple, Dict, Any

from assessment import create_assessment_report, score_errors, weighted_sequence
from exercise_profile import load_profile
from motion_data import load_legacy_frames, load_session_bodies, load_session_track
from motion_preprocessing import prepare_motion, prepared_to_bodies, retain_usable_frames
from subject_tracking import load_tracking_config

try:
    import cv2
except ImportError:
    cv2 = None

LOGGER = logging.getLogger("trainer_cam.analysis")

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
    if cv2 is None:
        radius = max(1, int(round(3 * sigma)))
        x = np.arange(-radius, radius + 1, dtype=np.float32)
        kernel = np.exp(-(x * x) / (2 * sigma * sigma))
        kernel /= np.sum(kernel)
        for i in range(A.shape[1]):
            for j in range(A.shape[2]):
                padded = np.pad(A[:, i, j], radius, mode='edge')
                B[:, i, j] = np.convolve(padded, kernel, mode='valid')
        return B

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
    Backward-compatible legacy loader. New code should call load_session_bodies().
    """
    frames = load_legacy_frames(filename, joint_count=n_joints)
    return [body for frame in frames for body in frame["bodies"]]


def getScore(element_distance, good=30.0, bad=120.0):
    """Backward-compatible wrapper for callers that pass squared distances."""
    if element_distance is None or len(element_distance) == 0:
        return 0.0
    d = np.asarray(element_distance, dtype=np.float32)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return 0.0
    return score_errors(np.sqrt(np.clip(d, 0.0, None)), good, bad, 15.0)



def getargs(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='two folder', add_help=True)
    parser.add_argument("--folder_tutor", default="NULL", help='tutor session folder')
    parser.add_argument("--folder_customer", default="NULL", help='customer session folder')
    parser.add_argument("--function", default='NULL', help='select from tracking,quality,report,showVideos,score,showMaxDiffetence')
    parser.add_argument("--profile", default=None, help='exercise profile id or JSON path')
    parser.add_argument("--tracking-config", default=None, help='subject tracking JSON path')
    parser.add_argument("--tutor-body-id", type=int, default=None, help='explicit tutor body ID')
    parser.add_argument("--customer-body-id", type=int, default=None, help='explicit customer body ID')
    parser.add_argument("--report-output", default=None, help='optional assessment JSON output path')
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    parser.add_argument("--min-confidence", type=int, default=1, choices=range(4))
    parser.add_argument("--max-interpolation-gap", type=int, default=3)
    parser.add_argument("--min-required-coverage", type=float, default=0.8)
    parser.add_argument("--min-frame-joint-fraction", type=float, default=1.0)
    parser.add_argument("--smoothing-sigma", type=float, default=3.0)
    parser.add_argument("--no-normalize", action="store_true")
    return parser.parse_args(args)


def main():
    args = getargs(sys.argv[1:])
    folder_tutor = args.folder_tutor
    folder_customer = args.folder_customer
    function = args.function
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOGGER.info("Starting analysis function=%s tutor=%s customer=%s", function, folder_tutor, folder_customer)

    if folder_tutor == "NULL" or folder_customer == "NULL":
        raise ValueError("Please provide --folder_tutor and --folder_customer")
    if not 0.0 <= args.min_required_coverage <= 1.0:
        raise ValueError("--min-required-coverage must be between 0 and 1")
    if not 0.0 < args.min_frame_joint_fraction <= 1.0:
        raise ValueError("--min-frame-joint-fraction must be in (0, 1]")
    profile = load_profile(args.profile)
    tracking_config = load_tracking_config(args.tracking_config)
    LOGGER.info("Using exercise profile id=%s source=%s", profile.profile_id, profile.source_path)
    LOGGER.info("Using subject tracking config source=%s", tracking_config.source_path)

    analyse_folder = os.path.join(folder_customer, "analyse")
    cached_report_ready = not args.report_output or Path(args.report_output).is_file()
    if (function == "showVideos" and os.path.exists(analyse_folder)
            and os.listdir(analyse_folder) and cached_report_ready):
        # If analysis already exists, just show it
        from view_image import showvideo
        showvideo(analyse_folder)
        return 0

    raw_bodies_A, tracking_A = load_session_track(
        folder_tutor, body_id=args.tutor_body_id, tracking_config=tracking_config
    )
    raw_bodies_B, tracking_B = load_session_track(
        folder_customer, body_id=args.customer_body_id, tracking_config=tracking_config
    )
    if function == "tracking":
        print(json.dumps({"tutor": tracking_A, "customer": tracking_B}, indent=2))
        return 0
    for role, tracking in (("tutor", tracking_A), ("customer", tracking_B)):
        LOGGER.info("%s subject tracking: %s", role.capitalize(), tracking)
        if not tracking["gate_passed"]:
            raise ValueError(
                f"{role} session failed subject tracking gates: "
                + "; ".join(tracking["gate_failures"])
            )
    if not raw_bodies_A or not raw_bodies_B:
        raise ValueError("Both recordings must contain at least one valid body frame")
    required_joints = profile.required_joints
    prepared_A = prepare_motion(
        raw_bodies_A,
        min_confidence=args.min_confidence,
        max_interpolation_gap=args.max_interpolation_gap,
        normalise=not args.no_normalize,
    )
    prepared_B = prepare_motion(
        raw_bodies_B,
        min_confidence=args.min_confidence,
        max_interpolation_gap=args.max_interpolation_gap,
        normalise=not args.no_normalize,
    )
    quality_A = prepared_A.quality_summary(required_joints)
    quality_B = prepared_B.quality_summary(required_joints)
    quality_A["subject_tracking"] = tracking_A
    quality_B["subject_tracking"] = tracking_B
    LOGGER.info("Tutor motion quality: %s", quality_A)
    LOGGER.info("Customer motion quality: %s", quality_B)
    for role, quality in (("tutor", quality_A), ("customer", quality_B)):
        if quality["required_joint_coverage"] < args.min_required_coverage:
            raise ValueError(
                f"{role} required joint coverage is too low: "
                f"{quality['required_joint_coverage']:.1%}"
            )
    prepared_A = retain_usable_frames(
        prepared_A, required_joints, minimum_fraction=args.min_frame_joint_fraction
    )
    prepared_B = retain_usable_frames(
        prepared_B, required_joints, minimum_fraction=args.min_frame_joint_fraction
    )
    quality_A["usable_frame_count"] = int(prepared_A.positions.shape[0])
    quality_B["usable_frame_count"] = int(prepared_B.positions.shape[0])
    if function == "quality":
        print(json.dumps({"tutor": quality_A, "customer": quality_B}, indent=2))
        return 0
    bodies_A = prepared_to_bodies(prepared_A)
    bodies_B = prepared_to_bodies(prepared_B)
    LOGGER.info("Prepared frames tutor=%d customer=%d", len(bodies_A), len(bodies_B))

    Angle_A = np.array(getAnglesToaxle(bodies_A, profile.feature_pairs, blind=False), dtype=np.float32)
    Angle_B = np.array(getAnglesToaxle(bodies_B, profile.feature_pairs, blind=False), dtype=np.float32)

    # Smooth to reduce noise before DTW
    Angle_A = GaussianFilter(Angle_A, sigma=args.smoothing_sigma)
    Angle_B = GaussianFilter(Angle_B, sigma=args.smoothing_sigma)

    # The exercise profile selects axes and applies feature weights before DTW.
    sequence_A = weighted_sequence(Angle_A, profile)
    sequence_B = weighted_sequence(Angle_B, profile)

    # Constrain DTW warping to a reasonable band for speed + stability
    paths = DTW.getPath(sequence_B, sequence_A, window=30)

    element_distance = DTW.get_elementwise_distances(sequence_B, sequence_A, paths)
    min_paths, min_distance = DTW.getMinPath_Distance(paths, element_distance)

    report = create_assessment_report(
        customer_angles=Angle_B,
        tutor_angles=Angle_A,
        path=paths,
        profile=profile,
        customer_motion=prepared_B,
        tutor_motion=prepared_A,
        customer_quality=quality_B,
        tutor_quality=quality_A,
    )
    if args.report_output:
        report_path = Path(args.report_output)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        LOGGER.info("Assessment report written to %s", report_path)


    if function == 'score':
        print(report["overall_score"])

    elif function == "report":
        print(json.dumps(report, indent=2))

    elif function == "showVideos":
        from save3D import save3D
        from view_image import view_imageseries
        plot_folder = os.path.join(folder_customer, "plot")
        if not os.path.exists(plot_folder):
            os.mkdir(plot_folder)
        # Plot the first configured feature so profiles with any feature count work.
        DTW.plotWrap(Angle_B[:, 0, 0], Angle_A[:, 0, 0], os.path.join(plot_folder, "wrap.jpg"))
        save3D(folder=folder_customer)
        view_imageseries(
            path=min_paths,
            elementdistance=min_distance,
            folder1_path=folder_customer,
            folder2_path=folder_tutor,
            folder1_path_3d=os.path.join(folder_customer, "3D"),
            plot_path=plot_folder,
            folder1_image_names=[body.get("image") for body in bodies_B],
            folder2_image_names=[body.get("image") for body in bodies_A],
        )

    elif function == "showMaxDiffetence":
        from view_image import resolve_session_image, showImage
        customer_index = report["worst_segment"]["customer_sequence_index"]
        tutor_index = report["worst_segment"]["tutor_sequence_index"]
        customer_image = resolve_session_image(
            folder_customer, bodies_B[customer_index].get("image"),
            bodies_B[customer_index].get("frame_index", customer_index)
        )
        tutor_image = resolve_session_image(
            folder_tutor, bodies_A[tutor_index].get("image"),
            bodies_A[tutor_index].get("frame_index", tutor_index)
        )
        if customer_image is None or tutor_image is None:
            raise FileNotFoundError("Comparison frame image is missing")
        showImage(
            customer_image,
            tutor_image,
        )
    else:
        raise ValueError("Unknown --function. Use: tracking, quality, report, score, showVideos, showMaxDiffetence")

    return 0


if __name__ == "__main__":
    main()
