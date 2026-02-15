import math
import pandas as pd
import numpy as np
import DTW as DTW
from view_image import view_imageseries ,showImage,showvideo
from save3D import save3D
import cv2
import argparse,sys
import os

features = [
(5,6),(6,7),
(12,13),(13,14),
(18,19),(19,20),
(22,23),(23,24),
(5,12)
]


def getVector(B,A):
    '''
    get the vector from B to A 
    Args:
        A,B : point
    '''
    return [A[0]-B[0], A[1]-B[1],A[2]-B[2]]



def GetAngle(A,B):
     '''
     get the angle between vector A and B in  radians
     Args:
         A,B: vector
     '''
     a = min( (A[0]*B[0]+A[1]*B[1]+A[2]*B[2])/(math.sqrt(A[0]**2+A[1]**2+A[2]**2)*math.sqrt(B[1]**2+B[2]**2+B[0]**2)),1)
     a = max(a,-1)
     return math.acos(a)
    #return math.acos((A[0]*B[0]+A[1]*B[1]+A[2]*B[2])/(math.sqrt(A[0]**2+A[1]**2+A[2]**2)*math.sqrt(B[1]**2+B[2]**2+B[0]**2)))
     #return (A[0]*B[0]+A[1]*B[1]+A[2]*B[2])/(math.sqrt(A[0]**2+A[1]**2+A[2]**2)*math.sqrt(B[1]**2+B[2]**2+B[0]**2))


def update(frame,bodies):
    '''
    get the all 32 body joints position in a given body at a given frame
    Args:
        frame: the particular frame
        bodies: the body 
    '''

    body = bodies[frame]

    x = [joint['position'][0] for joint in body['joints']]
    y = [joint['position'][1] for joint in body['joints']]
    z = [joint['position'][2] for joint in body['joints']]
    return x,y,z

#
def getPosition(bodies,frame,idx):
    '''
     get the position of  a specific body joint(determined by idx) from a particular frame
     Args: idx: the index of the body joint
    '''
    x,y,z=update(frame,bodies)
    return[x[idx],y[idx],z[idx]]

#
def IfOnSameSide(bodies,frame):
    SPINE_CHEST=getPosition(bodies,frame,2)
    WRIST_LEFT=getPosition(bodies,frame,7)
    WRIST_RIGHT=getPosition(bodies,frame,14)
    if((WRIST_RIGHT[0]-SPINE_CHEST[0])*(WRIST_LEFT[0]-SPINE_CHEST[0])>0):
        if( WRIST_LEFT[2]-WRIST_RIGHT[2]>0):
            #return True,(5,6),(6,7)
            return True,0,1
        else:
            #return True,(12,13),(13,14)
            return True,2,3
    else:
        return False,-1,-1

def getAnglesVariation(bodies,features,interval:int):
    '''
     get the variation of angles from same body part in different frames (note: return value is end with degree)
    '''
    angles=[[None] * (len(features)) for _ in range(len(bodies)-interval)]
    for i,feature in enumerate( features):
        f_1 = feature[0]
        f_2 =feature[1]
        for frame in range(0,len(bodies)-interval):
            a_1 = getPosition(bodies,frame,f_1)
            b_1= getPosition(bodies,frame,f_2)
            a_2=getPosition(bodies,frame+interval,f_1)
            b_2=getPosition(bodies,frame+interval,f_2)
            A=getVector(a_1,b_1)
            B=getVector(a_2,b_2)

            angle=int(GetAngle(A,B)/math.pi*180)
            angles[frame] [i] = angle
    return angles

# 
def getAnglesToZaxle(bodies,features):
     '''
          get the angle between part of body and Z axle
          Args:
                Bodies: the body
                feature: for instance:[(1,3),(1,3)] (A,B) connecting the bodt joint A and B to become a skleton
     '''
     angles=[[None] * (len(features)) for _ in range(len(bodies))]
     for i,feature in enumerate( features):
        f_1 = feature[0]
        f_2 =feature[1]
        for frame in range(0,len(bodies)):
            a_1 = getPosition(bodies,frame,f_1)
            b_1= getPosition(bodies,frame,f_2)
            A=getVector(a_1,b_1)
            Z=[0,1,0]
            angle=int(GetAngle(A,Z)/math.pi*180)

            angles[frame] [i] = angle
        
     return angles   


