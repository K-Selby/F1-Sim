# app.py

from src.UI.API.imports import *
from src.UI.screens.welcome import Title
from src.UI.screens.home import Home
from src.UI.screens.customRace import CustomeRace
from src.UI.screens.simulation import Simulation


# ===== PYGAME SETUP =====
pygame.init()

screen_x, screen_y = pygame.display.set_mode().get_size()
screen = pygame.display.set_mode((screen_x, screen_y), pygame.RESIZABLE)
pygame.display.set_caption("F1 Strategy Simulator")

# ===== WINDOW ICON =====
pygame_icon = pygame.image.load("data/UI/Images/Icon_Logo.png")
pygame.display.set_icon(pygame_icon)

# ===== MAIN APP LOOP =====
def main(s_Mode, screen, filepath):
    while True:
        # ===== TITLE SCREEN =====
        title_screen = Title(s_Mode, screen)
        while s_Mode == "Title":
            s_Mode, screen = title_screen.update()

        # ===== HOME SCREEN =====
        home_screen = Home(s_Mode, screen)
        while s_Mode == "Home":
            s_Mode, screen = home_screen.update()

        # ===== CUSTOM RACE SCREEN =====
        custom_race_screen = CustomeRace(s_Mode, screen)
        while s_Mode == "CustomRace":
            s_Mode, screen, filepath = custom_race_screen.update()

        # ===== SIMULATION SCREEN =====
        if s_Mode == "Simulation" and filepath != "":
            simulation_screen = Simulation(s_Mode, screen, filepath)

            while s_Mode == "Simulation":
                s_Mode, screen = simulation_screen.update()

        # ===== QUIT APP =====
        if s_Mode == "Quit":
            pygame.quit()
            sys.exit()


if __name__ == "__main__":
    # ===== STARTUP STATE =====
    s_Mode = "Title"
    filepath = ""

    main(s_Mode, screen, filepath)