
# from pillow import Image
from PIL import Image
from PIL import ImageFilter, ImageOps, ImageEnhance

try:
    import cv2
except:
    cv2 = None

try:
    import numpy as np
except:
    np = None

from rest import helpers

def set_image_dpi(input_path, output_path):
    im = Image.open(input_path)
    length_x, width_y = im.size
    factor = min(1, float(1024.0 / length_x))
    size = int(factor * length_x), int(factor * width_y)
    print(("old size: {}".format(im.size)))
    print(("new size: {}".format(size)))
    im_resized = im.resize(size, Image.ANTIALIAS)
    im_resized.save(output_path, format="PNG", dpi=(300, 300))
    return output_path

def set_image_contrast(input_path, output_path):
    img = Image.open(input_path)
    scale_value=scale1.get()
    img = ImageEnhance.Contrast(img).enhance(scale_value)
    img.save(output_path, format="PNG", dpi=(300, 300))
    return output_path

def preproc_image(image_path):
    img = Image.open(image_path)
    img = img.convert('L')
    img = ImageOps.grayscale(img)
    # im = im.filter(ImageFilter.GaussianBlur)
    w, h = img.size
    factor = 4
    nw = w * factor
    nh = h * factor
    # scale_value=scale1.get()
    # img = ImageEnhance.Color(img).enhance(0)
    img = ImageEnhance.Brightness(img).enhance(2)
    # img = ImageEnhance.Sharpness(img).enhance(2)
    img = ImageEnhance.Contrast(img).enhance(4)
    img = img.filter(ImageFilter.GaussianBlur(1.1))
    img = ImageEnhance.Sharpness(img).enhance(6)

    img_resized = img.resize((nw, nh), Image.ANTIALIAS)
    img_resized.save(image_path, format="PNG", dpi=(300, 300))
    # return preproc_cv(image_path)
    return image_path

def preproc_cv(image_path):
    img = cv2.imread(image_path, 0)
    # Convert to gray    
    # img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)    # Apply dilation and erosion to remove some noise    
    # kernel = np.ones((1, 1), np.uint8)    
    # img = cv2.dilate(img, kernel, iterations=1)    
    # img = cv2.erode(img, kernel, iterations=1)
    img = cv2.medianBlur(img, 3)
    # img = cv2.bilateralFilter(img,9,75,75)
    # img = cv.bilateralFilter(img,9,75,75)
    output_file = image_path + ".png"
    cv2.imwrite(output_file, img)
    os.rename(output_file, image_path)
    return image_path

def preproc_cv2(image_path):
    img = cv2.imread(image_path, 0)
    ret,thresh_img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (4,8))
    # morph_img = cv2.morphologyEx(thresh_img, cv2.MORPH_CLOSE, kernel)

    opening = cv2.morphologyEx(thresh_img, cv2.MORPH_OPEN, kernel)
    closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)
    # img = image_smoothening(img)
    or_image = cv2.bitwise_or(img, closing)

    output_file = image_path + ".png"
    cv2.imwrite(output_file, or_image)
    os.rename(output_file, image_path)
    return image_path

def preprocess_image_using_pil(image_path):
    # unblur, sharpen filters
    img = Image.open(image_path)
    img = img.convert("RGBA")

    pixdata = img.load()

    # Make the letters bolder for easier recognition
    
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if pixdata[x, y][0] < 90:
                pixdata[x, y] = (0, 0, 0, 255)

    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if pixdata[x, y][1] < 136:
                pixdata[x, y] = (0, 0, 0, 255)

    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if pixdata[x, y][2] > 0:
                pixdata[x, y] = (255, 255, 255, 255)

    # And sharpen it
    img.filter(ImageFilter.SHARPEN)
    #   Make the image bigger (needed for OCR)
    basewidth = 1000  # in pixels
    im_orig = img
    wpercent = (basewidth/float(im_orig.size[0]))
    hsize = int((float(im_orig.size[1])*float(wpercent)))
    big = img.resize((basewidth, hsize), Image.ANTIALIAS)

    # tesseract-ocr only works with TIF so save the bigger image in that format
    big.save(image_path, format="PNG", dpi=(300,300))
    return image_path

