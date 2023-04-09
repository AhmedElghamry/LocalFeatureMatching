import numpy as np
from audioop import reverse
from cmath import pi
from re import A
from typing import List
from unittest.mock import patch
import numpy as np
from copy import deepcopy
from scipy.signal import convolve2d, correlate2d
import cv2
from skimage.filters import scharr_h, scharr_v, sobel_h, sobel_v, gaussian


def get_interest_points(image, feature_width):
    """
    Returns interest points for the input image
    (Please note that we recommend implementing this function last and using cheat_interest_points()
    to test your implementation of get_features() and match_features())
    Implement the Harris corner detector (See Szeliski 4.1.1) to start with.
    You do not need to worry about scale invariance or keypoint orientation estimation
    for your Harris corner detector.
    You can create additional interest point detector functions (e.g. MSER)
    for extra credit.
    If you're finding spurious (false/fake) interest point detections near the boundaries,
    it is safe to simply suppress the gradients / corners near the edges of
    the image.
    Useful functions: A working solution does not require the use of all of these
    functions, but depending on your implementation, you may find some useful. Please
    reference the documentation for each function/library and feel free to come to hours
    or post on Piazza with any questions
        - skimage.feature.peak_local_max (experiment with different min_distance values to get good results)
        - skimage.measure.regionprops
    :params:
    :image: a grayscale or color image (your choice depending on your implementation)
    :feature_width:
    :returns:
    :xs: an np array of the x coordinates of the interest points in the image
    :ys: an np array of the y coordinates of the interest points in the image
    :optional returns (may be useful for extra credit portions):
    :confidences: an np array indicating the confidence (strength) of each interest point
    :scale: an np array indicating the scale of each interest point
    :orientation: an np array indicating the orientation of each interest point
    """
    threshold = 0.05

    rows, cols = image.shape

    xs = []
    ys = []
    rs = []

    image = cv2.GaussianBlur(image, ksize=(3, 3), sigmaX=8, sigmaY=8,
                             borderType=cv2.BORDER_CONSTANT)
    # get the gradients in the x and y directions using sobel filter

    I_x = cv2.Sobel(image, cv2.CV_32F, 1, 0)
    I_y = cv2.Sobel(image, cv2.CV_32F, 0, 1)

    Ixx = I_x**2
    Ixy = I_y*I_x
    Iyy = I_y**2

    # find the sum squared difference (SSD)
    for y in range(feature_width, rows-feature_width, 2):
        for x in range(feature_width, cols-feature_width, 2):
            Sxx = np.sum(Ixx[y-1:y+1, x-1:x+1])
            Syy = np.sum(Iyy[y-1:y+1, x-1:x+1])
            Sxy = np.sum(Ixy[y-1:y+1, x-1:x+1])

            # Find determinant and trace, use to get corner response

            detH = (Sxx * Syy) - (Sxy**2)
            traceH = Sxx + Syy
            r = detH - 0.06*(traceH**2)
            # If corner response is over threshold, it is a corner

            if r > threshold:
                xs.append(x)
                ys.append(y)
                rs.append(r)
    # we have a memory limitation where we cannpot store an array with shape == (3500>,128)
    # hence we check for the best 3500 points and include them in our calculations

    if (len(rs) > 3500):
        indices = np.argsort(rs)
        indices = indices[-3501:-1]
        xs = np.array(xs)
        ys = np.array(ys)
        xs = xs[indices]
        ys = ys[indices]

    return np.asarray(xs), np.asarray(ys)


def _image_gradient(image):
    '''
    This function calculates the magnitude and direction of pixel gradient
    Output: 
    gradient magnitude 
    gradient directions
    '''
    # # equation presented in David J lowe's paper
    # # page 13 under the section of orientation assignment
    # kx= [[0,0,0],[-1,0,1],[0,0,0]]
    # ky= [[0,1,0],[0,0,0],[0,-1,0]]
    # change_in_x= correlate2d(image,kx,'same')
    # change_in_y= correlate2d(image,ky,'same')
    # magnitude = np.sqrt(np.square(change_in_x) + np.square(change_in_y))
    # directions = np.arctan2(change_in_y,change_in_x)

    # we have used the sobel in our calculations instead of the equation
    # proposed in david j lowe'spaper as sobel gave us better results. We do think
    # that sobel has gave us better results bec it was much omre immune to
    # the very small changes.
    img_sobelx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)
    img_sobely = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)

    magnitude = np.sqrt(np.square(img_sobelx) + np.square(img_sobely))
    directions = np.arctan2(img_sobely, img_sobelx)

    return magnitude, directions


