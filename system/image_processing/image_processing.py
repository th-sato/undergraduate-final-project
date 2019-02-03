import cv2
import pickle
import os.path
import numpy as np
import matplotlib.pyplot as plt

# Global variables
LOCAL_PATH = os.path.dirname(__file__)  # get current directory


def encode_img_jpg(img):
    return cv2.imencode('.jpg', img)


def rescale_to_8_bit(img):
    return np.uint8(255 * img / np.max(img))


def main_condition_thresholding(img, thresh):
    return np.zeros_like(img), (img >= thresh[0]) & (img <= thresh[1])


# Create binary image using thresholding
def binary_img(image, condition_thresh):
    image[condition_thresh] = 1
    return image


def add_text_to_image(img, left_cur, right_cur, center):
    cur = (left_cur + right_cur)/2.

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, 'Radius of Curvature = %d(m)' % cur, (50, 50), font, 1, (255, 255, 255), 2)

    left_or_right = "left" if center < 0 else "right"
    cv2.putText(img, 'Vehicle is %.2fm %s of center' % (np.abs(center), left_or_right), (50, 100), font, 1,
                (255, 255, 255), 2)


def grayscale(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Or use RGB2GRAY if you read an image with mpimg


def gaussian_blur(img, kernel_size):
    """Applies a Gaussian Noise kernel"""
    return cv2.GaussianBlur(img, (kernel_size, kernel_size), 0)


def undistort(img):
    file_path = os.path.join(LOCAL_PATH, 'calibration/calibration_pickle.p')
    # open("nome_arquivo", "modo") ==> r: read e b: binary mode (image)
    cal_pickle = pickle.load(open(file_path, "rb"))
    mtx = cal_pickle["mtx"]
    dist = cal_pickle["dist"]
    return cv2.undistort(img, mtx, dist, None, mtx)


def x_thresh(img, sobel_kernel=3, thresh=(0, 255)):
    gray = grayscale(img)
    # Take only Sobel x
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=sobel_kernel)
    # Calculate the absolute value of the x derivative:
    abs_sobelx = np.absolute(sobelx)
    # Convert the absolute value image to binary:
    return binary_img(*main_condition_thresholding(rescale_to_8_bit(abs_sobelx), thresh))


def mag_thresh(img, sobel_kernel=3, thresh=(0, 255)):
    # Convert to grayscale
    gray = grayscale(img)
    # Take both Sobel x and y gradients
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=sobel_kernel)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=sobel_kernel)
    # Calculate the gradient magnitude
    gradmag = np.sqrt(sobelx**2 + sobely**2)
    return binary_img(*main_condition_thresholding(rescale_to_8_bit(gradmag), thresh))


def dir_threshold(img, sobel_kernel=3, thresh=(0, np.pi/2)):
    gray = grayscale(img)
    # Take both Sobel x and y gradients
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=sobel_kernel)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=sobel_kernel)
    # Calculate the gradient magnitude
    abs_sobelx = np.absolute(sobelx)
    abs_sobely = np.absolute(sobely)
    # -pi/2 < arctg(x) < pi/2
    return binary_img(*main_condition_thresholding(np.arctan2(abs_sobely, abs_sobelx), thresh))


def hsv_select(img, thresh_low, thresh_high):
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    # height, width, channels = img.shape
    return binary_img(np.zeros((img.shape[0], img.shape[1])),
                      (hsv[:, :, 0] >= thresh_low[0]) & (hsv[:, :, 0] <= thresh_high[0])
                      & (hsv[:, :, 1] >= thresh_low[1]) & (hsv[:, :, 1] <= thresh_high[1])
                      & (hsv[:, :, 2] >= thresh_low[2]) & (hsv[:, :, 2] <= thresh_high[2]))


def hls_select(img, thresh=(0, 255)):
    hls = cv2.cvtColor(img, cv2.COLOR_RGB2HLS)
    return binary_img(*main_condition_thresholding(hls[:, :, 2], thresh))


