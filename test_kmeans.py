import numpy as np

def kmeans_1d_threshold(values: np.ndarray) -> float:
    if len(values) < 2: return 2.80
    centers = np.percentile(values, [25, 75])
    for _ in range(20):
        dists = np.abs(values[:, None] - centers[None, :])
        labels = dists.argmin(axis=1)
        for i in range(2):
            if (labels == i).any():
                centers[i] = values[labels == i].mean()
    centers.sort()
    return float(np.mean(centers))

v = np.array([0.5, 0.6, 0.7, 3.1, 3.2, 3.3])
print(kmeans_1d_threshold(v))