def _get_patch(img, featureLoc, window):
    '''
    This Function should return the patch around the feature 
    Assumption:
    1. img is 2D -One channel-    
    Output:
    16*16 np array
    '''

    assert len(img.shape) == 2

    featureLoc = [round(num) for num in featureLoc]

    # +1 because the pos at x,y is included
    startXpos = featureLoc[1] - window + 1
    # +1 bec in slicing the arrays are inclusive exclusive
    endXpos = featureLoc[1] + window + 1

    startYpos = featureLoc[0] - window + 1
    endYpos = featureLoc[0] + window + 1

    if startXpos < 0:
        endXpos = endXpos - startXpos
        startXpos = 0

    if startYpos < 0:
        endYpos = endYpos - startYpos
        startYpos = 0
    if endXpos > img.shape[0]:
        startXpos = startXpos + img.shape[0] - endXpos
        endXpos = img.shape[0]

    if endYpos > img.shape[1]:
        startYpos = startYpos + img.shape[1] - endYpos
        endYpos = img.shape[1]

    return img[startXpos: endXpos, startYpos:endYpos]


def _create_cells(mag: List[np.ndarray], dir: List[np.ndarray], cellWindow=4):
    '''
    This function divide the patch into list of cells
    Output 
    1. list of cells magntiude
    2. list of cells direction
    '''

    assert mag.shape == dir.shape

    # We will treat them at first as list bec its append has lower complexity
    cells_mag = list()
    cells_dir = list()
    for i in range(0, mag.shape[0], cellWindow):
        for j in range(0, mag.shape[1], cellWindow):
            cells_mag.append(mag[i:i+cellWindow, j:j+cellWindow])
            cells_dir.append(dir[i:i+cellWindow, j:j+cellWindow])
    return np.array(cells_mag), np.array(cells_dir)


def _make_histogram(cell_magnitude, cell_dir):
    '''
    This function retuns the histogram of each cell 
    the histogram has 8 elements each represents the mag in a given direction
    Output
    list
    '''
    assert cell_magnitude.shape == cell_dir.shape

    histo = np.zeros(8)
    cell_magnitude = cell_magnitude.reshape(-1)
    cell_dir = cell_dir.reshape(-1)

    histo = np.histogram(cell_dir, bins=8,
                         range=(-np.pi, np.pi), weights=cell_magnitude)[0]

    return histo.tolist()


