# screens/customRace.py

from API.imports import *
import json

class CustomeRace:
    def __init__(self, s_Mode, screen):
        self.s_Mode = s_Mode
        self.screen = screen
        self.screen_x, self.screen_y = screen.get_size()
        self.title_text = "Build Your Own Simulation"
        self.subtitle_text = "Select your prefered race settings and enjoy"
        self.subtitle_text_2 = "high-quality F1 Simulations"
        self.box_title_text = "Choose Your Race Settings"
        self.return_text = "Return to Home"
        self.return_image = pygame.image.load("data/UI/Images/return.png")
        self.flag_image = pygame.image.load("data/UI/Images/flag.png")
        self.settings_image = pygame.image.load("data/UI/Images/settings.png")
        self.play_image = pygame.image.load("data/UI/Images/play_circle.png")
        self.race_cards_json = "data/CircuitOptions/AllCircuits/races.json"
        self.selected_card = -1
        self.colours = [red, red, green]
        self.box_colours = [box_colour, box_colour, box_colour]
        self.cards = []
        self.button = []
        self.dots = []
        self.race_cards = []
        self.dot_spacing = 40
        self.influence_radius = 150
        self.scroll_offset = 0
        self.max_scroll = 800  # how far content can scroll
        self.create_cards()
        self.button_1()
        self.create_dots()
        self.create_race_cards()
        
    # Create 3 option cards
    def create_cards(self):
        self.cards.clear()

        card_width = self.screen_x / 4
        card_height = self.screen_y / 4
        spacing = self.screen_x / 45
        total_width = (card_width * 3) + (spacing * 2)
        start_x = (self.screen_x - total_width) / 2
        y = self.screen_y / 3 - self.scroll_offset

        titles = [
            "Track Selection",
            "Simulation Settings",
            "Begin Simulation"
        ]

        descriptions = [
            "Choose any track from the previous years and \ncreate a custom race.",
            "Customise the simulation parameters to your liking\nand create unique scenarios.",
            "Its Lights out and away we go!"
        ]

        for i in range(3):
            base_rect = pygame.Rect(start_x + i * (card_width + spacing), y, card_width, card_height)

            self.cards.append({
                "base_rect": base_rect,
                "rect": base_rect.copy(),
                "title": titles[i],
                "desc": descriptions[i],
                "hover": False,
                "colour": self.box_colours[i],
                "hover_colour": self.colours[i],
                "scale": 1.0,
                "selected": False,
                "selected_colour": self.colours[i]
            })
            
            if self.selected_card == i:
                self.cards[i]["selected"] = True
                
            else:
                self.cards[i]["selected"] = False

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

    def button_1(self):
        # return button  settings
        # Draws borders
        self.button.clear()
        card_width = self.screen_x / 3.21
        card_height =  self.screen_y / 18.45
        start_x = (self.screen_x / 57)
        y = (self.screen_y/110.7) - self.scroll_offset
        
        base_rect = pygame.Rect(start_x, y, card_width, card_height)
        
        self.button.append({
                "base_rect": base_rect,
                "rect": base_rect.copy(),
                "title": "Return to Home",
                "hover": False,
                "colour": box_colour,
                "hover_colour": purple,
                "scale": 1.0,
                "image": self.return_image,
                "mode": "Home"
            })

    def box_scaling(self, mouse_pos):
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

            card["rect"] = pygame.Rect(base.centerx - new_width / 2, base.centery - new_height / 2, new_width, new_height)
            
        for card in self.button:
            card["hover"] = card["rect"].collidepoint(mouse_pos)
            if card["hover"]:
                target_scale = 1.05
            else:
                target_scale = 1.0

            # Smooth interpolation
            card["scale"] += (target_scale - card["scale"]) * 0.1
            
            # Apply scale
            base = card["base_rect"]
            new_width = base.width * card["scale"]
            new_height = base.height * card["scale"]

            card["rect"] = pygame.Rect(base.centerx - new_width / 2, base.centery - new_height / 2, new_width, new_height)
            
        for card in self.race_cards:
            card["hover"] = card["rect"].collidepoint(mouse_pos)

    def create_race_cards(self):
        with open(self.race_cards_json, "r") as circuitFile:
            self.race_data = json.load(circuitFile)["Races"]
            
        self.race_cards.clear()

        cards_per_row = 4
        spacing_x = self.screen_x / 34.2
        spacing_y = self.screen_y / 22.14

        card_width = self.screen_x / 4.8857142857
        card_height = self.screen_y / 3.1628571429
        total_width = (card_width * cards_per_row) + (spacing_x * (cards_per_row - 1))
        start_x = (self.screen_x - total_width) / 2

        start_y = self.screen_y / 1.5814285714 - self.scroll_offset

        for index, race in enumerate(self.race_data):

            row = index // cards_per_row
            col = index % cards_per_row

            x = start_x + col * (card_width + spacing_x)
            y = start_y + row * (card_height + spacing_y)

            base_rect = pygame.Rect(x, y, card_width, card_height)

            self.race_cards.append({
                "base_rect": base_rect,
                "rect": base_rect.copy(),
                "data": race,
                "hover": False
            })

        # Update max scroll dynamically
        total_rows = (len(self.race_data) // cards_per_row) + 1
        content_height = total_rows * (card_height + spacing_y)
        self.max_scroll = max(0, content_height - (self.screen_y / 2))

    def draw_race_cards(self):
        race_title_font = pygame.font.Font(font_name, int(self.screen_y / 55))
        round_font = pygame.font.Font(font_name, int(self.screen_y / 15))
            
        for card in self.race_cards:
            race = card["data"]
            rect = card["rect"]
            
            # Create surface
            card_surface = pygame.Surface((rect.width, rect.height),pygame.SRCALPHA)
            
            # Background
            if card["hover"]:
                colour = (box_hover_2)
            else:
                colour = (box_colour_2)

            pygame.draw.rect(card_surface, colour, card_surface.get_rect(), border_radius=12)

            # Blit to screen
            self.screen.blit(card_surface, rect.topleft)

            # Grand Prix title
            lines = race['Grand_Prix'].upper().split("\n")

            for index, line in enumerate(lines):
                title_surface = race_title_font.render(line, True, yellow)
                title_rect = title_surface.get_rect(topleft=(card["rect"].left + int(self.screen_x/114), rect.top + int(self.screen_y/73.8) + index * int(self.screen_y/44.28)))
                self.screen.blit(title_surface, title_rect)
    
            # Round number (big faded number)
            round_surface = round_font.render(f"{race['Round']:02}", True, grey_2)
            round_rect = round_surface.get_rect(topright=(rect.right - int(self.screen_x/114), rect.top + int(self.screen_y/110.7)))
            
            # Track layout image
            track_image = pygame.image.load(race['Menu_Item'])
            track_image = pygame.transform.scale(track_image, (self.screen_x / 4.275, self.screen_y / 2.7675))
            track_image_rect = track_image.get_rect(center=(rect.centerx, rect.centery + int(self.screen_y/55.35)))
            
            #self.screen.blit(title_surface, title_rect)
            self.screen.blit(round_surface, round_rect)
            self.screen.blit(track_image, track_image_rect)

    # Render Home Screen
    def render(self):
        self.screen.fill(background_colour)
        self.update_dots()
        
        # Title and Subtitle
        title_font = pygame.font.Font(font_name, int(self.screen_y/11.07))
        title = title_font.render(self.title_text, True, red)
        
        subtitle_font = pygame.font.Font(font_name, int(self.screen_y/36.9))
        subtitle = subtitle_font.render(self.subtitle_text, True, grey)
        
        title_rect = title.get_rect(center=(self.screen_x/2, self.screen_y/5.535 - self.scroll_offset))
        sub_rect = subtitle.get_rect(center=(self.screen_x/2, self.screen_y/4.1 - self.scroll_offset))
        
        self.screen.blit(title, title_rect)
        self.screen.blit(subtitle, sub_rect)

        # Return Menu Button
        return_font = pygame.font.Font(font_name, int(self.screen_y/22.14))
        return_image = pygame.transform.scale(self.return_image, (self.screen_x/28.5, self.screen_y/18.45))
        
        # Menu Cards icons
        card_title_font = pygame.font.Font(font_name, int(self.screen_y/39.5357142857))
        card_text_font = pygame.font.Font(font_name, int(self.screen_y/73.8))
        flag_image = pygame.transform.scale(self.flag_image, (self.screen_x/28.5, self.screen_y/18.45))
        settings_image = pygame.transform.scale(self.settings_image, (self.screen_x/28.5, self.screen_y/18.45))
        play_image = pygame.transform.scale(self.play_image, (self.screen_x/28.5, self.screen_y/18.45))
        
        for card in self.button:
            # Create transparent surface
            card_surface = pygame.Surface((card["rect"].width, card["rect"].height),pygame.SRCALPHA)

            # Ccolour changes
            if card["hover"]:
                r, g, b = card["hover_colour"]
                alpha = 150
                
            else:
                r, g, b = card["colour"]
                alpha = 200

            # Draw rounded rect
            pygame.draw.rect(card_surface, (r, g, b, alpha), card_surface.get_rect(), border_radius=18)

            # Blit to screen
            self.screen.blit(card_surface, card["rect"].topleft)

            # --- TEXT ---
            button_text = return_font.render(card["title"], True, white)
            text_pos = button_text.get_rect(midleft=(card["rect"].left + int(self.screen_x/24.4285714286), card["rect"].top + int(self.screen_y/36.9)))
            
            return_image = pygame.transform.scale(card["image"], (self.screen_x/28.5, self.screen_y/18.45))
            return_image_pos = return_image.get_rect(midleft=(card["rect"].left + int(self.screen_x/342), card["rect"].top + int(self.screen_y/36.9))) 
            
            self.screen.blit(button_text, text_pos)
            self.screen.blit(return_image, return_image_pos)
        
        for card in self.cards:
            # Create transparent surface
            card_surface = pygame.Surface((card["rect"].width, card["rect"].height),pygame.SRCALPHA)

            # Scolour changes
            if card["selected"]:
                r, g, b = card["selected_colour"]
                alpha = 200
                
            elif card["hover"]:
                r, g, b = card["hover_colour"]
                alpha = 150
                
            else:
                r, g, b = card["colour"]
                alpha = 200

            # Draw rounded rect
            pygame.draw.rect(card_surface, (r, g, b, alpha), card_surface.get_rect(), border_radius=18)

            # Blit to screen
            self.screen.blit(card_surface, card["rect"].topleft)

            # --- TEXT ---
            title_surface = card_title_font.render(card["title"], True, white)
            title_rect = title_surface.get_rect(midleft=(card["rect"].left + int(self.screen_x/114), card["rect"].centery - int(self.screen_y/36.9)))
            
            lines = card["desc"].split("\n")

            for index, line in enumerate(lines):
                desc_surface = card_text_font.render(line, True, (210, 210, 210))
                desc_rect = desc_surface.get_rect(midleft=(card["rect"].left + int(self.screen_x/114), card["rect"].centery + int(self.screen_y/55.35) + index * int(self.screen_y/44.28)))
                self.screen.blit(desc_surface, desc_rect)

            self.screen.blit(title_surface, title_rect)

        self.screen.blit(flag_image, (self.screen_x/8.9763779528, self.screen_y/2.9 - self.scroll_offset))
        self.screen.blit(settings_image, (self.screen_x/2.6057142857, self.screen_y/2.9 - self.scroll_offset))
        self.screen.blit(play_image, (self.screen_x/1.5244038333, self.screen_y/2.9 - self.scroll_offset))
        
        if self.selected_card == 0:
            self.draw_race_cards()
        
    # Update Loop
    def update(self):
        mouse_pos = pygame.mouse.get_pos()
        
        # Recalculate card layout when resizing
        new_w, new_h = self.screen.get_size()
        if new_w != self.screen_x or new_h != self.screen_y:
            self.screen_x, self.screen_y = new_w, new_h
            self.create_cards()
            self.button_1()
            self.create_dots()
            self.create_race_cards()

        for event in pygame.event.get():
            if event.type == pygame.MOUSEWHEEL:
                if self.selected_card != -1:           
                    self.scroll_offset -= event.y * 30  # scroll speed # Clamp scroll range
                    self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll))
                    self.button_1()
                    self.create_cards()
                    self.create_race_cards()

            if event.type == pygame.MOUSEBUTTONDOWN:
                card_num = -1
                for card in self.cards[:2]:  # only first 2 if that's intentional
                    card_num += 1
                    if card["rect"].collidepoint(mouse_pos):
                        # Select this one
                        if  card["selected"]:
                            card["selected"] = False
                            self.selected_card = -1
                            self.scroll_offset = 0
                            
                        else:
                            card["selected"] = True
                            self.selected_card = card_num # store index of selected card
                            
                        self.button_1()
                        self.create_cards()
                        self.create_race_cards()
                
                for card in self.button:
                    if card["rect"].collidepoint(mouse_pos):
                        self.s_Mode = card["mode"]

                if self.selected_card == 0:  
                    for card in self.race_cards:
                        if card["rect"].collidepoint(mouse_pos):
                            self.box_colours[0] = green
                            self.colours[0] = green
                            self.selected_card = -1
                            self.scroll_offset = 0
                            
                            circuit, grandprix = card["data"]["Track_Name"], card["data"]["Grand_Prix"]
                            with open("configs/sim_configuration.json", "r") as configFile:
                                config_data = json.load(configFile)
                                
                            # Update only required fields
                            config_data["Grand Prix"] = grandprix
                            config_data["Circuit"] = circuit
                            
                            # Write back to config file 
                            with open("configs/sim_configuration.json", "w") as configFile:
                                json.dump(config_data, configFile, indent=4)
                            
                            self.button_1()
                            self.create_cards()
        
            if event.type == pygame.QUIT:
                self.s_Mode = "Quit"
                
        # Smooth scaling
        self.box_scaling(mouse_pos)
        
        self.render()
        pygame.display.flip()
        fpsClock.tick(FPS)

        return self.s_Mode, self.screen