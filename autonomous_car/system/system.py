from constants.constants import FUZZY_CONTROLLER, PROPORCIONAL_CONTROLLER, DETECT_YELLOW, DETECT_BLACK
from image_processing.image_processing import *
from controller.fuzzy_controller import FuzzyController


class System:
    def __init__(self, controller, color_street):
        self._controller = controller
        self._color = color_street

    def output(self, video):
        video_processed, center, curv = self.video_processing(video)
        speed, angle = self.control(center, curv)
        return video_processed, speed, angle

    # define range of color in HSV
    def detect_street_by_color(self, video):
        if self._color == DETECT_YELLOW:
            lower_color, upper_color = np.array([20, 0, 100]), np.array([30, 255, 255])
            # lower_color, upper_color = np.array([20, 100, 100]), np.array([30, 255, 255])
        elif self._color == DETECT_BLACK:
            lower_color, upper_color = np.array([0, 0, 0]), np.array([180, 255, 35])
        else:
            raise ValueError('Color to found the street not found!')
        return detect_street(video, lower_color, upper_color)

    # Video processing
    # Return the processing video
    # Color image loaded by OpenCV is in BGR mode.
    def video_processing(self, video):
        video_street = self.detect_street_by_color(video)
        try:
            left_fit, right_fit, video_processed = fit_lines(video_street)
            # show_image(video_processed)
            left_cur, right_cur, center = curvature(left_fit, right_fit, video_processed)

            curv = (left_cur + right_cur) / 2
            add_text_to_image(video_processed, curv, center)
            video_processed = draw_lines(video, left_fit, right_fit)

        except Exception as e:
            print str(e)

        finally:
            return video_processed, 1, 1
            # return video_processed, center, curv

    # Define which controller to use
    # Return speed, angle
    def control(self, center, curv):
        if self._controller == FUZZY_CONTROLLER:
            FuzzyController.teste()

        elif self._controller == PROPORCIONAL_CONTROLLER:
            print "Controller"

        else:
            print "Controller not found"

        return 1, 2
