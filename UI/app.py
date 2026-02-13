# app.py
from API.imports import *
from screens.welcome import Title
from screens.home import Home
from screens.customRace import CustomeRace
from screens.simulation import Siumulation

# Initialise pygame
pygame.init()

screen_x, screen_y = pygame.display.set_mode().get_size()
print(screen_x, screen_y)

screen = pygame.display.set_mode((screen_x, screen_y), pygame.RESIZABLE)
pygame.display.set_caption('F1 Strategy Simulator')

# Create icon
pygame_icon = pygame.image.load('data/UI/Images/Icon_Logo.png')
pygame.display.set_icon(pygame_icon)

# Main app loop
def main(s_Mode, screen):
    # Main loop
    while True:
        # Title screen
        Title_Screen = Title(s_Mode, screen)
        while s_Mode == 'Title':
            s_Mode, screen = Title_Screen.update()
            
        # Menu screen
        Home_Screen = Home(s_Mode, screen)
        while s_Mode == 'Home':
            s_Mode, screen = Home_Screen.update()
            
        # Custom Race screen
        Custom_Race_Screen = CustomeRace(s_Mode, screen)
        while s_Mode == 'CustomRace':
            s_Mode, screen = Custom_Race_Screen.update()
            
        Siumulation_Screen = Siumulation(s_Mode, screen)
        while s_Mode == 'Simulation':
            s_Mode, screen = Siumulation_Screen.update()
        
        if s_Mode == 'Quit':
            print('Quit')
            pygame.quit()
            sys.exit()
            
if __name__ == "__main__":
    # Loop variable
    s_Mode = 'CustomRace'
    main(s_Mode, screen)
