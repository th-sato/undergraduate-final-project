import cv2 as cv
import base64
import os.path
import numpy as np
from constants.constants import AXIS_Y_METERS_PER_PIXEL, WIDTH_LANE, RED, BLUE, GREEN

# Global variables
LOCAL_PATH = os.path.dirname(__file__)  # get current directory


def show_image(img):
    cv.imshow('image', img)
    # cv.waitKey(10)
    cv.waitKey(0)
    # cv.destroyAllWindows()


def jpgimg_to_base64(img):
    ret, jpg = cv.imencode('.jpg', img)
    return base64.b64encode(jpg)


def add_text_to_image(img, curv, center):
    font = cv.FONT_HERSHEY_SIMPLEX
    cv.putText(img, 'Radius of Curvature = %d(m)' % curv, (50, 50), font, 0.7, (255, 255, 255), 1)

    left_or_right = "left" if center < 0 else "right"
    cv.putText(img, 'Vehicle is %.2fcm %s of center' % (np.abs(center), left_or_right), (50, 100), font, 0.7,
                (255, 255, 255), 1)


# img_binary contains only 0 or 255
def detect_street(img, lower_color, upper_color):
    img_hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)
    # interval = img.shape[0] / 2, int(img.shape[0] * (1.0 - 1.0 / 8.0))
    # img_hsv = img_hsv[interval[0]:interval[1], :]
    # Threshold the HSV image to get only the selected colors
    img_processed = cv.inRange(img_hsv, lower_color, upper_color)
    img_processed[img_processed == 255] = 1
    return img_processed


# Disconsider the proximity points of peak_one
def _disconsider_proximity_points(histogram, peak, space_lines):
    histogram_length = histogram.shape[0]  # Length of histogram

    # Left proximity
    if (peak - space_lines) < 0:
        histogram[0: peak] = 0
    else:
        histogram[(peak - space_lines): peak] = 0
    # Right proximity
    if (peak + space_lines) > (histogram_length - 1):
        histogram[peak: (histogram_length - 1)] = 0
    else:
        histogram[peak: (peak + space_lines)] = 0

    return histogram


def _find_peaks_of_image(histogram):
    space_lines = 110                               # Set the space between track lines
    histogram_min_value = 100                       # Value to consider that the point is valid
    left_line, right_line = None, None              # Defining the value of lines
    histogram_length = histogram.shape[0]           # Length of histogram
    peak_one = np.argmax(histogram)                 # Find one of the Peaks in Histogram

    histogram = _disconsider_proximity_points(histogram, peak_one, space_lines)
    peak_two = np.argmax(histogram)

    if histogram[peak_one] > histogram_min_value:
        if peak_one > np.int(histogram_length/2):   # Peak relative with right line
            right_line = peak_one
        else:                                       # Peak relative with left line
            left_line = peak_one

    if histogram[peak_two] > histogram_min_value:
        if peak_two > np.int(histogram_length/2):   # Peak relative with right line
            right_line = peak_two
        else:                                       # Peak relative with left line
            left_line = peak_two

    return right_line, left_line


