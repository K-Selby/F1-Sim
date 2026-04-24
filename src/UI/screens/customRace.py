# src/ui/screens/customRace.py

from src.UI.API.imports import *


class CustomRace:
    def __init__(self, s_Mode, screen):
        # ===== CORE STATE =====
        self.s_Mode = s_Mode
        self.screen = screen
        self.screen_x, self.screen_y = screen.get_size()
        # ===== SCREEN TEXT =====
        self.title_text = "Build Your Own Simulation"
        self.subtitle_text = "Select your prefered race settings and enjoy!"
        self.return_text = "Return to Home"
        self.generate_text = "Randomly Generate Grid Positions"
        # ===== IMAGES =====
        self.return_image = pygame.image.load("data/UI/Images/return.png")
        self.flag_image = pygame.image.load("data/UI/Images/flag.png")
        self.settings_image = pygame.image.load("data/UI/Images/settings.png")
        self.play_image = pygame.image.load("data/UI/Images/play_circle.png")
        self.dice_image = pygame.image.load("data/UI/Images/dice.png")
        # ===== FILE PATHS =====
        self.race_cards_json = "data/CircuitOptions/AllCircuits/races.json"
        self.teams_json = "configs/teams.json"
        # ===== CARD / PAGE STATE =====
        self.selected_card = -1
        self.text_desc_1 = "Choose any track from the previous years and \ncreate a custom race."
        self.text_desc_2 = ""
        self.colours = [red, red, green]
        self.box_colours = [box_colour, box_colour, box_colour]
        # ===== STORED UI DATA =====
        self.cards = []
        self.button = []
        self.dots = []
        self.race_cards = []
        self.circuit_boxes = []
        # ===== SELECTED RACE DATA =====
        self.grandprix = ""
        self.circuit = ""
        self.race_year = "2024"
        # ===== YEAR DROPDOWN =====
        self.season_dropdown_open = False
        self.season_dropdown_rect = None
        self.season_option_rects = []
        # ===== DRIVER / GRID DATA =====
        self.available_drivers = []
        self.grid_slots = []
        # ===== BACKGROUND / SCROLL =====
        self.dot_spacing = 40
        self.influence_radius = 150
        self.scroll_offset = 0
        self.max_scroll = 0
        # ===== INITIAL UI BUILD =====
        self.refresh_full_layout()

    # ===== LAYOUT REFRESH HELPERS =====
    def refresh_full_layout(self):
        # Rebuild everything used on this screen
        self.create_cards()
        self.create_buttons()
        self.create_dots()
        self.create_race_cards()
        self.create_year_option()
        self.load_available_drivers()
        self.create_starting_grid()
        self.create_circuit_characterisitcs()
        self.update_max_scroll()

    def refresh_scrolled_layout(self):
        # Rebuild layout that depends on scroll / positions
        self.create_buttons()
        self.create_cards()
        self.create_race_cards()
        self.create_year_option()
        self.create_starting_grid()
        self.create_circuit_characterisitcs()
        self.update_max_scroll()

    # ===== BACKGROUND =====
    def create_dots(self):
        self.dots.clear()

        for x in range(0, int(self.screen_x), self.dot_spacing):
            for y in range(0, int(self.screen_y), self.dot_spacing):
                self.dots.append({"pos": (x, y)})

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

    # ===== TOP CARDS =====
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
            self.text_desc_1,
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
                "selected": self.selected_card == i,
                "selected_colour": self.colours[i]
            })

    # ===== BUTTONS =====
    def create_buttons(self):
        self.button.clear()

        # Return button
        return_width = self.screen_x / 3.21
        return_height = self.screen_y / 18.45
        return_x = self.screen_x / 57
        return_y = (self.screen_y / 110.7) - self.scroll_offset

        return_rect = pygame.Rect(return_x, return_y, return_width, return_height)

        self.button.append({
            "base_rect": return_rect,
            "rect": return_rect.copy(),
            "title": self.return_text,
            "hover": False,
            "colour": box_colour,
            "hover_colour": purple,
            "scale": 1.0,
            "image": self.return_image,
            "mode": "Home"
        })

        # Random grid button
        generate_width = self.screen_x / 3.1
        generate_height = self.screen_y / 18.45
        generate_x = self.screen_x / 3
        generate_y = (self.screen_y / 1.08) - self.scroll_offset

        generate_rect = pygame.Rect(generate_x, generate_y, generate_width, generate_height)

        self.button.append({
            "base_rect": generate_rect,
            "rect": generate_rect.copy(),
            "title": self.generate_text,
            "hover": False,
            "colour": box_colour,
            "hover_colour": green,
            "scale": 1.0,
            "image": self.dice_image
        })

    def draw_ui_button(self, button, font_size, image_width, image_height):
        button_font = pygame.font.Font(font_name, font_size)

        button_surface = pygame.Surface((button["rect"].width, button["rect"].height), pygame.SRCALPHA)

        if button["hover"]:
            r, g, b = button["hover_colour"]
            alpha = 150
            
        else:
            r, g, b = button["colour"]
            alpha = 200

        pygame.draw.rect(button_surface, (r, g, b, alpha), button_surface.get_rect(), border_radius=18)
        self.screen.blit(button_surface, button["rect"].topleft)

        button_text = button_font.render(button["title"], True, white)
        text_pos = button_text.get_rect(midleft=(button["rect"].left + int(self.screen_x / 24.4285714286), button["rect"].top + int(self.screen_y / 36.9)))

        button_image = pygame.transform.scale(button["image"], (image_width, image_height))
        image_pos = button_image.get_rect(midleft=(button["rect"].left + int(self.screen_x / 342),button["rect"].top + int(self.screen_y / 36.9)))

        self.screen.blit(button_text, text_pos)
        self.screen.blit(button_image, image_pos)

    # ===== HOVER / SCALING =====
    def box_scaling(self, mouse_pos):
        # Top menu cards
        for card in self.cards:
            card["hover"] = card["rect"].collidepoint(mouse_pos)
            target_scale = 1.1 if card["hover"] else 1.0
            card["scale"] += (target_scale - card["scale"]) * 0.1

            base = card["base_rect"]
            new_width = base.width * card["scale"]
            new_height = base.height * card["scale"]

            card["rect"] = pygame.Rect(
                base.centerx - new_width / 2,
                base.centery - new_height / 2,
                new_width,
                new_height
            )

        # Circuit characteristic option boxes
        for item in self.circuit_boxes:
            for option in item["options"]:
                option["hover"] = option["rect"].collidepoint(mouse_pos)

        # Buttons
        for card in self.button:
            card["hover"] = card["rect"].collidepoint(mouse_pos)
            target_scale = 1.05 if card["hover"] else 1.0
            card["scale"] += (target_scale - card["scale"]) * 0.1

            base = card["base_rect"]
            new_width = base.width * card["scale"]
            new_height = base.height * card["scale"]

            card["rect"] = pygame.Rect(
                base.centerx - new_width / 2,
                base.centery - new_height / 2,
                new_width,
                new_height
            )

        # Race cards
        for card in self.race_cards:
            card["hover"] = card["rect"].collidepoint(mouse_pos)

    # ===== SCROLL LIMITS =====
    def update_max_scroll(self):
        self.max_scroll = 0

        # -------- TRACK SELECTION PAGE --------
        if self.selected_card == 0:
            cards_per_row = 4
            spacing_y = self.screen_y / 22.14
            card_height = self.screen_y / 3.1628571429
            race_cards_start_y = self.screen_y / 1.5814285714
            total_rows = (len(self.race_cards) + cards_per_row - 1) // cards_per_row

            if total_rows > 0:
                lowest_row_top = race_cards_start_y + ((total_rows - 1) * (card_height + spacing_y))
                race_cards_bottom = lowest_row_top + card_height
                
            else:
                race_cards_bottom = race_cards_start_y

            content_bottom = race_cards_bottom + (self.screen_y / 8)
            self.max_scroll = max(0, content_bottom - (self.screen_y * 0.5))

        # -------- SIMULATION SETTINGS PAGE --------
        elif self.selected_card == 1:
            year_section_bottom = self.screen_y / 1.5814285714 + (self.screen_y / 8)

            grid_start_y = self.screen_y / 1.0025
            row_gap = self.screen_y / 4
            slot_height = self.screen_y / 9.5

            last_row_y = grid_start_y + (9 * row_gap)
            right_side_extra = self.screen_y / 10
            grid_bottom = last_row_y + right_side_extra + slot_height

            random_button_bottom = self.screen_y / 1.08 + (self.screen_y / 18.45)

            circuit_start_y = grid_bottom + (self.screen_y / 8)
            circuit_row_gap = self.screen_y / 7.2
            circuit_count = 8

            last_circuit_y = circuit_start_y + ((circuit_count - 1) * circuit_row_gap)
            circuit_bottom = last_circuit_y + circuit_row_gap

            content_bottom = max(year_section_bottom, grid_bottom, random_button_bottom, circuit_bottom)

            open_dropdown_bottom = 0
            for slot in self.grid_slots:
                if slot["dropdown_open"] and slot["option_rects"]:
                    option_count = len(slot["option_rects"])
                    dropdown_height = slot["dropdown_rect"].height
                    dropdown_y = slot["dropdown_rect"].y + self.scroll_offset

                    open_dropdown_bottom = max(open_dropdown_bottom, dropdown_y + (dropdown_height * (option_count + 1)))

            content_bottom = max(content_bottom, open_dropdown_bottom)
            self.max_scroll = max(0, content_bottom - (self.screen_y * 0.5))

    # ===== TRACK SELECTION =====
    def create_race_cards(self):
        with open(self.race_cards_json, "r") as circuitFile:
            race_data = json.load(circuitFile)["Races"]

        self.race_cards.clear()

        cards_per_row = 4
        spacing_x = self.screen_x / 34.2
        spacing_y = self.screen_y / 22.14

        card_width = self.screen_x / 4.8857142857
        card_height = self.screen_y / 3.1628571429
        total_width = (card_width * cards_per_row) + (spacing_x * (cards_per_row - 1))
        start_x = (self.screen_x - total_width) / 2
        start_y = self.screen_y / 1.5814285714 - self.scroll_offset

        for index, race in enumerate(race_data):
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

    def draw_race_cards(self):
        race_title_font = pygame.font.Font(font_name, int(self.screen_y / 55))
        round_font = pygame.font.Font(font_name, int(self.screen_y / 15))

        for card in self.race_cards:
            race = card["data"]
            rect = card["rect"]

            card_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

            colour = box_hover_2 if card["hover"] else box_colour_2
            pygame.draw.rect(card_surface, colour, card_surface.get_rect(), border_radius=12)

            self.screen.blit(card_surface, rect.topleft)

            # Grand Prix title
            lines = race["Grand_Prix"].upper().split("\n")
            for index, line in enumerate(lines):
                title_surface = race_title_font.render(line, True, yellow)
                title_rect = title_surface.get_rect(topleft=(card["rect"].left + int(self.screen_x / 114), rect.top + int(self.screen_y / 73.8) + index * int(self.screen_y / 44.28)))
                self.screen.blit(title_surface, title_rect)

            # Round number
            round_surface = round_font.render(f"{race['Round']:02}", True, grey_2)
            round_rect = round_surface.get_rect(topright=(rect.right - int(self.screen_x / 114), rect.top + int(self.screen_y / 110.7)))

            # Track image
            track_image = pygame.image.load(race["Menu_Item"])
            track_image = pygame.transform.scale(track_image, (self.screen_x / 4.275, self.screen_y / 2.7675))
            track_image_rect = track_image.get_rect(center=(rect.centerx, rect.centery + int(self.screen_y / 55.35)))

            self.screen.blit(round_surface, round_rect)
            self.screen.blit(track_image, track_image_rect)

    # ===== YEAR DROPDOWN =====
    def create_year_option(self):
        season_options = ["2021", "2022", "2023", "2024"]

        start_x = self.screen_x / 2.95
        start_y = self.screen_y / 1.5814285714 - self.scroll_offset

        dropdown_width = self.screen_x / 8
        dropdown_height = self.screen_y / 18

        dropdown_x = start_x + self.screen_x / 4.5
        dropdown_y = start_y - dropdown_height / 2

        self.season_dropdown_rect = pygame.Rect(dropdown_x, dropdown_y, dropdown_width, dropdown_height)
        self.season_option_rects.clear()

        for i, option in enumerate(season_options):
            option_rect = pygame.Rect(dropdown_x,dropdown_y + dropdown_height * (i + 1),dropdown_width,dropdown_height)

            self.season_option_rects.append({
                "text": option,
                "rect": option_rect
            })

    def draw_year_option(self):
        title_font = pygame.font.Font(font_name, int(self.screen_y / 32))
        desc_font = pygame.font.Font(font_name, int(self.screen_y / 65))
        dropdown_font = pygame.font.Font(font_name, int(self.screen_y / 45))

        title_text = "Season Year ¦"
        desc_text = (
            "Choose what race season you want, this determines what teams & drivers\n"
            "are available and uses year specific data for the cars."
        )

        start_x = self.screen_x / 2.95
        start_y = self.screen_y / 1.5814285714 - self.scroll_offset

        title_surface = title_font.render(title_text, True, white)
        title_rect = title_surface.get_rect(midleft=(start_x, start_y))
        self.screen.blit(title_surface, title_rect)

        desc_lines = desc_text.split("\n")
        for i, line in enumerate(desc_lines):
            desc_surface = desc_font.render(line, True, grey)
            self.screen.blit(desc_surface, (start_x, start_y + self.screen_y / 18 + i * (self.screen_y / 40)))

        pygame.draw.rect(self.screen, box_colour, self.season_dropdown_rect, border_radius=8)
        pygame.draw.rect(self.screen, white, self.season_dropdown_rect, 2, border_radius=8)

        selected_surface = dropdown_font.render(self.race_year, True, white)
        selected_rect = selected_surface.get_rect(midleft=(self.season_dropdown_rect.left + 10, self.season_dropdown_rect.centery))
        self.screen.blit(selected_surface, selected_rect)

        arrow_surface = dropdown_font.render("▼", True, white)
        arrow_rect = arrow_surface.get_rect(center=(self.season_dropdown_rect.right - 18, self.season_dropdown_rect.centery))
        self.screen.blit(arrow_surface, arrow_rect)

        if self.season_dropdown_open:
            for option in self.season_option_rects:
                pygame.draw.rect(self.screen, box_colour_2, option["rect"], border_radius=6)
                pygame.draw.rect(self.screen, white, option["rect"], 1, border_radius=6)

                option_surface = dropdown_font.render(option["text"], True, white)
                option_rect = option_surface.get_rect(midleft=(option["rect"].left + 10, option["rect"].centery))
                self.screen.blit(option_surface, option_rect)

    # ===== STARTING GRID =====
    def create_starting_grid(self):
        # Keep current choices when rebuilding layout
        old_selected = {}
        for slot in self.grid_slots:
            old_selected[slot["position"]] = slot.get("selected_driver", {"id": "N/A", "display": "N/A"})

        self.grid_slots.clear()

        slot_width = self.screen_x / 4
        slot_height = self.screen_y / 9.5
        dropdown_width = slot_width / 1.225
        dropdown_height = slot_height / 1.8

        centre_x = self.screen_x / 2
        start_y = self.screen_y / 1.0025 - self.scroll_offset

        column_gap = self.screen_x / 18
        row_gap = self.screen_y / 4

        left_x = centre_x - column_gap - slot_width
        right_x = centre_x + column_gap

        for row in range(10):
            y = start_y + row * row_gap

            # Left side slot
            left_position = (row * 2) + 1
            left_dropdown = pygame.Rect(left_x + (slot_width - dropdown_width) / 2, y + slot_height / 3, dropdown_width, dropdown_height)

            self.grid_slots.append({
                "position": left_position,
                "side": "left",
                "x": left_x,
                "y": y,
                "slot_width": slot_width,
                "slot_height": slot_height,
                "dropdown_rect": left_dropdown,
                "selected_driver": old_selected.get(left_position, {"id": "N/A", "display": "N/A"}),
                "dropdown_open": False,
                "option_rects": []
            })

            # Right side slot
            right_position = (row * 2) + 2
            right_y = y + (self.screen_y / 10)
            right_dropdown = pygame.Rect(right_x + (slot_width - dropdown_width) / 2, right_y + slot_height / 3, dropdown_width, dropdown_height)

            self.grid_slots.append({
                "position": right_position,
                "side": "right",
                "x": right_x,
                "y": right_y,
                "slot_width": slot_width,
                "slot_height": slot_height,
                "dropdown_rect": right_dropdown,
                "selected_driver": old_selected.get(right_position, {"id": "N/A", "display": "N/A"}),
                "dropdown_open": False,
                "option_rects": []
            })

        self.build_grid_dropdown_options()

    def draw_starting_grid(self):
        title_font = pygame.font.Font(font_name, int(self.screen_y / 30))
        subtitle_font = pygame.font.Font(font_name, int(self.screen_y / 62))
        pos_font = pygame.font.Font(font_name, int(self.screen_y / 38))
        dropdown_font = pygame.font.Font(font_name, int(self.screen_y / 70))

        title_text = "Starting Grid Selection"
        desc_text = (
            "Decide the race starting order by choosing which driver starts in what positon.\n"
            "Or you can randomly assign drivers to positions on the grid."
        )

        title_surface = title_font.render(title_text, True, white)
        title_rect = title_surface.get_rect(center=(self.screen_x / 2, self.screen_y / 1.2 - self.scroll_offset))
        self.screen.blit(title_surface, title_rect)

        desc_lines = desc_text.split("\n")
        for i, line in enumerate(desc_lines):
            desc_surface = subtitle_font.render(line, True, grey)
            desc_rect = desc_surface.get_rect(
                center=(self.screen_x / 2, self.screen_y / 1.16 - self.scroll_offset + i * (self.screen_y / 40))
            )
            self.screen.blit(desc_surface, desc_rect)

        # Draw all slots and closed dropdowns
        for slot in self.grid_slots:
            x = slot["x"]
            y = slot["y"]
            slot_width = slot["slot_width"]
            slot_height = slot["slot_height"]
            dropdown_rect = slot["dropdown_rect"]

            pos_surface = pos_font.render(f"P{slot['position']}", True, white)
            pos_rect = pos_surface.get_rect(midleft=(x, y - self.screen_y / 60))
            self.screen.blit(pos_surface, pos_rect)

            pygame.draw.line(self.screen, white, (x, y), (x + slot_width, y), 3)
            pygame.draw.line(self.screen, white, (x, y), (x, y + slot_height * 0.75), 3)
            pygame.draw.line(self.screen, white, (x + slot_width, y), (x + slot_width, y + slot_height * 0.75), 3)

            pygame.draw.rect(self.screen, box_colour, dropdown_rect, border_radius=8)
            pygame.draw.rect(self.screen, white, dropdown_rect, 2, border_radius=8)

            selected_text = slot["selected_driver"]["display"]
            selected_surface = dropdown_font.render(selected_text, True, white)
            selected_text_rect = selected_surface.get_rect(midleft=(dropdown_rect.left + 10, dropdown_rect.centery))
            self.screen.blit(selected_surface, selected_text_rect)

            arrow_surface = dropdown_font.render("▼", True, white)
            arrow_rect = arrow_surface.get_rect(center=(dropdown_rect.right - 15, dropdown_rect.centery))
            self.screen.blit(arrow_surface, arrow_rect)

        # Draw open dropdowns last so they stay on top
        for slot in self.grid_slots:
            if slot["dropdown_open"]:
                for option in slot["option_rects"]:
                    pygame.draw.rect(self.screen, box_colour_2, option["rect"], border_radius=6)
                    pygame.draw.rect(self.screen, white, option["rect"], 1, border_radius=6)

                    option_surface = dropdown_font.render(option["display"], True, white)
                    option_text_rect = option_surface.get_rect(midleft=(option["rect"].left + 10, option["rect"].centery))
                    self.screen.blit(option_surface, option_text_rect)

    # ===== DRIVER DATA =====
    def load_available_drivers(self):
        self.available_drivers.clear()

        with open(self.teams_json, "r") as teamFile:
            teams_data = json.load(teamFile)

        year_data = teams_data.get(self.race_year, {})

        for team_name, team_info in year_data.items():
            drivers = team_info.get("drivers", [])[:2]

            for driver in drivers:
                driver_name = driver["name"]
                driver_number = driver["number"]
                display_text = f"{driver_name} {driver_number} ({team_name})"

                self.available_drivers.append({
                    "id": f"{driver_name}_{driver_number}_{team_name}",
                    "name": driver_name,
                    "number": driver_number,
                    "team": team_name,
                    "display": display_text
                })

    def get_free_driver_options(self, current_position):
        options = []
        used_driver_ids = set()

        for slot in self.grid_slots:
            if slot["position"] != current_position and slot["selected_driver"]["id"] != "N/A":
                used_driver_ids.add(slot["selected_driver"]["id"])

        for driver in self.available_drivers:
            if driver["id"] not in used_driver_ids:
                options.append({
                    "id": driver["id"],
                    "display": driver["display"]
                })

        return options

    def build_grid_dropdown_options(self):
        for slot in self.grid_slots:
            slot["option_rects"].clear()

            options = self.get_free_driver_options(slot["position"])
            dropdown_rect = slot["dropdown_rect"]

            for i, option in enumerate(options):
                option_rect = pygame.Rect(
                    dropdown_rect.x,
                    dropdown_rect.y + dropdown_rect.height * (i + 1),
                    dropdown_rect.width,
                    dropdown_rect.height
                )

                slot["option_rects"].append({
                    "id": option["id"],
                    "display": option["display"],
                    "rect": option_rect
                })

    def get_starting_grid(self):
        starting_grid = []

        for slot in sorted(self.grid_slots, key=lambda s: s["position"]):
            starting_grid.append({
                "position": slot["position"],
                "driver_id": slot["selected_driver"]["id"],
                "display": slot["selected_driver"]["display"]
            })

        return starting_grid

    # ===== CIRCUIT CHARACTERISTICS =====
    def create_circuit_characterisitcs(self):
        # Keep selected values if layout gets rebuilt
        old_values = {}
        for item in self.circuit_boxes:
            old_values[item["name"]] = item.get("selected", "Default")

        self.circuit_boxes.clear()

        characteristics = [
            {
                "name": "traction",
                "title": "Traction",
                "desc": "Higher values mean better grip when accelerating out of slower corners, so cars can put\nthe power down earlier and gain more speed on corner exit. This usually improves\nlap time, especially at circuits with many traction zones. Lower values make wheelspin\nand poor exits more likely, which hurts acceleration and can make cars slower over a lap."
            },
            {
                "name": "asphalt_grip",
                "title": "Asphalt Grip",
                "desc": "Higher values mean the track surface naturally provides more grip, which improves\nbraking, cornering and acceleration. This normally leads to faster and more stable lap times.\nLower values mean the surface is more slippery, so the car has less overall grip\nand drivers are more likely to lose time through braking zones and corners."
            },
            {
                "name": "asphalt_abrasion",
                "title": "Asphalt Abrasion",
                "desc": "Higher values mean the track surface is rougher and wears away the tyre surface\nmore aggressively. This increases tyre degradation, can reduce stint length, and may force\nextra pit stops or more conservative strategy choices. Lower values mean the surface\nis smoother and tyres usually last longer with less performance drop-off."
            },
            {
                "name": "track_evolution",
                "title": "Track Evolution",
                "desc": "Higher values mean the circuit improves more as rubber is laid down, so grip increases\nas the session or race develops. This can make later laps faster and may change the\nbalance of strategy during the race. Lower values mean the track changes less over time,\nso conditions stay more consistent from start to finish."
            },
            {
                "name": "tyre_stress",
                "title": "Tyre Stress",
                "desc": "Higher values mean the circuit places more total load through the tyres over the lap,\nwhich increases tyre wear and can cause performance to drop more quickly during a stint.\nThis often pushes teams towards shorter stints and more pit stops. Lower values mean\nthe circuit is easier on the tyres, allowing longer stints and more flexible strategy options."
            },
            {
                "name": "braking",
                "title": "Braking",
                "desc": "Higher values mean the circuit has heavier or more demanding braking zones, so cars\nlose and regain more speed into corners. This can increase tyre and brake load, affect\nconsistency, and make overtaking opportunities more important. Lower values mean braking\ndemands are lighter, so the lap is less dependent on major stop-start sections."
            },
            {
                "name": "lateral",
                "title": "Lateral",
                "desc": "Higher values mean the circuit puts more side load through the tyres in medium and\nhigh-speed corners. This increases cornering stress and can raise tyre temperatures and\ndegradation, especially over longer stints. Lower values mean less sustained cornering\nload, so tyres are usually managed more easily and performance stays more consistent."
            },
            {
                "name": "downforce",
                "title": "Downforce",
                "desc": "Higher values mean the circuit rewards high-downforce performance more, usually\nbecause of more medium and high-speed cornering sections. Cars with strong aerodynamic\ngrip tend to gain more lap time here. Lower values mean the circuit is less dependent on\ndownforce and may favour lower-drag efficiency, straight-line speed, or traction instead."
            }
        ]

        if self.grid_slots:
            grid_bottom = max(slot["y"] + slot["slot_height"] for slot in self.grid_slots)
            
        else:
            grid_bottom = self.screen_y / 1.2

        start_y = grid_bottom + (self.screen_y / 8)
        row_gap = self.screen_y / 7.2

        option_width = self.screen_x / 22
        option_height = self.screen_y / 22
        option_gap = self.screen_x / 140
        option_start_x = self.screen_x / 1.95

        for i, item in enumerate(characteristics):
            y = start_y + (i * row_gap)

            options = []
            option_labels = ["Default", "1", "2", "3", "4", "5"]

            for j, label in enumerate(option_labels):
                rect_x = option_start_x + j * (option_width + option_gap)
                rect = pygame.Rect(rect_x, y, option_width, option_height)

                options.append({
                    "label": label,
                    "rect": rect,
                    "hover": False
                })

            self.circuit_boxes.append({
                "name": item["name"],
                "title": item["title"],
                "desc": item["desc"],
                "y": y,
                "selected": old_values.get(item["name"], "Default"),
                "options": options
            })

    def draw_circuit_characterisitcs(self):
        title_font = pygame.font.Font(font_name, int(self.screen_y / 30))
        subtitle_font = pygame.font.Font(font_name, int(self.screen_y / 62))
        name_font = pygame.font.Font(font_name, int(self.screen_y / 42))
        desc_font = pygame.font.Font(font_name, int(self.screen_y / 80))
        option_font = pygame.font.Font(font_name, int(self.screen_y / 70))

        if self.circuit_boxes:
            section_y = self.circuit_boxes[0]["y"] - (self.screen_y / 10)
            
        else:
            section_y = self.screen_y / 2

        title_surface = title_font.render("Circuit Characteristics", True, white)
        title_rect = title_surface.get_rect(center=(self.screen_x / 2, section_y))
        self.screen.blit(title_surface, title_rect)

        subtitle_text = (
            "Adjust the circuit values used by the simulation. Higher and lower values change\n"
            "how the track behaves and how demanding it is on the car and tyres."
        )

        subtitle_lines = subtitle_text.split("\n")
        for i, line in enumerate(subtitle_lines):
            sub_surface = subtitle_font.render(line, True, grey)
            sub_rect = sub_surface.get_rect(center=(self.screen_x / 2, section_y + self.screen_y / 28 + i * (self.screen_y / 40)))
            self.screen.blit(sub_surface, sub_rect)

        name_x = self.screen_x / 7
        desc_x = self.screen_x / 7

        for item in self.circuit_boxes:
            name_surface = name_font.render(item["title"], True, white)
            self.screen.blit(name_surface, (name_x, item["y"]))

            desc_lines = item["desc"].split("\n")
            for i, line in enumerate(desc_lines):
                desc_surface = desc_font.render(line, True, grey)
                self.screen.blit(desc_surface, (desc_x, item["y"] + self.screen_y / 28 + i * (self.screen_y / 55)))

            for option in item["options"]:
                rect = option["rect"]
                selected_label = item["selected"]

                if selected_label == option["label"]:
                    border_colour = white
                    
                elif option["hover"]:
                    border_colour = grey
                
                else:
                    border_colour = (0, 0, 0, 0)

                pygame.draw.rect(self.screen, box_colour, rect, border_radius=6)

                if selected_label == option["label"] or option["hover"]:
                    pygame.draw.rect(self.screen, border_colour, rect, 2, border_radius=6)

                option_surface = option_font.render(option["label"], True, white)
                option_rect = option_surface.get_rect(center=rect.center)
                self.screen.blit(option_surface, option_rect)

    # ===== VALIDATION / SAVE =====
    def validate_simulation_settings(self):
        # Build circuit characteristic values
        circuit_characteristics = {}
        for item in self.circuit_boxes:
            circuit_characteristics[item["name"]] = item["selected"]

        values = {
            "circuit": self.circuit,
            "grandprix": self.grandprix,
            "race_year": self.race_year,
            "starting_grid": self.get_starting_grid(),
            "circuit_characteristics": circuit_characteristics
        }

        has_circuit = self.circuit != "" and self.grandprix != ""

        grid_complete = True
        for slot in self.grid_slots:
            if slot["selected_driver"]["id"] == "N/A":
                grid_complete = False
                break

        if not has_circuit:
            if not grid_complete:
                self.text_desc_2 = "\n\n You must select a circuit and complete the starting\ngrid before you can start the simultion."
                
            else:
                self.text_desc_2 = "\n\n You must select a circuit before you\ncan start the simultion."

        elif not grid_complete:
            self.text_desc_2 = "\n\n You must complete the starting grid before\nyou can start the simultion."

        else:
            self.text_desc_2 = ""

        is_complete = has_circuit and grid_complete
        return is_complete, values

    def save_sim_configuration(self, values):
        folder_path = "data/RaceData/SimulationConfigs"
        os.makedirs(folder_path, exist_ok=True)

        timestamp = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        file_name = f"RaceConfig-{timestamp}.json"
        file_path = os.path.join(folder_path, file_name)

        config_data = {
            "circuit": values["circuit"],
            "grandprix": values["grandprix"],
            "race_year": values["race_year"],
            "starting_grid": values["starting_grid"],
            "circuit_characteristics": values["circuit_characteristics"]
        }

        with open(file_path, "w") as file:
            json.dump(config_data, file, indent=4)

        return file_path

    # ===== RENDER =====
    def render(self):
        self.screen.fill(background_colour)
        self.update_dots()

        # Screen title
        title_font = pygame.font.Font(font_name, int(self.screen_y / 11.07))
        title = title_font.render(self.title_text, True, red)

        subtitle_font = pygame.font.Font(font_name, int(self.screen_y / 36.9))
        subtitle = subtitle_font.render(self.subtitle_text, True, grey)

        title_rect = title.get_rect(center=(self.screen_x / 2, self.screen_y / 5.535 - self.scroll_offset))
        sub_rect = subtitle.get_rect(center=(self.screen_x / 2, self.screen_y / 4.1 - self.scroll_offset))

        self.screen.blit(title, title_rect)
        self.screen.blit(subtitle, sub_rect)

        # Card icons
        flag_image = pygame.transform.scale(self.flag_image, (self.screen_x / 28.5, self.screen_y / 18.45))
        settings_image = pygame.transform.scale(self.settings_image, (self.screen_x / 28.5, self.screen_y / 18.45))
        play_image = pygame.transform.scale(self.play_image, (self.screen_x / 28.5, self.screen_y / 18.45))

        # Return button
        self.draw_ui_button(self.button[0], int(self.screen_y / 22.14), self.screen_x / 28.5, self.screen_y / 18.45)

        # Card text
        card_title_font = pygame.font.Font(font_name, int(self.screen_y / 39.5357142857))
        card_text_font = pygame.font.Font(font_name, int(self.screen_y / 73.8))

        count = 0
        for card in self.cards:
            count += 1

            card_surface = pygame.Surface((card["rect"].width, card["rect"].height), pygame.SRCALPHA)

            if card["selected"]:
                r, g, b = card["selected_colour"]
                alpha = 200
                
            elif card["hover"]:
                r, g, b = card["hover_colour"]
                alpha = 150
                
            else:
                r, g, b = card["colour"]
                alpha = 200

            pygame.draw.rect(card_surface, (r, g, b, alpha), card_surface.get_rect(), border_radius=18)
            self.screen.blit(card_surface, card["rect"].topleft)

            title_surface = card_title_font.render(card["title"], True, white)
            title_rect = title_surface.get_rect(midleft=(card["rect"].left + int(self.screen_x / 114), card["rect"].centery - int(self.screen_y / 36.9)))

            lines = card["desc"].split("\n")
            for index, line in enumerate(lines):
                desc_surface = card_text_font.render(line, True, (210, 210, 210))
                desc_rect = desc_surface.get_rect(midleft=(card["rect"].left + int(self.screen_x / 114), card["rect"].centery + int(self.screen_y / 55.35) + index * int(self.screen_y / 44.28)))
                self.screen.blit(desc_surface, desc_rect)

            if count == 3 and self.text_desc_2 != "":
                error_lines = self.text_desc_2.split("\n")
                for index_2, line in enumerate(error_lines):
                    desc_surface = card_text_font.render(line, True, red)
                    desc_rect = desc_surface.get_rect(midleft=(card["rect"].left + int(self.screen_x / 114), card["rect"].centery + int(self.screen_y / 24.6) + index_2 * int(self.screen_y / 44.28)))
                    self.screen.blit(desc_surface, desc_rect)

            self.screen.blit(title_surface, title_rect)

        self.screen.blit(flag_image, (self.screen_x / 8.9763779528, self.screen_y / 2.9 - self.scroll_offset))
        self.screen.blit(settings_image, (self.screen_x / 2.6057142857, self.screen_y / 2.9 - self.scroll_offset))
        self.screen.blit(play_image, (self.screen_x / 1.5244038333, self.screen_y / 2.9 - self.scroll_offset))

        # Page specific content
        if self.selected_card == 0:
            self.draw_race_cards()

        if self.selected_card == 1:
            self.draw_ui_button(self.button[1], int(self.screen_y / 40), self.screen_x / 28.5, self.screen_y / 18.45)
            self.draw_year_option()
            self.draw_circuit_characterisitcs()
            self.draw_starting_grid()

    # ===== UPDATE =====
    def update(self):
        filepath = ""
        mouse_pos = pygame.mouse.get_pos()

        # Rebuild layout on resize
        new_w, new_h = self.screen.get_size()
        if new_w != self.screen_x or new_h != self.screen_y:
            self.screen_x, self.screen_y = new_w, new_h
            self.refresh_full_layout()

        for event in pygame.event.get():
            # Scroll only when a card page is open
            if event.type == pygame.MOUSEWHEEL:
                if self.selected_card != -1:
                    self.scroll_offset -= event.y * 30
                    self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll))
                    self.refresh_scrolled_layout()

            if event.type == pygame.MOUSEBUTTONDOWN:
                # ===== TOP CARD SELECTION =====
                card_num = -1
                for card in self.cards[:2]:
                    card_num += 1

                    if card["rect"].collidepoint(mouse_pos):
                        if card["selected"]:
                            card["selected"] = False
                            self.selected_card = -1
                            self.scroll_offset = 0
                            
                        else:
                            card["selected"] = True
                            self.selected_card = card_num

                        self.refresh_full_layout()

                # ===== START SIMULATION =====
                if self.cards[2]["rect"].collidepoint(mouse_pos):
                    is_complete, values = self.validate_simulation_settings()

                    if is_complete:
                        filepath = self.save_sim_configuration(values)
                        self.s_Mode = "Simulation"

                # ===== RETURN BUTTON =====
                if self.button[0]["rect"].collidepoint(mouse_pos):
                    self.s_Mode = self.button[0]["mode"]

                # ===== TRACK CARD CLICK =====
                if self.selected_card == 0:
                    for card in self.race_cards:
                        if card["rect"].collidepoint(mouse_pos):
                            self.box_colours[0] = green
                            self.colours[0] = green
                            self.selected_card = -1
                            self.scroll_offset = 0

                            self.circuit = card["data"]["Track_Name"]
                            self.grandprix = card["data"]["Grand_Prix"]
                            self.text_desc_1 = (
                                f"Choose any track from the previous years and \ncreate a custom race.\n\n"
                                f" You have selected the {self.grandprix} at the {self.circuit}."
                            )

                            self.refresh_full_layout()
                            break

                # ===== SETTINGS PAGE CLICKS =====
                if self.selected_card == 1:
                    clicked_anything = False

                    # -------- YEAR DROPDOWN --------
                    if self.season_dropdown_rect.collidepoint(mouse_pos):
                        self.season_dropdown_open = not self.season_dropdown_open
                        clicked_anything = True

                    elif self.season_dropdown_open:
                        clicked_option = False

                        for option in self.season_option_rects:
                            if option["rect"].collidepoint(mouse_pos):
                                self.race_year = option["text"]
                                self.season_dropdown_open = False
                                self.load_available_drivers()

                                # Reset grid after changing season
                                for slot in self.grid_slots:
                                    slot["selected_driver"] = {"id": "N/A", "display": "N/A"}
                                    slot["dropdown_open"] = False

                                self.build_grid_dropdown_options()
                                clicked_option = True
                                clicked_anything = True
                                break

                        if not clicked_option:
                            self.season_dropdown_open = False

                    # -------- RANDOM GRID BUTTON --------
                    if self.button[1]["rect"].collidepoint(mouse_pos):
                        self.season_dropdown_open = False

                        for slot in self.grid_slots:
                            slot["dropdown_open"] = False

                        random_drivers = self.available_drivers.copy()
                        random.shuffle(random_drivers)

                        for i, slot in enumerate(self.grid_slots):
                            if i < len(random_drivers):
                                slot["selected_driver"] = {
                                    "id": random_drivers[i]["id"],
                                    "display": random_drivers[i]["display"]
                                }
                                
                            else:
                                slot["selected_driver"] = {
                                    "id": "N/A",
                                    "display": "N/A"
                                }

                        self.build_grid_dropdown_options()
                        clicked_anything = True

                    # -------- GRID DROPDOWNS --------
                    for slot in self.grid_slots:
                        if slot["dropdown_rect"].collidepoint(mouse_pos):
                            for other_slot in self.grid_slots:
                                other_slot["dropdown_open"] = False

                            slot["dropdown_open"] = not slot["dropdown_open"]

                            if slot["dropdown_open"]:
                                self.build_grid_dropdown_options()

                            clicked_anything = True
                            break

                        if slot["dropdown_open"]:
                            option_clicked = False

                            for option in slot["option_rects"]:
                                if option["rect"].collidepoint(mouse_pos):
                                    slot["selected_driver"] = {
                                        "id": option["id"],
                                        "display": option["display"]
                                    }
                                    slot["dropdown_open"] = False
                                    self.build_grid_dropdown_options()
                                    option_clicked = True
                                    clicked_anything = True
                                    break

                            if option_clicked:
                                break

                    # -------- CIRCUIT CHARACTERISTIC BOXES --------
                    for item in self.circuit_boxes:
                        option_clicked = False

                        for option in item["options"]:
                            if option["rect"].collidepoint(mouse_pos):
                                item["selected"] = option["label"]
                                clicked_anything = True
                                option_clicked = True
                                break

                        if option_clicked:
                            break

                    # Close dropdowns if user clicked away
                    if not clicked_anything:
                        self.season_dropdown_open = False
                        for slot in self.grid_slots:
                            slot["dropdown_open"] = False

            if event.type == pygame.QUIT:
                self.s_Mode = "Quit"

        # Update hover / scale animation
        self.box_scaling(mouse_pos)

        self.render()
        pygame.display.flip()
        fpsClock.tick(FPS)

        return self.s_Mode, self.screen, filepath