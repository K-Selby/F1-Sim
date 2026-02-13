import pygame
import sys
import json
from threading import Timer

# Frames per second setting
FPS = 120
fpsClock = pygame.time.Clock()

# Sets up the colors
white = (255, 255, 255)
black = (0, 0, 0)
red = (255, 0, 0)
grey = (160, 160, 160)
grey_2 = (60, 60, 60)
background_colour = (10, 10, 15)
text_colour_red = (206, 46, 30)
box_colour = (18, 22, 30)
box_hover = (28, 34, 45)
red_box = (200, 40, 40)
box_colour_2 = (20, 20, 20)
box_hover_2 = (40, 40, 40)
blue = (40, 90, 200)   # Blue
green = (40, 170, 90)    # Green
purple = (128, 0, 128)
yellow = (255, 255, 0)

font_name = "data/UI/F1_Fonts/Formula1/Formula1-Bold.ttf"