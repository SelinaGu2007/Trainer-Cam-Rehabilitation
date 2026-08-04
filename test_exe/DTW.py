import numpy as np
from typing import Iterable, List, Sequence, Tuple, Optional

try:
    from dtaidistance import dtw_ndim
    from dtaidistance import dtw_visualisation as dtwvis
except ImportError:  # A deterministic NumPy fallback keeps offline scoring usable.
    dtw_ndim = None
    dtwvis = None


def _fallback_path(s1: np.ndarray, s2: np.ndarray, window: Optional[int] = None) -> List[Tuple[int, int]]:
    a = np.asarray(s1, dtype=np.float64).reshape(len(s1), -1)
    b = np.asarray(s2, dtype=np.float64).reshape(len(s2), -1)
    if len(a) == 0 or len(b) == 0:
        return []

    band = max(len(a), len(b)) if window is None else max(int(window), abs(len(a) - len(b)))
    cost = np.full((len(a) + 1, len(b) + 1), np.inf, dtype=np.float64)
    cost[0, 0] = 0.0
    for i in range(1, len(a) + 1):
        start = max(1, i - band)
        stop = min(len(b), i + band) + 1
        for j in range(start, stop):
            local = float(np.sum((a[i - 1] - b[j - 1]) ** 2))
            cost[i, j] = local + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])

    i, j = len(a), len(b)
    if not np.isfinite(cost[i, j]):
        raise ValueError("DTW window is too small to connect both sequences")
    path: List[Tuple[int, int]] = []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        candidates = (cost[i - 1, j - 1], cost[i - 1, j], cost[i, j - 1])
        step = int(np.argmin(candidates))
        if step == 0:
            i, j = i - 1, j - 1
        elif step == 1:
            i -= 1
        else:
            j -= 1
    path.reverse()
    return path


# ----------------------------
# Core DTW helpers
# ----------------------------

def getDistance(S1: np.ndarray, S2: np.ndarray, *, window: Optional[int] = None) -> float:
    """
    DTW distance between two (multi-dimensional) time series.

    Args:
        S1, S2: arrays shaped (T, D) or (T,) for 1D.
        window: optional Sakoe-Chiba band (max warping deviation).

    Returns:
        DTW distance (float).
    """
    if dtw_ndim is not None:
        if window is None:
            return float(dtw_ndim.distance(S1, S2))
        return float(dtw_ndim.distance(S1, S2, window=window))
    path = _fallback_path(S1, S2, window)
    distances = get_elementwise_distances(S1, S2, path)
    return float(np.sqrt(np.sum(distances)))


def getPath(s1: np.ndarray, s2: np.ndarray, *, window: Optional[int] = None) -> List[Tuple[int, int]]:
    """
    Warping path from s1 to s2.

    Args:
        s1, s2: arrays shaped (T, D) or (T,) for 1D.
        window: optional Sakoe-Chiba band.

    Returns:
        List of (i, j) indices in the warping path.
    """
    if dtw_ndim is not None:
        if window is None:
            return dtw_ndim.warping_path(s1, s2)
        return dtw_ndim.warping_path(s1, s2, window=window)
    return _fallback_path(s1, s2, window)


def get_elementwise_distances(s1: np.ndarray, s2: np.ndarray, path: Sequence[Tuple[int, int]]) -> List[float]:
    """
    Element-wise squared L2 distances along a given warping path.

    This is vectorized for speed compared to iterating one pair at a time.

    Args:
        s1, s2: time series arrays.
        path: list/sequence of (i, j) pairs.

    Returns:
        Python list of squared distances (float).
    """
    if path is None or len(path) == 0:
        return []

    p = np.asarray(path, dtype=np.int64)  # shape (K, 2)
    i = p[:, 0]
    j = p[:, 1]

    a = np.asarray(s1)[i]
    b = np.asarray(s2)[j]
    diff = a - b
    # Sum every feature dimension while preserving one scalar per path pair.
    # Motion features are shaped (time, axis, segment), not just (time, feature).
    feature_axes = tuple(range(1, diff.ndim))
    d = np.sum(diff * diff, axis=feature_axes) if feature_axes else diff * diff
    return d.astype(np.float32).tolist()


# ----------------------------
# Visualization
# ----------------------------

def plotWrap(s1: np.ndarray, s2: np.ndarray, filename: str, *, window: Optional[int] = None) -> None:
    """
    Plot warping alignment between two 1D series and save to file.

    Args:
        s1, s2: 1D time series.
        filename: output path
        window: optional Sakoe-Chiba band
    """
    path = getPath(s1, s2, window=window)
    if dtwvis is not None:
        dtwvis.plot_warping(s1, s2, path, filename)
        return

    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, sharex=False)
    axes[0].plot(np.asarray(s1), color="tab:blue")
    axes[0].set_title("Customer sequence")
    axes[1].plot(np.asarray(s2), color="tab:orange")
    axes[1].set_title("Tutor sequence")
    fig.tight_layout()
    fig.savefig(filename)
    plt.close(fig)


# ----------------------------
# Post-processing path/distance
# ----------------------------

def getMinPath_Distance(path: Sequence[Tuple[int, int]], distance: Sequence[float]):
    """
    For each unique y (the second index), keep the (x, y) pair with minimal distance.
    Returns are sorted by y for deterministic alignment with frames.

    Original version used a dict and returned arbitrary order. This version is:
      - deterministic (sorted by y)
      - faster (vectorized argmin within groups)

    Args:
        path: list of (x, y)
        distance: list aligned with path, elementwise squared distances

    Returns:
        min_path: list of (x, y) one per unique y, sorted by y
        min_dis:  list of minimal distances aligned with min_path
    """
    if path is None or len(path) == 0:
        return [], []
    if distance is None or len(distance) == 0:
        return [], []

    p = np.asarray(path, dtype=np.int64)
    d = np.asarray(distance, dtype=np.float32)
    if p.shape[0] != d.shape[0]:
        raise ValueError("path and distance must have the same length")

    x = p[:, 0]
    y = p[:, 1]

    # sort by y then distance so first occurrence per y is minimal
    order = np.lexsort((d, y))
    y_sorted = y[order]
    x_sorted = x[order]
    d_sorted = d[order]

    # indices of first occurrence of each y in the sorted list
    first_idx = np.concatenate(([0], np.where(y_sorted[1:] != y_sorted[:-1])[0] + 1))

    y_min = y_sorted[first_idx]
    x_min = x_sorted[first_idx]
    d_min = d_sorted[first_idx]

    # already sorted by y
    min_path = list(zip(x_min.tolist(), y_min.tolist()))
    min_dis = d_min.tolist()
    return min_path, min_dis


def getMaxIndex_Item(a: Sequence[float], framecout: int = 1):
    """
    Find the window (length=framecout) with the maximum sum.

    Original version was O(n * framecout) in Python loops.
    This version uses convolution (fast, vectorized).

    Args:
        a: list/array
        framecout: window length

    Returns:
        (max_index, max_item)
    """
    if a is None or len(a) == 0:
        return 0, 0.0
    if framecout <= 0:
        raise ValueError("framecout must be >= 1")

    arr = np.asarray(a, dtype=np.float32)
    if framecout == 1:
        idx = int(np.argmax(arr))
        return idx, float(arr[idx])

    if arr.size < framecout:
        # only one possible window: whole array
        return 0, float(np.sum(arr))

    kernel = np.ones(framecout, dtype=np.float32)
    sums = np.convolve(arr, kernel, mode="valid")
    idx = int(np.argmax(sums))
    return idx, float(sums[idx])
