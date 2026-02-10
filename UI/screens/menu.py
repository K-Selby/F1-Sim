# screens/menu.py
from API.imports import *

class MenuScreen:
    def __init__(self, screen):
        self.screen = screen
        self.width, self.height = screen.get_size()

        self.title_font = pygame.font.SysFont("arial", 48, bold=True)
        self.text_font = pygame.font.SysFont("arial", 28)

        self.title = self.title_font.render("F1 Strategy Simulator", True, (255, 255, 255))
        self.subtitle = self.text_font.render(
            "Press ENTER to continue",
            True,
            (180, 180, 180),
        )

        self.title_rect = self.title.get_rect(center=(self.width // 2, self.height // 2 - 40))
        self.sub_rect = self.subtitle.get_rect(center=(self.width // 2, self.height // 2 + 30))

        self.blink_timer = 0
        self.show_subtitle = True

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                print("Menu confirmed — next screen goes here")

    def update(self):
        # simple blink animation
        self.blink_timer += 1
        if self.blink_timer > 40:
            self.show_subtitle = not self.show_subtitle
            self.blink_timer = 0

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.screen.blit(self.title, self.title_rect)

        if self.show_subtitle:
            self.screen.blit(self.subtitle, self.sub_rect)