def warp(img):
    # height, width, channels = img.shape
    img_size = (img.shape[1], img.shape[0])

    src = np.float32([[800, 510], [1150, 700], [270, 700], [510, 510]])
    dst = np.float32([[650, 470], [640, 700], [270, 700], [270, 510]])

    m = cv2.getPerspectiveTransform(src, dst)
    # inverse
    m_inv = cv2.getPerspectiveTransform(dst, src)
    # create a warped image
    warped = cv2.warpPerspective(img, m, img_size, flags=cv2.INTER_LINEAR)
    unpersp = cv2.warpPerspective(warped, m_inv, img_size, flags=cv2.INTER_LINEAR)

    return warped, unpersp, m_inv


# Define a function for creating lane lines
def lane_detector(img):
    # Define a kernel size and apply Gaussian smoothing
    kernel_size = 5
    undist = gaussian_blur(undistort(img), kernel_size)

    # Define parameters for gradient thresholding
    sxbinary = x_thresh(undist, sobel_kernel=3, thresh=(22, 100))

    # Define parameters for color thresholding
    s_binary = hls_select(undist, thresh=(90, 255))

    # Combine the two binary thresholds
    combined_binary = np.zeros_like(sxbinary)
    combined_binary[(s_binary == 1) | (sxbinary == 1)] = 1

    # Apply perspective transform
    # Define points
    warped_im, _, m_inv = warp(combined_binary)

    return undist, sxbinary, s_binary, combined_binary, warped_im, m_inv


# Functions for drawing lines
def fit_lines(img, plot=True):
    binary_warped = img.copy()
    # Assuming you have created a warped binary image called "binary_warped"
    # Take a histogram of the bottom half of the image
    histogram = np.sum(binary_warped[binary_warped.shape[0] / 2:, :], axis=0)
    # Create an output image to draw on and  visualize the result
    out_img = np.dstack((binary_warped, binary_warped, binary_warped)) * 255
    # Find the peak of the left and right halves of the histogram
    # These will be the starting point for the left and right lines
    # Make this more robust
    midpoint = np.int(histogram.shape[0] / 4)  # lanes aren't always centered in the image
    leftx_base = np.argmax(histogram[150:midpoint]) + 150  # Left lane shouldn't be searched from zero
    rightx_base = np.argmax(histogram[midpoint: midpoint + 500]) + midpoint

    # Choose the number of sliding windows
    nwindows = 9
    # Set height of windows
    window_height = np.int(binary_warped.shape[0] / nwindows)
    # Identify the x and y positions of all nonzero pixels in the image
    nonzero = binary_warped.nonzero()
    nonzeroy = np.array(nonzero[0])
    nonzerox = np.array(nonzero[1])
    # Current positions to be updated for each window
    leftx_current = leftx_base
    rightx_current = rightx_base
    # Set the width of the windows +/- margin
    margin = 80
    # Set minimum number of pixels found to recenter window
    minpix = 70
    # Create empty lists to receive left and right lane pixel indices
    left_lane_inds = []
    right_lane_inds = []
    # Step through the windows one by one
    for window in range(nwindows):
        # Identify window boundaries in x and y (and right and left)
        win_y_low = binary_warped.shape[0] - (window + 1) * window_height
        win_y_high = binary_warped.shape[0] - window * window_height
        win_xleft_low = leftx_current - margin
        win_xleft_high = leftx_current + margin
        win_xright_low = rightx_current - margin
        win_xright_high = rightx_current + margin
        # Draw the windows on the visualization image
        cv2.rectangle(out_img, (win_xleft_low, win_y_low), (win_xleft_high, win_y_high), (0, 255, 0), 2)
        cv2.rectangle(out_img, (win_xright_low, win_y_low), (win_xright_high, win_y_high), (0, 255, 0), 2)
        # Identify the nonzero pixels in x and y within the window
        good_left_inds = ((nonzeroy >= win_y_low) & (nonzeroy < win_y_high) & (nonzerox >= win_xleft_low) & (
                    nonzerox < win_xleft_high)).nonzero()[0]
        good_right_inds = ((nonzeroy >= win_y_low) & (nonzeroy < win_y_high) & (nonzerox >= win_xright_low) & (
                    nonzerox < win_xright_high)).nonzero()[0]
        # Append these indices to the lists
        left_lane_inds.append(good_left_inds)
        right_lane_inds.append(good_right_inds)
        # If you found > minpix pixels, recenter next window on their mean position
        if len(good_left_inds) > minpix:
            leftx_current = np.int(np.mean(nonzerox[good_left_inds]))
        if len(good_right_inds) > minpix:
            rightx_current = np.int(np.mean(nonzerox[good_right_inds]))

    # Concatenate the arrays of indices
    left_lane_inds = np.concatenate(left_lane_inds)
    right_lane_inds = np.concatenate(right_lane_inds)

    # Extract left and right line pixel positions
    leftx = nonzerox[left_lane_inds]
    lefty = nonzeroy[left_lane_inds]
    rightx = nonzerox[right_lane_inds]
    righty = nonzeroy[right_lane_inds]

    # Fit a second order polynomial to each
    left_fit = np.polyfit(lefty, leftx, 2)
    right_fit = np.polyfit(righty, rightx, 2)

    # Generate x and y values for plotting
    ploty = np.linspace(0, binary_warped.shape[0] - 1, binary_warped.shape[0])
    left_fitx = left_fit[0] * ploty ** 2 + left_fit[1] * ploty + left_fit[2]
    right_fitx = right_fit[0] * ploty ** 2 + right_fit[1] * ploty + right_fit[2]

    out_img[nonzeroy[left_lane_inds], nonzerox[left_lane_inds]] = [255, 0, 0]
    out_img[nonzeroy[right_lane_inds], nonzerox[right_lane_inds]] = [0, 0, 255]

    if plot:
        plt.figure(figsize=(10, 10))
        fig = plt.figure()

        plt.imshow(out_img)
        plt.plot(left_fitx, ploty, color='yellow')
        plt.plot(right_fitx, ploty, color='yellow')
        plt.xlim(0, 1280)
        plt.ylim(720, 0)

    return img


