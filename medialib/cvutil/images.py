try:
    import cv2
    import numpy as np
except:
    cv2 = None
import os
from . import contours

face_cascade = None
eye_cascade = None

def loadFaceDetection():
    global face_cascade, eye_cascade
    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier('haarcascade_eye.xml')

class CVImage(object):
    def __init__(self, path=None, image=None):
        self.path = path
        self.image = image
        self.last_image = None
        self.gray_img = None
        self._kernel = None
        if image is None and path:
            if not os.path.exists(path):
                raise Exception("file does not exist: {}".format(path))
            self.image = cv2.imread(self.path)
            self._org_img = self.image
        self.contours = None

    @property
    def is_grayscale(self):
        return len(self.image.shape) == 2

    @property
    def width(self):
        h, w = self.image.shape[:2]
        return w

    @property
    def height(self):
        h, w = self.image.shape[:2]
        return h 

    def reset(self):
        self.setImage(self._org_img)
        return self

    def setImage(self, image):
        self.gray_img = None
        self.last_image = self.image
        self.image = image
        return self

    def grayscale(self, preserve_orig=False):
        if self.gray_img != None:
            return self
        if self.is_grayscale:
            self.gray_img = self.image
            return self
        gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        if not preserve_orig:
            self.setImage(gray)
        self.gray_img = gray
        return self

    def bw(self, threshold=127, threshold_convert=255):
        return self.blackAndWhite()

    def blackAndWhite(self, threshold=127, threshold_convert=255):
        self.grayscale(True)
        thresh, bw_img = cv2.threshold(self.gray_img, threshold, threshold_convert, cv2.THRESH_BINARY)
        self.setImage(bw_img)
        return self

    def isBlurry(self, threshold=100.0):
        self.grayscale(True)
        fm = cv2.Laplacian(self.gray_img, cv2.CV_64F).var()
        if fm < threshold:
            return True
        return False

    def toB64(self, frame):
        return str(base64.b64encode(frame), encoding="utf-8")

    def copy(self):
        return CVImage(image=self.image)

    def save(self, path=None, ext="png"):
        if path is None:
            path = self.path
        filename, cext = os.path.splitext(path)
        if cext.lower() != ext:
            opath = path
            path = "{}.{}".format(path, ext)
            cv2.imwrite(path, self.image)
            os.rename(path, opath)
        else:
            cv2.imwrite(path, self.image)

    def drawBoxes(self, boxes, color=(255, 0, 0), thickness=2):
        if isinstance(boxes[0][0], tuple):
            for xy1, xy2 in boxes:
                cv2.rectangle(self.image, xy1, xy2, color, thickness)
        else:
            for x, y, w, h in boxes:
                x2 = x + w
                y2 = y + h
                cv2.rectangle(self.image, (x, y), (x2, y2), color, thickness)
        return self

    def drawContours(self, contours=None, index=-1, color=(255, 0, 0), thickness=2):
        if contours is None:
            if self.contours is None:
                contours = self.findContours()
            else:
                contours = self.contours
        for i in range(0, len(contours)):
            cv2.drawContours(self.image, contours, i, color, thickness)
        return self

    def findContours(self, method=0):
        if not self.is_grayscale:
            return self.findContoursAdv()
        cnts = cv2.findContours(self.image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.contours =  contours.grab_contours(cnts)
        return self.contours

    def findContoursAdv(self):
        self.grayscale(True)
        blurred = cv2.GaussianBlur(self.gray_img, (5, 5), 0)
        ret, thresh = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY)
        cnts = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        self.contours =  contours.grab_contours(cnts)
        return self.contours

    def detectBox(self):
        self.grayscale(True)
        edges = cv2.Canny(self.gray_img, 75, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 30, maxLineGap=250)
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(self.image, (x1, y1), (x2, y2), (0, 0, 0), 5)
        return self

    def crop(self, x, y, w, h, scale_width=1.0, scale_height=1.0):
        height, width, channels = self.image.shape
        scaled_w = int(w * scale_width)
        scaled_h = int(h * scale_height)
        scaled_x = max(0, int(x - (scaled_w - w) / 2))
        scaled_y = max(0, int(y - (scaled_h - h) / 2))
        scaled_x = min(scaled_x, width)
        scaled_y = min(scaled_y, height)
        # this could go past the height of the image!!
        crop_x = scaled_x + scaled_w
        crop_y = scaled_y + scaled_h
        self.setImage(self.image[scaled_y:crop_y, scaled_x:crop_x])
        return self

    def resize(self, factor=0, width=None, height=None, inter=3):
        dim = None
        (h, w) = self.image.shape[:2]
        if factor == 0 and width is None and height is None:
            return self

        if factor:
            nh = h * factor
            nw = w * factor
            dim = (nw, nh)
        else:
            # check to see if the width is None
            if width is None:
                r = height / float(h)
                dim = (int(w * r), height)
            else:
                r = width / float(w)
                dim = (width, int(h * r))
        self.last_image = self.image
        self.setImage(cv2.resize(self.image, dim, interpolation=inter))
        return self

    def translate(self, x, y):
        # define the translation matrix and perform the translation
        M = np.float32([[1, 0, x], [0, 1, y]])
        shifted = cv2.warpAffine(self.image, M, (self.image.shape[1], self.image.shape[0]))
        self.setImage(shifted)
        # return the translated image
        return self

    def rotate(self, angle, center=None, scale=1.0):
        (h, w) = self.image.shape[:2]
        if center is None:
            center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, scale)
        rotated = cv2.warpAffine(self.image, M, (w, h))
        self.setImage(rotated)
        return self

    def rotateBound(self, angle):
        (h, w) = self.image.shape[:2]
        (cX, cY) = (w / 2, h / 2)
        M = cv2.getRotationMatrix2D((cX, cY), -angle, 1.0)
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        nW = int((h * sin) + (w * cos))
        nH = int((h * cos) + (w * sin))
        M[0, 2] += (nW / 2) - cX
        M[1, 2] += (nH / 2) - cY
        self.setImage(cv2.warpAffine(self.image, M, (nW, nH)))
        return self

    def autoCanny(self, sigma=0.33):
        # compute the median of the single channel pixel intensities
        v = np.median(self.image)
        # apply automatic Canny edge detection using the computed median
        lower = int(max(0, (1.0 - sigma) * v))
        upper = int(min(255, (1.0 + sigma) * v))
        edged = cv2.Canny(self.image, lower, upper)
        self.setImage(edged)
        return self

    def adjustGamma(self, gamma=1.0):
        # build a lookup table mapping the pixel values [0, 255] to
        # their adjusted gamma values
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        # apply gamma correction using the lookup table
        self.setImage(cv2.LUT(self.image, table))
        return self

    @property
    def kernel(self):
        if self._kernel is None:
            self.setKernel()
        return self._kernel
    
    def setKernel(self, size=(5,5)):
        self._kernel = np.ones(size,np.uint8)
        return self

    def erode(self, iterations=1):
        self.setImage(cv2.erode(self.image,self.kernel,iterations))
        return self

    def dilate(self, iterations=1):
        self.setImage(cv2.dilate(self.image,self.kernel,iterations))
        return self

    def opening(self):
        self.setImage(cv2.morphologyEx(self.image,cv2.MORPH_OPEN, self.kernel))
        return self

    def closing(self):
        self.setImage(cv2.morphologyEx(self.image,cv2.MORPH_CLOSE, self.kernel))
        return self

    def laplacian(self):
        self.setImage(cv2.Laplacian(self.image,cv2.CV_64F))
        return self

    def invert(self):
        self.setImage(cv2.bitwise_not(self.image))
        return self

    def brightness(self, level=0):
        return self.adjust(level)

    def contrast(self, level=0):
        return self.adjust(0, level)

    def blur(self, size=(5,5)):
        self.setImage(cv2.blur(self.image,size))
        return self

    def gaussianBlur(self, size=(5,5), sigma_x=0, sigma_y=0):
        self.setImage(cv2.GaussianBlur(self.image,size, sigma_x, sigma_y))
        return self

    def medianBlur(self, ksize=5):
        self.setImage(cv2.medianBlur(self.image,ksize))
        return self

    def bilateralFilter(self, diameter=9, sigma_color=75, sigma_space=75):
        self.setImage(cv2.bilateralFilter(self.image,diameter,sigma_color,sigma_space))
        return self

    def adaptiveThreshold(self, max_value=255, method=1, threshold_type=0, size=11, k=2):
        self.setImage(cv2.adaptiveThreshold(self.image,max_value,method, threshold_type,size,k))
        return self

    def autoBalance(self, clip_limit=2.0, tile_grid_size=(8,8)):
        # create a CLAHE object (Arguments are optional).
        # clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        # self.setImage(clahe.apply(self.image))
        self.grayscale()
        self.setImage(cv2.equalizeHist(self.gray_img))
        return self
    
    def adjust(self, brightness=0.0, contrast=0.0):
        """
        Adjust the brightness and/or contrast of an image
        :param image: OpenCV BGR image
        :param contrast: Float, contrast adjustment with 0 meaning no change
        :param brightness: Float, brightness adjustment with 0 meaning no change
        """
        beta = 0
        # See the OpenCV docs for more info on the `beta` parameter to addWeighted
        # https://docs.opencv.org/3.4.2/d2/de8/group__core__array.html#gafafb2513349db3bcff51f54ee5592a19
        self.setImage(cv2.addWeighted(self.image,
                               1 + float(contrast) / 100.,
                               self.image,
                               beta,
                               float(brightness)))
        return self

    def cropAndRotate(self, rect, box, crop_width_scale=1.2, crop_height_scale=1.2):
        width = rect[1][0]
        height = rect[1][1]
        angle = rect[2]
        rotated = False

        Xs = [i[0] for i in box]
        Ys = [i[1] for i in box]
        x1 = min(Xs)
        x2 = max(Xs)
        y1 = min(Ys)
        y2 = max(Ys)

        if angle < -45:
            angle += 90
            rotated = True

        center = (int((x1 + x2) / 2), int((y1 + y2) / 2))
        size = (int(crop_width_scale * (x2 - x1)), int(crop_height_scale * (y2 - y1)))

        M = cv2.getRotationMatrix2D((size[0] / 2, size[1] / 2), angle, 1.0)

        cropped = cv2.getRectSubPix(self.image, size, center)
        cropped = cv2.warpAffine(cropped, M, size)

        cropped_width = width if not rotated else height
        cropped_height = height if not rotated else width

        cropped_rotated = cv2.getRectSubPix(
            cropped,
            (int(cropped_width * crop_width_scale), int(cropped_height * crop_height_scale)),
            (size[0] / 2, size[1] / 2),
        )
        self.setImage(cropped_rotated)
        return self

    def findLargestFace(self, faces=None):
        max_area = 0
        big_face = None
        for (x, y, w, h) in faces:
            new_area = w * h
            if new_area > max_area:
                big_face = (x, y, w, h)
        return big_face

    def detectEyes(self, face):
        (x,y,w,h) = face
        roi_gray = self.gray_img[y:y+h, x:x+w]
        eyes = eye_cascade.detectMultiScale(roi_gray)
        return eyes

    def detectFaces(self, scale_factor=1.2, min_neighbors=10):
        self.grayscale(True) 
        if face_cascade is None:
            loadFaceDetection()
        faces = face_cascade.detectMultiScale(self.gray_img, scale_factor, min_neighbors)
        self.faces = faces
        return faces
