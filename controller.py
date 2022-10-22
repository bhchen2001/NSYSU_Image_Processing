import _thread
import numpy as np
from time import sleep
from PIL import Image, ImageQt
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QLabel
from PyQt5.QtCore import QEvent

from DIP_GUI import Ui_MainWindow
from myQLabel import imgLabel
from myPcxImage import PcxImage

def err_msgbox(error_msg, func):
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setText(func)
    msg_box.setGeometry(0, 0, 400, 300)
    msg_box.setInformativeText(error_msg)
    msg_box.setWindowTitle("Error")
    msg_box.exec_()

    return

class MainWindowController(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # setup mainwindow ui
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.setup_control()

    def setup_control(self):

        """
        Dicts for managing dynamic components
        """
        self.img_label_dict = dict()
        self.text_dict = dict()
        self.button_dict = dict()
        self.slider_dict = dict()
        self.label_dict = dict()
        self.flag_dict = dict()

        self.ori_img_label = None

        # if mod rgb processing, freeze the statusbar
        self.flag_dict["mod_rgb_flag"] = False
        """
        states of draw_flag
            0: no cut function called       <-----------------------------------
            |                                                                  |
            | click menu bar                                                   |
            v                                                                  |
            1: cut function called, waiting for starting corrdinate            |
            |                                                                  |
            | click on image label                                             |
            v                                                                  |
            2. starting coordinate confirm, waiting for ending coordinate      |
            |                                                                  |
            |_________click_on_image_again-->start cutting_____________________|
        """
        self.flag_dict["draw_flag"] = 0
        self.flag_dict["magic_wand_flag"] = 0
        self.flag_dict["ball_flag"] = 0

        """
        Action triggered connect
        """
        # basic function
        self.ui.actionOpen.triggered.connect(self.open_file)
        self.ui.actionReset.triggered.connect(self.reset)

        # func_week1
        self.ui.actionSimple_Dup.triggered.connect(lambda: self.enlarge_img("simple_dup", slider = False))
        self.ui.actionBi_Linear.triggered.connect(lambda: self.enlarge_img("bi_linear", slider = False))
        self.ui.actionNormal_Rotate.triggered.connect(lambda: self.rotate_img("normal", slider = False))
        self.ui.actionReverse_Rotate.triggered.connect(lambda: self.rotate_img("reverse", slider = False))
        self.ui.actionShear.triggered.connect(lambda: self.shear(slider = False))
        self.ui.actionRect_Cut.triggered.connect(lambda: self.cut_img("rect", draw = False))
        self.ui.actionCircle_Cut.triggered.connect(lambda: self.cut_img("circle", draw = False))
        self.ui.actionMagic_Wand.triggered.connect(lambda: self.magic_wand(select = False))
        self.ui.actionAplha.triggered.connect(lambda: self.alpha(slider = False))
        self.ui.actionBall.triggered.connect(lambda: self.ball(button = False)) 

    def display(self, label, image_array, width, height, posx, posy):

        """
        Display image on the qt label
            posx, posy: -1 for default position (defined in DIP_GUI)
        """
        # try:
        # print("size of image_array: {0}".format(image_array.shape))
        img = np.array(image_array, dtype=np.uint8)
        img = Image.fromarray(img)
        qt_img = ImageQt.ImageQt(img)
        pixmap_img = QtGui.QPixmap.fromImage(qt_img).scaled(width, height)
        pixmap_img.detach()

        if posx == -1 or posy == -1:
            label.resize(width, height)
        else:
            label.setGeometry(QtCore.QRect(posx, posy, width, height))
        label.setPixmap(pixmap_img)
        label.show()
        # except:
        #     err_msgbox("cannot diaplay the image on label", self.display.__name__)
        #     return -1
        return

    def enable_menu(self):

        """
        Enable the function in menu content
        """
        self.ui.menuEnlarge.setEnabled(True)
        self.ui.menuRotate.setEnabled(True)
        self.ui.actionShear.setEnabled(True)
        self.ui.menuCut.setEnabled(True)
        self.ui.actionMagic_Wand.setEnabled(True)
        self.ui.actionAplha.setEnabled(True)

    def show_header(self):

        """
        Show the information in header, including the color palette by little image
        """
        # header content
        output = "Header INFO:\n"
        for item, value in self.ori_pcx.header.items():
            if item == "colormap" or item == "filter":
                continue
            elif item == "window":
                xmin, ymin, xmax, ymax = (int.from_bytes(value[0:2], byteorder="little"), 
                                          int.from_bytes(value[2:4], byteorder="little"),
                                          int.from_bytes(value[4:6], byteorder="little"), 
                                          int.from_bytes(value[6:8], byteorder="little"))
                tmp = "{0}: \nXmin = {1}, Ymin = {2}, \nXmax = {3}, Ymax = {4}\n".format(item, xmin, ymin, xmax, ymax)
            else:
                tmp = "{0}: {1}\n".format(item, value)
            output += tmp
        self.ui.header_label.setFont(QtGui.QFont('Times', 15))
        self.ui.header_label.setText(output)

        pal_image, width, height = self.ori_pcx.color_pal_image()
        self.display(self.ui.palette_label, pal_image, width, height, -1, -1)

        return


    def open_file(self):
        filename, filetype = QFileDialog.getOpenFileName(self, "Open File", "./ImagePCX")

        self.ori_pcx = PcxImage()
        self.ori_pcx.read_from_filename(filename)
        self.ori_pcx.decode_image()

        width, height  = self.ori_pcx.width, self.ori_pcx.height

        # initialize the label for showing original image
        self.ori_img_label = imgLabel(self)
        self.ori_img_label.setGeometry(QtCore.QRect(80, 80, 256, 256))
        self.ori_img_label.setText("")
        self.ori_img_label.setObjectName("ori_img_label")
        self.ori_img_label.installEventFilter(self)

        self.display(self.ori_img_label, self.ori_pcx.ori_image, self.ori_pcx.width, self.ori_pcx.height, -1, -1)
        self.show_header()

        self.enable_menu()

        return

    def mod_pixel_rgb(self, posx, posy):
        rgb_msg = self.text_dict["rgb_textedit"].toPlainText()

        rgb = rgb_msg.split('\n')

        mod_img, width, height = self.ori_pcx.mod_pixel(posx, posy, int(rgb[0]), int(rgb[1]), int(rgb[2]))

        # initialize the label for showing modified
        self.create_img_label(400, 80, 256, 256, "mod_img")
        self.display(self.img_label_dict["mod_img"], mod_img, width, height, -1, -1)
        self.flag_dict["mod_rgb_flag"] = False
        return

    def enlarge_img(self, type, slider = True):
        if slider == False:
            name = "enlarge_label"
            slider_num = "\n-4                                             4"
            self.create_label(160, 400, 240, 100, name, type + slider_num)

            name = "enlarge_slider"
            self.create_slider(200, 450, 160, 22, name, -4, 4, 0.5)
            self.slider_dict[name].valueChanged.connect(lambda: self.enlarge_img(type, slider = True))
            return
        times = self.slider_dict["enlarge_slider"].value()
        mod_img, width, height = self.ori_pcx.enlarge(type, times)
        self.create_img_label(400, 80, 256, 256, "mod_img")
        self.display(self.img_label_dict["mod_img"], mod_img, width, height, -1, -1)

        return

    def rotate_img(self, type, slider = True):
        if slider == False:
            name = "rotate_label"
            slider_num = "\n-180                                             180"
            self.create_label(160, 480, 240, 100, name, type + slider_num)

            name = "rotate_slider"
            self.create_slider(200, 530, 160, 22, name, -180, 180, 1)
            self.slider_dict[name].valueChanged.connect(lambda: self.rotate_img(type, slider = True))
            return
        theta = self.slider_dict["rotate_slider"].value()
        mod_img, width, height = self.ori_pcx.rotate(type, theta)
        self.create_img_label(400, 80, 256, 256, "mod_img")
        self.display(self.img_label_dict["mod_img"], mod_img, width, height, -1, -1)

        return

    def shear(self, slider = True):
        if slider == False:
            name = "shear_label"
            slider_num = "\n0                                             10"
            self.create_label(160, 560, 240, 100, name, "shear" + slider_num)

            name = "shear_slider"
            self.create_slider(200, 600, 160, 22, name, 0, 10, 0.5)
            self.slider_dict[name].valueChanged.connect(lambda: self.shear(slider = True))
            return
        slope = self.slider_dict["shear_slider"].value()
        mod_img, width, height = self.ori_pcx.shear(slope)
        self.create_img_label(400, 80, 256, 256, "mod_img")
        self.display(self.img_label_dict["mod_img"], mod_img, width, height, -1, -1)

        return

    def cut_img(self, type, draw = True):
        if draw == False:
            self.flag_dict["draw_flag"] = 1
            if type == "rect":
                self.cut_begin = None
                self.cut_end = None
                self.ori_img_label.cut_rect = True
            elif type == "circle":
                self.ori_img_label.cut_circle = True
            return
        elif draw == True:
            if type == "rect":
                mod_img, width, height = self.ori_pcx.cut(type, self.cut_begin, self.cut_end)
            elif type == "circle":
                mod_img, width, height = self.ori_pcx.cut(type, self.ori_img_label.centroid, self.ori_img_label.radius)
            self.create_img_label(400, 80, 256, 256, "mod_img")
            self.display(self.img_label_dict["mod_img"], mod_img, width, height, -1, -1)
            self.ori_img_label.reset_cut_flags()
            self.cut_begin = None
            self.cut_end = None
        
        return

    def magic_wand(self, select = False):
        if select == False:
            self.flag_dict["magic_wand_flag"] = 1
            self.wand_begin = None
            self.wand_end = None
            self.current = None
            self.magic_wand_img = np.copy(self.ori_pcx.ori_image)
            self.create_img_label(400, 80, 256, 256, "mod_img")
            self.display(self.img_label_dict["mod_img"], self.magic_wand_img, self.ori_pcx.width, self.ori_pcx.height, -1, -1)
            return
        elif select == True:
            self.magic_wand_img = self.ori_pcx.magic_wand(self.magic_wand_img, self.wand_begin, self.wand_end, self.current)
            self.display(self.img_label_dict["mod_img"], self.magic_wand_img, self.ori_pcx.width, self.ori_pcx.height, -1, -1)

        return

    def alpha(self, slider = True):
        if slider == False:
            # open another image
            filename, filetype = QFileDialog.getOpenFileName(self, "Open File", "./ImagePCX")
            alpha_pcx = PcxImage()
            alpha_pcx.read_from_filename(filename)
            alpha_pcx.decode_image()
            self.alpha_img = alpha_pcx.ori_image
            self.alpha_width, self.alpha_height  = alpha_pcx.width, alpha_pcx.height
            self.create_img_label(400, 80, 256, 256, "mod_img")
            self.display(self.img_label_dict["mod_img"], self.alpha_img, self.alpha_width, self.alpha_height, -1, -1)

            # set label and slider
            name = "alpha_label"
            slider_num = "\n0                                             1"
            self.create_label(160, 630, 240, 100, name, "alpha" + slider_num)

            name = "alpha_slider"
            self.create_slider(200, 680, 160, 22, name, 0, 10, 1)
            self.slider_dict[name].valueChanged.connect(lambda: self.alpha(slider = True))
            return
        alpha_value = self.slider_dict["alpha_slider"].value() / 10
        mod_img, width, height = self.ori_pcx.alpha(self.alpha_img, self.alpha_width, self.alpha_height, alpha_value)
        self.create_img_label(400, 80, 256, 256, "mod_img")
        self.display(self.img_label_dict["mod_img"], mod_img, width, height, -1, -1)
        return

    def ball(self, button = True):
        if button == False:
            # set button and slider
            name = "ball_btn"
            self.create_button(60, 540, 93, 28, name, "ball")
            self.button_dict[name].clicked.connect(lambda: self.ball_control())

            # show the ball image and initialize the variables
            self.flag_dict["ball_flag"] = False
            self.ball_vector = np.array([1, 0.5])
            self.ball_speed = 10
            self.ball_pcx = PcxImage()
            self.ball_img, width, height, self.ball_center, self.vector = self.ball_pcx.ball("create")
            self.create_img_label(400, 80, 256, 256, "mod_img")
            self.display(self.img_label_dict["mod_img"], self.ball_img, width, height, -1, -1)
            return

    def bouncing_ball(self):
        while self.flag_dict["ball_flag"] == True:
            self.ball_img, width, height, self.ball_center, self.vector = \
                self.ball_pcx.ball("bouncing", center = self.ball_center, vector = self.ball_vector, speed = self.ball_speed)
            self.create_img_label(400, 80, 256, 256, "mod_img")
            self.display(self.img_label_dict["mod_img"], self.ball_img, width, height, -1, -1)
            sleep(0.5)
        return

    def ball_control(self):
        if self.flag_dict["ball_flag"] == False:
            self.flag_dict["ball_flag"] = True
            self.bouncing_ball()
            # _thread.start_new_thread(self.bouncing_ball, ())
        elif self.flag_dict["ball_flag"] == True:
            self.flag_dict["ball_flag"] = False
        return

    def eventFilter(self, obj, event):
        if obj is self.ori_img_label:
            if event.type() == QEvent.MouseMove:
                if self.flag_dict["mod_rgb_flag"] == False:
                    x, y = event.pos().x(), event.pos().y()
                    r, g, b = self.ori_pcx.rgb_value_pos(x, y)
                    self.ui.statusbar.showMessage(("x = {0}, y = {1}, r ={2}, g = {3}, b = {4}".format(x, y, r, g, b)))

                # for cut image
                if self.flag_dict["draw_flag"] == 2:
                    self.ori_img_label.end = event.pos()
                    if self.ori_img_label.cut_circle == True:
                        centerx, centery = self.ori_img_label.centroid.x(), self.ori_img_label.centroid.y()
                        self.ori_img_label.radius = np.linalg.norm(np.array([event.pos().x(), event.pos().y()]) - np.array([centerx, centery]))
                    self.update()

                # for magic wand
                if self.flag_dict["magic_wand_flag"] == 4:
                    self.current = event.pos()
                    self.magic_wand(select = True)

                return True
            elif event.type() == QEvent.MouseButtonDblClick:
                if self.flag_dict["draw_flag"] == 0:
                    self.flag_dict["mod_rgb_flag"] = True
                    x, y = event.pos().x(), event.pos().y()
                    r, g, b = self.ori_pcx.rgb_value_pos(x, y)
                    self.ui.statusbar.showMessage(("x = {0}, y = {1}, r ={2}, g = {3}, b = {4}".format(x, y, r, g, b)))

                    # show the textedit box for rgb value and confirm button
                    self.create_text(60, 390, 91, 101, "rgb_textedit", "RedGreenBlue", gray=True)
                    self.create_button(60, 510, 93, 28, "rgb_ok_btn", "Ok")
                    self.button_dict["rgb_ok_btn"].clicked.connect(lambda: self.mod_pixel_rgb(x, y))

            elif event.type() == QEvent.MouseButtonPress:
                """
                For cut image
                """
                if self.flag_dict["draw_flag"] == 1:
                    self.flag_dict["draw_flag"] = 2
                    if self.ori_img_label.cut_rect == True:
                        self.ori_img_label.begin = event.pos()
                        self.ori_img_label.end = event.pos()
                        self.cut_begin = event.pos()
                    elif self.ori_img_label.cut_circle == True:
                        self.ori_img_label.centroid = event.pos()
                elif self.flag_dict["draw_flag"] == 2:
                    self.flag_dict["draw_flag"] = 0
                    if self.ori_img_label.cut_rect == True:
                        self.ori_img_label.begin = event.pos()
                        self.ori_img_label.end = event.pos()
                        self.cut_end = event.pos()
                    # cut the subimage
                    if self.ori_img_label.cut_rect == True:
                        self.cut_img("rect", draw = True)
                    elif self.ori_img_label.cut_circle == True:
                        self.cut_img("circle", draw = True)
                    # remove the rect / circle that drawing on the image
                    self.update()

                """
                For magic wand
                """
                if self.flag_dict["magic_wand_flag"] == 1:
                    self.wand_begin = event.pos()
                    self.flag_dict["magic_wand_flag"] = 2
                    print("stage 2, begin set")
                elif self.flag_dict["magic_wand_flag"] == 2:
                    self.wand_end = event.pos()
                    self.flag_dict["magic_wand_flag"] = 3
                    print("stage 3, end set")
                elif self.flag_dict["magic_wand_flag"]  == 3:
                    self.flag_dict["magic_wand_flag"] = 4
                    print("stage 4, start painting")
                elif self.flag_dict["magic_wand_flag"] == 4:
                    self.flag_dict["magic_wand_flag"] = 0
                    print("magic wand over")

                return True

        return super(MainWindowController, self).eventFilter(obj, event)

    def create_img_label(self, posx, posy, width, height, name):

        """
        Create the image label
        """
        if name in self.img_label_dict:
            self.img_label_dict[name].hide()
        label = imgLabel(self)
        label.setGeometry(QtCore.QRect(posx, posy, width, height))
        label.setText("")
        label.setObjectName(name)
        label.installEventFilter(self)

        self.img_label_dict[name] = label
        return

    def create_label(self, posx, posy, width, height, name, text):

        """
        Create the text label
        """
        if name in self.label_dict:
            self.label_dict[name].hide()
        label = imgLabel(self)
        label.setGeometry(QtCore.QRect(posx, posy, width, height))
        label.setText(text)
        label.setObjectName(name)
        label.installEventFilter(self)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setFont(QtGui.QFont('Times', 10))
        label.show()

        self.label_dict[name] = label
        return

    def create_text(self, posx, posy, width, height, name, text, gray = False):

        """
        Create the textedit
        """
        text = QtWidgets.QTextEdit(self)
        text.setGeometry(QtCore.QRect(posx, posy, width, height))
        text.setObjectName("textEdit")
        _translate = QtCore.QCoreApplication.translate
        if gray == True:
            text.setHtml(_translate("MainWindow", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
            "<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
            "p, li { white-space: pre-wrap; }\n"
            "</style></head><body style=\" font-family:\'PMingLiU\'; font-size:9pt; font-weight:400; font-style:normal;\">\n"
            "<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-size:14pt; color:#878787;\">Red<br>Green<br>Blue</span></p></body></html>"))
        text.show()

        self.text_dict[name] = text
        return

    def create_button(self, posx, posy, width, height, name, text):

        """
        Create button
        """
        btn = QtWidgets.QPushButton(self)
        btn.setGeometry(QtCore.QRect(posx, posy, width, height))
        btn.setObjectName("pushButton")
        _translate = QtCore.QCoreApplication.translate
        btn.setText(_translate("MainWindow", text))
        btn.show()

        self.button_dict[name] = btn
        return

    def create_slider(self, posx, posy, width, height, name, min, max, step):
        if name in self.slider_dict:
            self.slider_dict[name].hide()
        slider = QtWidgets.QSlider(self)
        slider.setGeometry(QtCore.QRect(posx, posy, width, height))
        slider.setOrientation(QtCore.Qt.Horizontal)
        slider.setObjectName(name)

        slider.setMinimum(min)
        slider.setMaximum(max)
        slider.setSingleStep(step)
        # slider.setPageStep(page_step)
        slider.show()

        self.slider_dict[name] = slider
        return

    def reset(self):

        """
        Remove everything but original image image, mod_image in pcx object set to None
        """
        for key, value in self.img_label_dict.items():
            value.hide()
        for key, value in self.button_dict.items():
            value.hide()
        for key, value in self.text_dict.items():
            value.hide()
        for key, value in self.label_dict.items():
            value.hide()
        for key, value in self.slider_dict.items():
            value.hide()
        for key, value in self.flag_dict.items():
            value = 0

        self.ori_pcx.mod_image = None