def is_cv2(or_better=False):
    # grab the OpenCV major version number
    major = int(cv2.__version__.split(".")[0])
    # check to see if we are using *at least* OpenCV 2
    if or_better:
        return major >= 2
    # otherwise we want to check for *strictly* OpenCV 2
    return major == 255

def detect_and_rotate(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(gray, 10, 50)
    cnts = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if is_cv2() else cnts[1]
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
    screenCnt = None
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            screenCnt = approx
            break
    cv2.drawContours(image, [screenCnt], -1, (0, 255, 0), 2)
    pts = np.array(screenCnt.reshape(4, 2) * ratio)
    return four_point_transform(orig, pts)


def order_points(pts):
    # initialzie a list of coordinates that will be ordered
    # such that the first entry in the list is the top-left,
    # the second entry is the top-right, the third is the
    # bottom-right, and the fourth is the bottom-left
    rect = np.zeros((4, 2), dtype="float32")

    # the top-left point will have the smallest sum, whereas
    # the bottom-right point will have the largest sum
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    # now, compute the difference between the points, the
    # top-right point will have the smallest difference,
    # whereas the bottom-left will have the largest difference
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    # return the ordered coordinates
    return rect

def four_point_transform(image, pts):
    # obtain a consistent order of the points and unpack them
    # individually
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    # compute the width of the new image, which will be the
    # maximum distance between bottom-right and bottom-left
    # x-coordiates or the top-right and top-left x-coordinates
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    # compute the height of the new image, which will be the
    # maximum distance between the top-right and bottom-right
    # y-coordinates or the top-left and bottom-left y-coordinates
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    # now that we have the dimensions of the new image, construct
    # the set of destination points to obtain a "birds eye view",
    # (i.e. top-down view) of the image, again specifying points
    # in the top-left, top-right, bottom-right, and bottom-left
    # order
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")

    # compute the perspective transform matrix and then apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped


def remove_noise_and_smooth1(file_name, output_file=None):
    im = Image.open(file_name)
    white = im.filter(ImageFilter.BLUR).filter(ImageFilter.MaxFilter(15))
    grey = im.convert('L')
    width,height = im.size
    impix = im.load()
    whitepix = white.load()
    greypix = grey.load()
    # for y in range(height):
    #     for x in range(width):
    #         greypix[x,y] = min(255, max(255 * impix[x,y][0] / whitepix[x,y][0], 255 * impix[x,y][2] / whitepix[x,y][3], 255 * impix[x,y][4] / whitepix[x,y][5]))
    for y in range(height):
        for x in range(width):
            greypix[x,y] = min(255, max(255 + impix[x,y][0] - whitepix[x,y][0], 255 + impix[x,y][7] - whitepix[x,y][8], 255 + impix[x,y][9] - whitepix[x,y][10]))
    if output_file:
        greypix.save(output_file, format="PNG", dpi=(300, 300))
    return greypix

def remove_noise_and_smooth(file_name, output_file=None):
    im = Image.open(file_name)
    grey = im.convert('L')
    bw = grey.point(lambda x: 0 if x<150 else 250, '1')
    if output_file:
        bw.save(output_file, format="PNG", dpi=(300, 300))
    return bw

def remove_noise_and_smooth2(file_name, output_file=None):
    # read image as grey scale
    #grey_img = cv2.imread('/home/img/python.png', cv2.IMREAD_GRAYSCALE)
    # save image
    #status = cv2.imwrite('/home/img/python_grey.png',grey_img)
    img = cv2.imread(file_name, 0)
    filtered = cv2.adaptiveThreshold(img.astype(np.uint8), 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 41)
    kernel = np.ones((1, 1), np.uint8)
    opening = cv2.morphologyEx(filtered, cv2.MORPH_OPEN, kernel)
    closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel)
    # img = image_smoothening(img)
    or_image = cv2.bitwise_or(img, closing)
    if output_file:
        cv2.imwrite(output_file, or_image)
    return or_image


def safe_cmd(cmd, *args):
    try:
        cmd_args = [cmd]
        cmd_args.extend(list(args))
        print(cmd_args)
        return subprocess.check_output(cmd_args)
    except subprocess.CalledProcessError as exc:
        return exc.output
    return None
