import pygame
import sys
from threading import Timer

# Frames per second setting
FPS = 60
fpsClock = pygame.time.Clock()

# Sets up the colors
white = (255, 255, 255)
black = (0, 0, 0)
red = (255, 0, 0)
grey = (160, 160, 160)
dot_colour = (60, 60, 60)
background_colour = (10, 10, 15)
text_colour_red = (206, 46, 30)
box_colour = (18, 22, 30)
box_hover = (28, 34, 45)
red_box = (200, 40, 40)
blue = (40, 90, 200)   # Blue
green = (40, 170, 90)    # Green

font_name = "data/UI/F1_Fonts/Formula1/Formula1-Bold.ttf"