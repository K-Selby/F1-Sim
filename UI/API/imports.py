import pygame
import sys
from screens.menu import MenuScreen
from threading import Timer

# Frames per second setting
FPS = 60
fpsClock = pygame.time.Clock()

# Sets up the colors
white = (255, 255, 255)
black = (0, 0, 0)
red = (255, 0, 0)
grey = (0, 0, 0)
text_colour = (204, 172, 69)