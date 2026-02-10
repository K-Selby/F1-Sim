# app.py
from API.imports import *
from screens.welcome import Title

# ----------------------------
# Config
# ----------------------------
# Initialise pygame
pygame.init()

screen_x, screen_y = pygame.display.set_mode().get_size()
screen_x, screen_y = screen_x/1.5, screen_y/1.5

# Create icon
pygame_icon = pygame.image.load('data/UI/Image_Logo.png')
pygame.display.set_icon(pygame_icon)

# ----------------------------
# Main app loop
# ----------------------------

def main(s_Mode):
   # Sets up the window
    screen = pygame.display.set_mode((screen_x, screen_y), pygame.RESIZABLE)
    pygame.display.set_caption('F1 Strategy Simulator')
    
    # Main loop
    while True:
        # Title screen
        Title_Screen = Title(s_Mode, screen)
        while s_Mode == 'Title':
            s_Mode = Title_Screen.update()

        if s_Mode == 'Quit':
            print('Quit')
            pygame.quit()
            sys.exit()

if __name__ == "__main__":
    # Loop variable
    s_Mode = 'Title'
    main(s_Mode)