def getAnglesToaxle(bodies,features,blind=False):
     '''
          get the angle between part of body and there axles(Y,Z,X )
          Args:
                Bodies: the body
                feature: for instance:[(1,3),(1,3)] (A,B) connecting the bodt joint A and B to become a skleton
                Blind: if blind = True, then it will ignore the covered arm if both arms are in the same side
     '''

     angles=[[[None for _ in range(len(features))] for _ in range(3)] for _ in range(len(bodies))]
     for i,feature in enumerate( features):
        f_1 = feature[0]
        f_2 =feature[1]
        for frame in range(0,len(bodies)):
            a_1 = getPosition(bodies,frame,f_1)
            b_1= getPosition(bodies,frame,f_2)
            A=getVector(a_1,b_1)
            Z=[0,1,0]
            y=[0,0,1]
            x=[1,0,0]
            anglez=int(GetAngle(A,Z)/math.pi*180)
            angley=int(GetAngle(A,y)/math.pi*180)
            anglex = int(GetAngle(A,x)/math.pi*180)
            angles[frame][0] [i] = anglez
            angles[frame][1] [i] = angley
            angles[frame][2] [i] = anglex
     if(blind):
        for frame in range(0,len(bodies)):
            T,A_1,A_2=IfOnSameSide(bodies,frame)
            if(T):
                angles[frame][0][A_1]=0
                angles[frame][1][A_1]=0
                angles[frame][2][A_1]=0
                angles[frame][0][A_2]=0
                angles[frame][1][A_2]=0
                angles[frame][2][A_2]=0
        
     return angles   

def GaussianFilter(A:np.array,sigma=1):
    '''
    Use Gaussian distribution to filter the data in each column
    Args:
         A: numpy array that be filtered
         sigma: the sigma for Gaussian distribution, must be a possiitive and  odd number, default with 1
    '''
    B=np.zeros_like(A)
    for i in range(A.shape[1]):
        for j in range(A.shape[2]):
            column=(A[:,i,j])
            filtercolumn = cv2.GaussianBlur(column,(0,0),sigma)
            B[:,i,j]=filtercolumn.reshape(-1)
    return(B)


# find the plane form two non-parallel vector
def find_plane(vector1, vector2):
    vector1=np.array(vector1)
    vector2=np.array(vector2)
    normal_vector = np.cross(vector1, vector2)
    d = -np.dot(normal_vector, vector1)
    return normal_vector, d

# find the orthogonal plane from the plane and cross the given vector
def find_orthogonal_plane(normal_plane, vector_on_plane):
    #normal_plane_normalized = normal_plane / np.linalg.norm(normal_plane)
    orthogonal_normal = np.cross(normal_plane, vector_on_plane)
    d = -np.dot(orthogonal_normal, vector_on_plane)
    return orthogonal_normal, d

def getAngleFromPlane(norma_plane,vector):
    vector=np.array(vector)
    a= min( norma_plane@vector/(np.sqrt(norma_plane@norma_plane)*np.sqrt(vector@vector)),1)
    a = max(a,-1)
    return np.arccos(a).item()  #convert the np.array to float type

# get the angles bwtween features and two specified planes,  return a 2*n array
def getFeatuesAnglesFromPlane(bodies,features,frame,plane_1,plane_2):
    angles=[[None] * (len(features)) for _ in range(2)]
    for i,feature in enumerate(features):
        f_1,f_2=feature
        p_1 =getPosition(bodies,frame,f_1)
        p_2 =getPosition(bodies,frame,f_2)
        skleton = getVector(p_1,p_2)
        angle1 = int(getAngleFromPlane(plane_1,skleton)/math.pi*180)
        angle2 = int(getAngleFromPlane(plane_2,skleton)/math.pi*180)
        angles[0][i]=angle1
        angles[1][i] =angle2
    return angles
    