#
#
# def fit_continuous(left_fit, right_fit, binary_warped, plot=True):
#     # Assume you now have a new warped binary image
#     # from the next frame of video (also called "binary_warped")
#     # It's now much easier to find line pixels!
#     nonzero = binary_warped.nonzero()
#     nonzeroy = np.array(nonzero[0])
#     nonzerox = np.array(nonzero[1])
#     margin = 50
#     left_lane_inds = ((nonzerox > (left_fit[0] * (nonzeroy ** 2) + left_fit[1] * nonzeroy + left_fit[2] - margin))
#                       & (nonzerox < (left_fit[0] * (nonzeroy ** 2) + left_fit[1] * nonzeroy + left_fit[2] + margin)))
#     right_lane_inds = ((nonzerox > (right_fit[0] * (nonzeroy ** 2) + right_fit[1] * nonzeroy + right_fit[2] - margin))
#                        & (nonzerox < (
#                         right_fit[0] * (nonzeroy ** 2) + right_fit[1] * nonzeroy + right_fit[2] + margin)))
#
#     # Again, extract left and right line pixel positions
#     leftx = nonzerox[left_lane_inds]
#     lefty = nonzeroy[left_lane_inds]
#     rightx = nonzerox[right_lane_inds]
#     righty = nonzeroy[right_lane_inds]
#     # Fit a second order polynomial to each
#     if len(leftx) == 0:
#         left_fit_new = []
#     else:
#         left_fit_new = np.polyfit(lefty, leftx, 2)
#
#     if len(rightx) == 0:
#         right_fit_new = []
#     else:
#         right_fit_new = np.polyfit(righty, rightx, 2)
#
#     if plot == True:
#         # Generate x and y values for plotting
#         ploty = np.linspace(0, binary_warped.shape[0] - 1, binary_warped.shape[0])
#         left_fitx = left_fit[0] * ploty ** 2 + left_fit[1] * ploty + left_fit[2]
#         right_fitx = right_fit[0] * ploty ** 2 + right_fit[1] * ploty + right_fit[2]
#
#         # Create an image to draw on and an image to show the selection window
#         out_img = np.dstack((binary_warped, binary_warped, binary_warped)) * 255
#         window_img = np.zeros_like(out_img)
#         # Color in left and right line pixels
#         out_img[nonzeroy[left_lane_inds], nonzerox[left_lane_inds]] = [255, 0, 0]
#         out_img[nonzeroy[right_lane_inds], nonzerox[right_lane_inds]] = [0, 0, 255]
#
#         # Generate a polygon to illustrate the search window area
#         # And recast the x and y points into usable format for cv2.fillPoly()
#         left_line_window1 = np.array([np.transpose(np.vstack([left_fitx - margin, ploty]))])
#         left_line_window2 = np.array([np.flipud(np.transpose(np.vstack([left_fitx + margin, ploty])))])
#         left_line_pts = np.hstack((left_line_window1, left_line_window2))
#         right_line_window1 = np.array([np.transpose(np.vstack([right_fitx - margin, ploty]))])
#         right_line_window2 = np.array([np.flipud(np.transpose(np.vstack([right_fitx + margin, ploty])))])
#         right_line_pts = np.hstack((right_line_window1, right_line_window2))
#
#         # Draw the lane onto the warped blank image
#         cv2.fillPoly(window_img, np.int_([left_line_pts]), (0, 255, 0))
#         cv2.fillPoly(window_img, np.int_([right_line_pts]), (0, 255, 0))
#         result = cv2.addWeighted(out_img, 1, window_img, 0.3, 0)
#
#         plt.imshow(result)
#         plt.plot(left_fitx, ploty, color='yellow')
#         plt.plot(right_fitx, ploty, color='yellow')
#         plt.xlim(0, 1280)
#         plt.ylim(720, 0)
#
#     return left_fit_new, right_fit_new
#
#
# # Calculate Curvature
# def curvature(left_fit, right_fit, binary_warped, print_data=True):
#     ploty = np.linspace(0, binary_warped.shape[0] - 1, binary_warped.shape[0])
#     # Define y-value where we want radius of curvature
#     # I'll choose the maximum y-value, corresponding to the bottom of the image
#     y_eval = np.max(ploty)
#
#     ym_per_pix = 30 / 720  # meters per pixel in y dimension
#     xm_per_pix = 3.7 / 700  # meters per pixel in x dimension
#
#     # Define left and right lanes in pixels
#     leftx = left_fit[0] * ploty ** 2 + left_fit[1] * ploty + left_fit[2]
#     rightx = right_fit[0] * ploty ** 2 + right_fit[1] * ploty + right_fit[2]
#
#     # Identify new coefficients in metres
#     left_fit_cr = np.polyfit(ploty * ym_per_pix, leftx * xm_per_pix, 2)
#     right_fit_cr = np.polyfit(ploty * ym_per_pix, rightx * xm_per_pix, 2)
#
#     # Calculate the new radii of curvature
#     left_curverad = ((1 + (2 * left_fit_cr[0] * y_eval * ym_per_pix + left_fit_cr[1]) ** 2) ** 1.5) / np.absolute(
#         2 * left_fit_cr[0])
#     right_curverad = ((1 + (2 * right_fit_cr[0] * y_eval * ym_per_pix + right_fit_cr[1]) ** 2) ** 1.5) / np.absolute(
#         2 * right_fit_cr[0])
#
#     # Calculation of center
#     # left_lane and right lane bottom in pixels
#     left_lane_bottom = (left_fit[0] * y_eval) ** 2 + left_fit[0] * y_eval + left_fit[2]
#     right_lane_bottom = (right_fit[0] * y_eval) ** 2 + right_fit[0] * y_eval + right_fit[2]
#     # Lane center as mid of left and right lane bottom
#
#     lane_center = (left_lane_bottom + right_lane_bottom) / 2.
#     center_image = 640
#     center = (lane_center - center_image) * xm_per_pix  # Convert to meters
#
#     if print_data == True:
#         # Now our radius of curvature is in meters
#         print(left_curverad, 'm', right_curverad, 'm', center, 'm')
#
#     return left_curverad, right_curverad, center
#
#
# def draw_lines(undist, warped, left_fit, right_fit, left_cur, right_cur, center, show_img=True):
#     # Create an image to draw the lines on
#     warp_zero = np.zeros_like(warped).astype(np.uint8)
#     color_warp = np.dstack((warp_zero, warp_zero, warp_zero))
#
#     ploty = np.linspace(0, warped.shape[0] - 1, warped.shape[0])
#     # Fit new polynomials to x,y in world space
#     left_fitx = left_fit[0] * ploty ** 2 + left_fit[1] * ploty + left_fit[2]
#     right_fitx = right_fit[0] * ploty ** 2 + right_fit[1] * ploty + right_fit[2]
#
#     # Recast the x and y points into usable format for cv2.fillPoly()
#     pts_left = np.array([np.transpose(np.vstack([left_fitx, ploty]))])
#     pts_right = np.array([np.flipud(np.transpose(np.vstack([right_fitx, ploty])))])
#     pts = np.hstack((pts_left, pts_right))
#
#     # Draw the lane onto the warped blank image
#     cv2.fillPoly(color_warp, np.int_([pts]), (0, 255, 0))
#
#     # Warp the blank back to original image space using inverse perspective matrix (Minv)
#     newwarp = cv2.warpPerspective(color_warp, Minv, (color_warp.shape[1], color_warp.shape[0]))
#     # Combine the result with the original image
#     result = cv2.addWeighted(undist, 1, newwarp, 0.3, 0)
#     add_text_to_image(result, left_cur, right_cur, center)
#     if show_img == True:
#         plt.figure(figsize=(10, 10))
#         fig = plt.figure()
#         plt.imshow(result)
#
#     return result
#
#
# def sanity_check(left_fit, right_fit):
#     # Performs a sanity check on the lanes
#
#     # 1. Check if left and right fit returned a value
#     if len(left_fit) == 0 or len(right_fit) == 0:
#         status = False
#
#     else:
#         # Check distance b/w lines
#         ploty = np.linspace(0, 20, num=10)
#         left_fitx = left_fit[0] * ploty ** 2 + left_fit[1] * ploty + left_fit[2]
#         right_fitx = right_fit[0] * ploty ** 2 + right_fit[1] * ploty + right_fit[2]
#         delta_lines = np.mean(right_fitx - left_fitx)
#         if delta_lines >= 150 and delta_lines <= 430:  # apprrox delta in pixels
#             status = True
#         else:
#             status = False
#
#         # Calculate slope of left and right lanes at midpoint of y (i.e. 360)
#         L_0 = 2 * left_fit[0] * 360 + left_fit[1]
#         R_0 = 2 * right_fit[0] * 360 + right_fit[1]
#         delta_slope_mid = np.abs(L_0 - R_0)
#
#         # Calculate slope of left and right lanes at top of y (i.e. 720)
#         L_1 = 2 * left_fit[0] * 720 + left_fit[1]
#         R_1 = 2 * right_fit[0] * 720 + right_fit[1]
#         delta_slope_top = np.abs(L_1 - R_1)
#
#         # Check if lines are parallel at the middle
#
#         if delta_slope_mid <= 0.1:
#             status = True
#         else:
#             status = False
#
#     return status
