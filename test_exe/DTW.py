import numpy as np
import math
from dtaidistance import dtw_ndim
from dtaidistance import dtw_visualisation as dtwvis

def getDistance(S1: np.array, S2: np.array):
    '''
    this function get the DTW distance between S1 and S2
    Args: S1, S2: 2 time  series 
    return: distance
    '''
    distance = dtw_ndim.distance(S1, S2)
    return distance

def getPath(s1,s2): # from s1 to s2
    '''
    get the corresonding path which is from s1 to s2
    Args: S1, S2: 2 time  series 
    '''    
    return dtw_ndim.warping_path(s1,s2)

def get_elementwise_distances(s1, s2, path):
    '''
    get the distance between the point1 from s1 and point2 from s2 according to the given path
    Arggs: s1,s2 : time series
           path:   a path which is from s1 to s2
    '''
    elementwise_distances = []
    for p in path:
        distance = np.sum((s1[p[0]] - s2[p[1]]) ** 2)
        elementwise_distances.append(distance)
    return elementwise_distances


def plotWrap(s1,s2,filename):# from s1 to s2
    '''
    plot the path between s1,s2

    Args: s1, s2 : time series( must be one dimesion)
    '''
    path = dtw_ndim.warping_path(s1, s2)
    dtwvis.plot_warping(s1, s2, path, filename)





def getMinPath_Distance(path,distance):
    '''
        get the path and corresponding distance in each path with the same y ,  asuming that path like (x,y) 
        Args: paths : the paths between time series s1 and s2
              distance: corresponding distace regards to the path
    '''
    min_distances = {}  # Dictionary to store minimal distances and corresponding x-coordinates for each y-coordinate

    for i in range(len(path)):
        x, y = path[i]
        dist = distance[i]

        if y not in min_distances:
            min_distances[y] = {'x': x, 'y': y, 'distance': dist}
        else:
            if dist < min_distances[y]['distance']:
                min_distances[y]['x'] = x
                min_distances[y]['distance'] = dist

    # Print the minimal distances, x-coordinates, and y-coordinates for each unique y-coordinate
    min_path=[]
    min_dis=[]
    for y, data in min_distances.items():
        #print(f"For y={y}: x={data['x']}, y={data['y']}, distance={data['distance']}")
        min_path.append((data['x'],data['y']))
        min_dis.append(data['distance'])
    return min_path,min_dis

def getMaxIndex_Item(a:list,framecout=1):
    '''
    The function calculates the sum of consecutive sublists of length framecout in the input list a. It then returns the index and value of the maximum sum found.
    Args:  a: a list
           framecount:  the length that sum up, default is 1
    '''
    b=[]
    for i in range(0,len(a)-framecout+1):
        m=sum(a[i:i+framecout])
        b.append(m)
    max_item=max(b)
    max_index=b.index(max_item)
    return max_index,max_item
    