def getMostFeatures(BodiesAngles_From,BodiesAngles_TO,id_from,id_to):
    Angles_From=BodiesAngles_From(id_from)
    Angles_To=BodiesAngles_TO(id_to)


def getBodiesFromFile(filename):
    '''
    get the information of a body from a given file
    '''
    with open(filename, 'r') as file:
        lines = file.readlines()

    bodies = []
    current_body={}
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
    return(bodies)


def getScore(element_distance):
    punishment=[]
    #p=[]
    #p=[math.sqrt(dis)-100 for dis in element_distance if math.sqrt(dis) > 100 ]
    #print(p)
    punishment = [(math.sqrt(dis)-100)**1.5 for dis in element_distance if math.sqrt(dis) > 100]

    score_a = sum(punishment)*len(punishment)/len(element_distance)
    #score_a = sum((math.sqrt(dis) - 100)  for dis in element_distance if math.sqrt(dis) > 100)
    score_b= math.sqrt(sum(element_distance)/len(element_distance))
    score = 0.2*score_a + 0.8*score_b

    return 100-0.1*score  if 100-0.1*score >0 else 0


def getargs(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        description='tow folder', add_help=True, usage=" ")
    parser.add_argument("--folder_tutor", default="NULL",
                        help='the floder example')
    parser.add_argument("--folder_customer", default="NULL",
                        help='the folder for customer')
    parser.add_argument("--function",default='NULL',help=' select from showVideos,score,showMaxDiffetence')
    args1 = parser.parse_args()
    return args1

def main():
    args = getargs(sys.argv[1:])
    folder_tutor=args.folder_tutor
    folder_customer=args.folder_customer
    function =args.function
    analyse_folder = f'{folder_customer}\\analyse'
    if  os.path.exists(analyse_folder):
        if os.listdir(analyse_folder):
            showvideo(analyse_folder)
            return 0
    bodies_A=getBodiesFromFile(f"{folder_tutor}\\output2.txt")
    bodies_B=getBodiesFromFile(f"{folder_customer}\\output2.txt")
 


    Angle_A=getAnglesToaxle(bodies_A,features,blind=False)
    Angle_B=getAnglesToaxle(bodies_B,features,blind=False)

   

    Angle_A=np.array(Angle_A,dtype=np.float32)
    Angle_B=np.array(Angle_B,dtype=np.float32)

    Angle_A = GaussianFilter(Angle_A,3)
    Angle_B = GaussianFilter(Angle_B,3)
    
    paths  = DTW.getPath(Angle_B,Angle_A)
    element_distance =DTW.get_elementwise_distances(Angle_B,Angle_A,paths )

    min_paths,min_distance=DTW.getMinPath_Distance(paths,element_distance)


    max_Index,max_Item=DTW.getMaxIndex_Item(min_distance,1)
    if(function=='score'):
        score =getScore(min_distance)
        print(score)
   
    elif(function=="showVideos"):
        output_folder = f'{folder_customer}\\plot'
        if not os.path.exists(output_folder):
            os.mkdir(output_folder)
        DTW.plotWrap(Angle_B[:,0,1],Angle_A[:,0,1],f'{output_folder}\\wrap.jpg')
        save3D(folder=folder_customer)
        view_imageseries(path=min_paths,elementdistance=min_distance,folder1_path=folder_customer,folder2_path=folder_tutor,folder1_path_3d=f'{folder_customer}\\3D',plot_path=f'{folder_customer}\\plot')

    elif (function=="showMaxDiffetence"):
        showImage(f"{folder_customer}\\imamge_idx_{min_paths[max_Index][0]}.jpg",f"{folder_tutor}\\imamge_idx_{min_paths[max_Index][1]}.jpg")

if __name__ == "__main__": 
    main()
        