def get_features(image, x, y, feature_width):
    """
    Returns feature descriptors for a given set of interest points.
    To start with, you might want to simply use normalized patches as your
    local feature. This is very simple to code and works OK. However, to get
    full credit you will need to implement the more effective SIFT-like descriptor
    (See Szeliski 4.1.2 or the original publications at
    http://www.cs.ubc.ca/~lowe/keypoints/)
    Your implementation does not need to exactly match the SIFT reference.
    Here are the key properties your (baseline) descriptor should have:
    (1) a 4x4 grid of cells, each feature_width / 4 pixels square.
    (2) each cell should have a histogram of the local distribution of
        gradients in 8 orientations. Appending these histograms together will
        give you 4x4 x 8 = 128 dimensions.
    (3) Each feature should be normalized to unit length
    You do not need to perform the interpolation in which each gradient
    measurement contributes to multiple orientation bins in multiple cells
    As described in Szeliski, a single gradient measurement creates a
    weighted contribution to the 4 nearest cells and the 2 nearest
    orientation bins within each cell, for 8 total contributions. This type
    of interpolation probably will help, though.
    You do not have to explicitly compute the gradient orientation at each
    pixel (although you are free to do so). You can instead filter with
    oriented filters (e.g. a filter that responds to edges with a specific
    orientation). All of your SIFT-like feature can be constructed entirely
    from filtering fairly quickly in this way.
    You do not need to do the normalize -> threshold -> normalize again
    operation as detailed in Szeliski and the SIFT paper. It can help, though.
    Another simple trick which can help is to raise each element of the final
    feature vector to some power that is less than one.
    Useful functions: A working solution does not require the use of all of these
    functions, but depending on your implementation, you may find some useful. Please
    reference the documentation for each function/library and feel free to come to hours
    or post on Piazza with any questions
        - skimage.filters (library)
    :params:
    :image: a grayscale or color image (your choice depending on your implementation)
    :x: np array of x coordinates of interest points
    :y: np array of y coordinates of interest points
    :feature_width: in pixels, is the local feature width. You can assume
                    that feature_width will be a multiple of 4 (i.e. every cell of your
                    local SIFT-like feature will have an integer width and height).
    If you want to detect and describe features at multiple scales or
    particular orientations you can add input arguments.
    :returns:
    :features: np array of computed features. It should be of size
            [len(x) * feature dimensionality] (for standard SIFT feature
            dimensionality is 128)
    """

    # TODO: Your implementation here! See block comments and the project webpage for instructions

    # This is a placeholder - replace this with your features!
    features = np.zeros((1, 128))
    features = list()
    bluredimage = cv2.GaussianBlur(image, ksize=(3, 3), sigmaX=8, sigmaY=8,
                                   borderType=cv2.BORDER_CONSTANT)

    gradMag, gradDir = _image_gradient(bluredimage)

    for featureLoc in zip(x, y):

        featureVector = list()

        mag = _get_patch(gradMag, featureLoc, feature_width//2)
        dir = _get_patch(gradDir, featureLoc, feature_width//2)
        # create 4*4 cells lists
        cellsMg, cellsDir = _create_cells(mag, dir, feature_width//4)
        # now create histogram for each cell
        for cell in zip(cellsMg, cellsDir):
            featureVector.extend(_make_histogram(cell[0], cell[1]))

        # extend was used bec, i need to make the histo grams in the same
        # list not to be a list of lists
        features.append(featureVector)

    features = np.array(features)

    # now we will normalize to reduce the effect of illumionization
    # normalize the feature vector
    scaler = features.max()
    features = features/scaler

    # putting thresshold then normalize again
    features[features > 0.2] = 0.2

    scaler = features.max()
    features = features/scaler
    # using the recommended trick that was recommended
    features = features**0.8
    return features


def match_features(im1_features, im2_features):
    """
    Implements the Nearest Neighbor Distance Ratio Test to assign matches between interest points
    in two images.
    Please implement the "Nearest Neighbor Distance Ratio (NNDR) Test" ,
    Equation 4.18 in Section 4.1.3 of Szeliski.
    For extra credit you can implement spatial verification of matches.
    Please assign a confidence, else the evaluation function will not work. Remember that
    the NNDR test will return a number close to 1 for feature points with similar distances.
    Think about how confidence relates to NNDR.
    This function does not need to be symmetric (e.g., it can produce
    different numbers of matches depending on the order of the arguments).
    A match is between a feature in im1_features and a feature in im2_features. We can
    represent this match as a the index of the feature in im1_features and the index
    of the feature in im2_features
    :params:
    :im1_features: an np array of features returned from get_features() for interest points in image1
    :im2_features: an np array of features returned from get_features() for interest points in image2
    :returns:
    :matches: an np array of dimension k x 2 where k is the number of matches. The first
            column is an index into im1_features and the second column is an index into im2_features
    :confidences: an np array with a real valued confidence for each match
    """
    dist = np.zeros((im1_features.shape[0], im2_features.shape[0]))

    matches = []
    confidences = []

    threshold = 0.8

    for i in range(im1_features.shape[0]):
        for y in range(im2_features.shape[0]):

            x_features = im1_features[i]
            y_features = im2_features[y]

            sub = (x_features - y_features) ** 2
            Sum = sub.sum()
            Sum = np.sqrt(Sum)
            dist[i, y] = Sum

        sorted_index = np.argsort(dist[i])
        ratio = (dist[i, sorted_index[0]] / dist[i, sorted_index[1]])

        if ratio < threshold:
            matches.append([i, sorted_index[0]])
            confidences.append(dist[i, sorted_index[0]])

    return np.asarray(matches), np.asarray(confidences)
