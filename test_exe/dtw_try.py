import numpy as np
import math
from dtaidistance import dtw_ndim
from dtaidistance import dtw_visualisation as dtwvis

def DTW(S1: np.array, S2: np.array):
    distance = dtw_ndim.distance(S1, S2)
    return distance


def get_elementwise_distances(s1, s2, path):
    elementwise_distances = []
    total_distance = 0.0
    for p in path:
        distance = np.sum((s1[p[0]] - s2[p[1]]) ** 2)
        elementwise_distances.append(distance)
        total_distance += distance
    total_distance = np.sqrt(total_distance)
    return elementwise_distances, total_distance


x = np.arange(0, 13)
A = np.sin([i/12*math.pi  for i in x])
t=np.arange(0,17)
B=np.sin([i/16 * math.pi for i in t])
print(np.shape(A))

#path = dtw_ndim.warping_path(A, B)
#dtwvis.plot_warping(A, B, path, filename="warp.png")
'''
x = np.arange(0, 13)
A = np.sin([[k*i/12*math.pi for k in range(1,9)] for i in x])
t=np.arange(0,17)
B=np.sin([[k*i/16 * math.pi for k in range(1,9)]  for i in t])
print(np.shape(A))

A1=np.squeeze(A[:,5])
B1=np.squeeze(B[:,5])
print(A1)
print(np.shape(B1))
'''
A=np.array([[[1,2],[3,4],[2,7]],[[1,4],[2,5],[4,3]],[[3,11],[6,15],[8,6]]])
B=np.array([[[1,3],[3,5],[4,14]],[[2,8],[4,10],[8,6]]])
print(DTW(A,B))
path = dtw_ndim.warping_path(A, B)

print(get_elementwise_distances(A,B,path))

'''
for p in path:
    a = A[0]
    b = B[1]
'''
print(path)
#print(np.shape(dtw_ndim.distance_matrix(A,B)))
print(A[:, 0, 0])
dtwvis.plot_warping(A[:, 0, 0], B[:, 0, 0], path, filename="warp.png")
