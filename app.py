# app.py
from src.UI.API.imports import *
from src.UI.screens.welcome import Title
from src.UI.screens.home import Home
from src.UI.screens.customRace import CustomeRace
from src.UI.screens.simulation import Simulation

# Initialise pygame
pygame.init()

screen_x, screen_y = pygame.display.set_mode().get_size()

screen = pygame.display.set_mode((screen_x, screen_y), pygame.RESIZABLE)
pygame.display.set_caption('F1 Strategy Simulator')

# Create icon
pygame_icon = pygame.image.load('data/UI/Images/Icon_Logo.png')
pygame.display.set_icon(pygame_icon)

# Main app loop
def main(s_Mode, screen, filepath):
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
            
        # Custom Race screen§
        Custom_Race_Screen = CustomeRace(s_Mode, screen)
        while s_Mode == 'CustomRace':
            s_Mode, screen, filepath = Custom_Race_Screen.update()
            
        Siumulation_Screen = Simulation(s_Mode, screen, filepath)
        while s_Mode == 'Simulation':
            s_Mode, screen = Siumulation_Screen.update()
        
        if s_Mode == 'Quit':
            pygame.quit()
            sys.exit()
            
if __name__ == "__main__":
    # Loop variable
    s_Mode = 'Simulation'
    filepath = "data/RaceData/SimulationConfigs/RaceConfig-26-03-2026-12-30-18.json"
    main(s_Mode, screen, filepath)