# Functions for drawing lines
def fit_lines(binary_img):
    nwindows = 50           # Choose the number of sliding windows
    margin = 30             # Set the width of the windows +/- margin
    minpix = 10             # Set minimum number of pixels found to recenter window
    interval_img = 9/10     # Histogram interval to take in image
    # Create empty lists to receive left and right lane pixel indices
    left_lane_inds = []
    right_lane_inds = []

    binary_warped = binary_img
    height_img, width_img = binary_warped.shape
    # Assuming you have created a warped binary image called "binary_warped"
    # Take a histogram of the bottom half of the image
    boundary_histogram = np.int(height_img*interval_img)
    histogram = np.sum(binary_warped[boundary_histogram:, :], axis=0)
    # Create an output image to draw on and  visualize the result
    out_img = np.dstack((binary_warped, binary_warped, binary_warped)) * 255
    # Find the peak of the left and right halves of the histogram
    left_x_base, right_x_base = _find_peaks_of_image(histogram)

    # Set height of windows
    window_height = np.int(height_img / nwindows)
    # Identify the x and y positions of all nonzero pixels in the image
    nonzero = binary_warped.nonzero()
    nonzero_y = np.array(nonzero[0])
    nonzero_x = np.array(nonzero[1])

    # Current positions to be updated for each window
    left_x_current = left_x_base
    right_x_current = right_x_base

    # Step through the windows one by one
    for window in range(nwindows):
        # Identify window boundaries in x and y (and right and left)
        win_y_low = binary_warped.shape[0] - (window + 1) * window_height
        win_y_high = binary_warped.shape[0] - window * window_height
        win_x_left_low = left_x_current - margin
        win_x_left_high = left_x_current + margin
        win_x_right_low = right_x_current - margin
        win_x_right_high = right_x_current + margin
        # Draw the windows on the visualization image
        # Identify the nonzero pixels in x and y within the window
        good_left_inds = ((nonzero_y >= win_y_low) & (nonzero_y < win_y_high) & (nonzero_x >= win_x_left_low) & (
                    nonzero_x < win_x_left_high)).nonzero()[0]
        good_right_inds = ((nonzero_y >= win_y_low) & (nonzero_y < win_y_high) & (nonzero_x >= win_x_right_low) & (
                    nonzero_x < win_x_right_high)).nonzero()[0]
        # Append these indices to the lists
        left_lane_inds.append(good_left_inds)
        right_lane_inds.append(good_right_inds)
        # If you found > minpix pixels, recenter next window on their mean position
        if len(good_left_inds) > minpix:
            left_x_current = np.int(np.mean(nonzero_x[good_left_inds]))
        if len(good_right_inds) > minpix:
            right_x_current = np.int(np.mean(nonzero_x[good_right_inds]))

    # Concatenate the arrays of indices
    left_lane_inds = np.concatenate(left_lane_inds)
    right_lane_inds = np.concatenate(right_lane_inds)

    # Extract left and right line pixel positions
    left_x = nonzero_x[left_lane_inds]
    left_y = nonzero_y[left_lane_inds]
    right_x = nonzero_x[right_lane_inds]
    right_y = nonzero_y[right_lane_inds]

    # Fit a second order polynomial to each
    left_fit = np.polyfit(left_y, left_x, 2)
    right_fit = np.polyfit(right_y, right_x, 2)

    out_img[nonzero_y[left_lane_inds], nonzero_x[left_lane_inds]] = RED
    out_img[nonzero_y[right_lane_inds], nonzero_x[right_lane_inds]] = BLUE

    return left_fit, right_fit, out_img.shape


# Calculate Curvature
def curvature(left_fit, right_fit, image_shape):
    # xm_per_pix = AXIS_X_METERS_PER_PIXEL  # meters per pixel in x dimension
    ym_per_pix = AXIS_Y_METERS_PER_PIXEL  # meters per pixel in y dimension
    height_img, width_img, _ = image_shape
    center_image = width_img / 2

    plot_y = np.linspace(0, height_img - 1, height_img)
    # Define y-value where we want radius of curvature
    # I'll choose the maximum y-value, corresponding to the bottom of the image
    y_eval = np.max(plot_y)

    # Define left and right lanes in pixels
    left_x = left_fit[0] * plot_y ** 2 + left_fit[1] * plot_y + left_fit[2]
    right_x = right_fit[0] * plot_y ** 2 + right_fit[1] * plot_y + right_fit[2]

    # Calculation of center
    # left_lane and right lane bottom in pixels
    left_lane_bottom = left_fit[0] * y_eval ** 2 + left_fit[1] * y_eval + left_fit[2]
    right_lane_bottom = right_fit[0] * y_eval ** 2 + right_fit[1] * y_eval + right_fit[2]
    # Lane center as mid of left and right lane bottom

    xm_per_pix = np.abs(WIDTH_LANE / (right_lane_bottom - left_lane_bottom))
    lane_center = (left_lane_bottom + right_lane_bottom) / 2.
    distance_center = (lane_center - center_image) * xm_per_pix  # Convert to meters

    # Identify new coefficients in meters
    left_fit_cr = np.polyfit(plot_y * ym_per_pix, left_x * xm_per_pix, 2)
    right_fit_cr = np.polyfit(plot_y * ym_per_pix, right_x * xm_per_pix, 2)

    # Calculate the new radius of curvature
    left_curverad = ((1 + (2 * left_fit_cr[0] * y_eval * ym_per_pix + left_fit_cr[1]) ** 2) ** 1.5) / np.absolute(
        2 * left_fit_cr[0])
    right_curverad = ((1 + (2 * right_fit_cr[0] * y_eval * ym_per_pix + right_fit_cr[1]) ** 2) ** 1.5) / np.absolute(
        2 * right_fit_cr[0])

    return left_curverad, right_curverad, left_x, right_x, distance_center


def draw_lines(img, left_fit_x, right_fit_x):
    # Create an image to draw the lines on
    img_zeros = np.zeros_like(img)

    ploty = np.linspace(0, img.shape[0] - 1, img.shape[0])

    # Recast the x and y points into usable format for cv2.fillPoly()
    pts_left = np.array([np.transpose(np.vstack([left_fit_x, ploty]))])
    pts_right = np.array([np.flipud(np.transpose(np.vstack([right_fit_x, ploty])))])
    pts = np.hstack((pts_left, pts_right))

    # Draw the lane onto the warped blank image
    cv.fillPoly(img_zeros, np.array([pts], dtype=np.int32), GREEN)
    return cv.addWeighted(img, 1, img_zeros, 0.8, 0)
