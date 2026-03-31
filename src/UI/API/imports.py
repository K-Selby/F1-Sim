import pygame
import sys
import json
import random
import os
import math
from datetime import datetime
from threading import Timer

# Frames per second setting
FPS = 120
fpsClock = pygame.time.Clock()

# Sets up the colors
white = (255, 255, 255)
black = (0, 0, 0)
red = (255, 0, 0)
red_2 = (139, 60, 60)
red_3 = (185, 0, 0)
grey = (160, 160, 160)
grey_2 = (60, 60, 60)
background_colour = (10, 10, 15)
text_colour_red = (206, 46, 30)
box_colour = (18, 22, 30)
box_hover = (28, 34, 45)
red_box = (200, 40, 40)
box_colour_2 = (20, 20, 20)
box_hover_2 = (40, 40, 40)
box_colour_3 = (30, 30, 30)
blue = (40, 90, 200)   # Blue
green = (40, 170, 90)    # Green
purple = (128, 0, 128)
yellow = (255, 255, 0)
team_colours = {
    "Red Bull Racing": (30, 65, 255),
    "Ferrari": (220, 0, 0),
    "Mercedes": (0, 210, 190),
    "McLaren": (255, 135, 0),
    "Aston Martin": (0, 110, 70),
    "Alpine": (255, 105, 180),
    "Williams": (0, 90, 255),
    "RB": (70, 90, 255),
    "Kick Sauber": (0, 180, 70),
    "Haas F1 Team": (180, 180, 180),
}

font_name = "data/UI/F1_Fonts/Formula1/Formula1-Bold.ttf"