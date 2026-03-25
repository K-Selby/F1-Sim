# screens/home.py

from API.imports import *

class Home:
    def __init__(self, s_Mode, screen):
        self.s_Mode = s_Mode
        self.screen = screen
        self.screen_x, self.screen_y = screen.get_size()
        self.logo_text = "Formula 1"
        self.home_title_text = "F1 Simulations"
        self.home_subtitle_text = "Choose Your Race Simulator"
        self.logo_image = pygame.image.load("data/UI/Images/F1_Logo.png")
        self.race_image = pygame.image.load("data/UI/Images/race.png")
        self.replay_image = pygame.image.load("data/UI/Images/replay_circle.png")
        self.seed_image = pygame.image.load("data/UI/Images/globe_circle.png")
        self.cards = []
        self.create_cards()
        self.dots = []
        self.dot_spacing = 40
        self.influence_radius = 150
        self.create_dots()

    # Create 3 option cards
    def create_cards(self):
        self.cards.clear()

        card_width = self.screen_x / 4
        card_height = self.screen_y / 4
        spacing = self.screen_x / 45
        total_width = (card_width * 3) + (spacing * 2)
        start_x = (self.screen_x - total_width) / 2
        y = self.screen_y / 3

        titles = [
            "New Race Simulator",
            "Race Replays",
            "Seeded Simulation"
        ]

        descriptions = [
            "Fully dynamic race with fresh randomness.",
            "Replay historical races with real data.",
            "Run deterministic seeded simulations."
        ]

        modes = [
            "CustomRace",
            "RaceReplays",
            "SeededRaces"
        ]

        colours = [red, blue, purple]

        for i in range(3):
            base_rect = pygame.Rect(start_x + i * (card_width + spacing), y, card_width, card_height    )

            self.cards.append({
                "base_rect": base_rect,
                "rect": base_rect.copy(),
                "title": titles[i],
                "desc": descriptions[i],
                "mode": modes[i],
                "hover": False,
                "colour": box_colour,
                "hover_colour": colours[i],
                "scale": 1.0
            })

    def create_dots(self):
        self.dots.clear()

        for x in range(0, int(self.screen_x), self.dot_spacing):
            for y in range(0, int(self.screen_y), self.dot_spacing):
                self.dots.append({
                    "pos": (x, y),
                    "radius": 3
                })
             
    def update_dots(self):
        mouse_x, mouse_y = pygame.mouse.get_pos()

        for dot in self.dots:
            dot_x, dot_y = dot["pos"]
            dx = dot_x - mouse_x
            dy = dot_y - mouse_y
            distance = (dx**2 + dy**2) ** 0.5

            if distance < self.influence_radius:
                intensity = 1 - (distance / self.influence_radius)
                r = int(grey_2[0] + (red[0] - grey_2[0]) * intensity)
                g = int(grey_2[1] + (red[1] - grey_2[1]) * intensity)
                b = int(grey_2[2] + (red[2] - grey_2[2]) * intensity)
                color = (r, g, b)

                radius = 3 + (6 * intensity)
            else:
                color = grey_2
                radius = 3
            
            pygame.draw.circle(self.screen, color, (dot_x, dot_y), int(radius))

    # Render Home Screen
    def render(self):
        self.screen.fill(background_colour)
        
        self.update_dots()

        # Top-left Logo
        logo_font = pygame.font.Font(font_name, int(self.screen_y/22.14))
        logo_text = logo_font.render(self.logo_text, True, white)
        
        logo_image = pygame.transform.scale(self.logo_image, (self.screen_x/8.90625, self.screen_y/23.0625))
        self.screen.blit(logo_image, (self.screen_x/171, self.screen_y/110.7))
        self.screen.blit(logo_text, (self.screen_x/7.72, self.screen_y/110.7))

        # Section Title (centered)
        home_title_font = pygame.font.Font(font_name, int(self.screen_y/11.07))
        home_title = home_title_font.render(self.home_title_text, True, red)
        
        home_subtitle_font = pygame.font.Font(font_name, int(self.screen_y/36.9))
        home_subtitle = home_subtitle_font.render(self.home_subtitle_text, True, grey)
        
        title_rect = home_title.get_rect(center=(self.screen_x/2, self.screen_y/5.535))
        sub_rect = home_subtitle.get_rect(center=(self.screen_x/2, self.screen_y/4.1))

        self.screen.blit(home_title, title_rect)
        self.screen.blit(home_subtitle, sub_rect)

        # Draw Cards
        card_title_font = pygame.font.Font(font_name, int(self.screen_y/39.5357142857))
        card_text_font = pygame.font.Font(font_name, int(self.screen_y/73.8))
        race_image = pygame.transform.scale(self.race_image, (self.screen_x/28.5, self.screen_y/18.45))
        replay_image = pygame.transform.scale(self.replay_image, (self.screen_x/28.5, self.screen_y/18.45))
        seed_image = pygame.transform.scale(self.seed_image, (self.screen_x/28.5, self.screen_y/18.45))
        
        for card in self.cards:
            # Create transparent surface
            card_surface = pygame.Surface((card["rect"].width, card["rect"].height),pygame.SRCALPHA)

            # Semi transparent base
            if not card["hover"]:
                r, g, b = card["colour"]
                alpha = 200
                
            else:
                r, g, b = card["hover_colour"]
                alpha = 150

            # Draw rounded rect
            pygame.draw.rect(card_surface, (r, g, b, alpha), card_surface.get_rect(), border_radius=18)

            # Blit to screen
            self.screen.blit(card_surface, card["rect"].topleft)

            # --- TEXT ---
            title_surface = card_title_font.render(card["title"], True, white)
            desc_surface = card_text_font.render(card["desc"], True, (210, 210, 210))

            title_rect = title_surface.get_rect(topleft=(card["rect"].left + int(self.screen_x/114), card["rect"].top + int(self.screen_y/12.3)))
            desc_rect = desc_surface.get_rect(topleft=(card["rect"].left+ int(self.screen_x/114), card["rect"].top + int(self.screen_y/8.5153846154)))

            self.screen.blit(title_surface, title_rect)
            self.screen.blit(desc_surface, desc_rect)

        self.screen.blit(race_image, (self.screen_x/8.9763779528, self.screen_y/2.9))
        self.screen.blit(replay_image, (self.screen_x/2.6057142857, self.screen_y/2.9))
        self.screen.blit(seed_image, (self.screen_x/1.5244038333, self.screen_y/2.9))
        
    # Update Loop
    def update(self):
        mouse_pos = pygame.mouse.get_pos()
        
        # Recalculate card layout when resizing
        new_w, new_h = self.screen.get_size()
        if new_w != self.screen_x or new_h != self.screen_y:
            self.screen_x, self.screen_y = new_w, new_h
            self.create_cards()

        # Smooth scaling
        for card in self.cards:
            card["hover"] = card["rect"].collidepoint(mouse_pos)
            
            if card["hover"]:
                target_scale = 1.1
            else:
                target_scale = 1.0

            # Smooth interpolation
            card["scale"] += (target_scale - card["scale"]) * 0.1
            
            # Apply scale
            base = card["base_rect"]
            new_width = base.width * card["scale"]
            new_height = base.height * card["scale"]

            card["rect"] = pygame.Rect(
                base.centerx - new_width / 2,
                base.centery - new_height / 2,
                new_width,
                new_height
            )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.s_Mode = "Quit"

            if event.type == pygame.MOUSEBUTTONDOWN:
                for card in self.cards:
                    if card["rect"].collidepoint(mouse_pos):
                        self.s_Mode = card["mode"]
        
        self.render()
        pygame.display.flip()
        fpsClock.tick(FPS)

        return self.s_Mode, self.screen