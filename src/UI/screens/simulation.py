from src.UI.API.imports import *
from src.RaceSimulator import main

class Simulation:
    def __init__(self, s_Mode, screen, filepath):
        self.s_Mode = s_Mode
        self.screen = screen
        self.filepath = filepath
        self.screen_x, self.screen_y = screen.get_size()
        self.dots = []
        self.dot_spacing = 40
        self.influence_radius = 150
        self.timing_update_interval = 2.0
        self.last_timing_update = 0.0
        self.cached_classification = []
        self.sim_finished = False
        self.speed_presets = [1.0, 2.0, 10.0]
        self.sim_speed = 1.0
        self.custom_speed_input_active = False
        self.custom_speed_input = ""
        self.speed_buttons = []
        self.create_dots()
        self.create_speed_buttons()
        # Build race manager 
        self.rm = main(filepath)
        self.rm.write_to_log("Simulation started.")
        self.rm.broadcast_public_signals()
        for team in self.rm.teams:
            team.decide()
            
        self.gp_title = self.rm.grandprix
        self.circuit_subtitle = f"{self.rm.circuit_name} -- {self.rm.season}"
        self.lap_text = f"Lap {self.rm.lap_number + 1}/{self.rm.total_laps}"
        self.cached_classification = self.get_live_classification()

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

    def draw_title_bar(self):
        title_bar_height = self.screen_y / 8.5
        title_bar_width = self.screen_x / 2
        title_font = pygame.font.Font(font_name, int(self.screen_y / 18))
        subtitle_font = pygame.font.Font(font_name, int(self.screen_y / 48))
        lap_font = pygame.font.Font(font_name, int(self.screen_y / 42))
        
        r, g, b = red
        
        # Background bar
        bar_surface = pygame.Surface((title_bar_width, title_bar_height), pygame.SRCALPHA)
        pygame.draw.rect(bar_surface, (r,g,b, 220), bar_surface.get_rect(), border_radius=18)
        bar_rect = bar_surface.get_rect(center=(self.screen_x / 2, title_bar_height / 1.8))
        self.screen.blit(bar_surface, bar_rect)

        # Main title
        title_surface = title_font.render(self.gp_title, True, white)
        title_rect = title_surface.get_rect(center=(self.screen_x / 2, title_bar_height / 2.5))
        self.screen.blit(title_surface, title_rect)

        # Subtitle
        subtitle_surface = subtitle_font.render(self.circuit_subtitle, True, grey)
        subtitle_rect = subtitle_surface.get_rect(center=(self.screen_x / 2, title_bar_height / 1.45))
        self.screen.blit(subtitle_surface, subtitle_rect)
        
        # Lap count
        current_lap = min(self.rm.lap_number, self.rm.total_laps)
        lap_text = f"Lap {current_lap}/{self.rm.total_laps}"
        lap_surface = lap_font.render(lap_text, True, white)
        lap_rect = lap_surface.get_rect(center=(self.screen_x / 2, title_bar_height / 1.15))
        self.screen.blit(lap_surface, lap_rect)

    def get_live_classification(self):
        finished_cars = []
        running_cars = []
        pit_cars = []
        dnf_cars = []

        for car in self.rm.cars:
            if car.retired:
                dnf_cars.append(car)
            elif car.lap_count >= self.rm.total_laps:
                finished_cars.append(car)
            elif car.in_pit_lane:
                pit_cars.append(car)
            else:
                running_cars.append(car)

        # Finished cars must be ordered by total race time
        finished_cars.sort(key=lambda car: car.total_time)

        # Running and pit cars are still ordered by race progress
        running_cars.sort(key=lambda car: self.rm.get_progress(car), reverse=True)
        pit_cars.sort(key=lambda car: self.rm.get_progress(car), reverse=True)

        classification = []

        # -----------------------------
        # Finished cars
        # -----------------------------
        winner_time = finished_cars[0].total_time if finished_cars else None

        for car in finished_cars:
            if winner_time is not None and car == finished_cars[0]:
                gap_ahead = "LEADER"
            elif winner_time is not None:
                gap_ahead = f"+{(car.total_time - winner_time):.3f}"
            else:
                gap_ahead = "FIN"

            classification.append({
                "position": len(classification) + 1,
                "driver": car.car_id,
                "team": car.team_id,
                "gap_ahead": gap_ahead,
                "status": "finished"
            })

        # -----------------------------
        # Running cars
        # -----------------------------
        for index, car in enumerate(running_cars):
            if index == 0 and not finished_cars:
                gap_ahead = "LEADER"
            elif index == 0 and finished_cars:
                finished_ahead = finished_cars[-1]
                gap_ahead = f"+{max(0.0, (car.total_time + car.current_lap_time) - finished_ahead.total_time):.3f}"
            else:
                ahead_car = running_cars[index - 1]
                gap_distance = max(0.0, self.rm.get_progress(ahead_car) - self.rm.get_progress(car))
                ref_speed = max(car.last_speed_mps, 1.0)
                time_gap = gap_distance / ref_speed
                gap_ahead = f"+{time_gap:.3f}"

            classification.append({
                "position": len(classification) + 1,
                "driver": car.car_id,
                "team": car.team_id,
                "gap_ahead": gap_ahead,
                "status": "running"
            })

        # -----------------------------
        # Pit cars
        # -----------------------------
        for car in pit_cars:
            classification.append({
                "position": len(classification) + 1,
                "driver": car.car_id,
                "team": car.team_id,
                "gap_ahead": "IN PIT",
                "status": "pit"
            })

        # -----------------------------
        # DNF cars
        # -----------------------------
        for car in dnf_cars:
            classification.append({
                "position": len(classification) + 1,
                "driver": car.car_id,
                "team": car.team_id,
                "gap_ahead": "DNF",
                "status": "dnf"
            })

        return classification

    def draw_timing_tower(self):
        title_font = pygame.font.Font(font_name, int(self.screen_y / 28))
        header_font = pygame.font.Font(font_name, int(self.screen_y / 55))
        row_font = pygame.font.Font(font_name, int(self.screen_y / 62))

        tower_width = self.screen_x / 3.8
        tower_height = self.screen_y / 1.225
        tower_x = self.screen_x / 7.2
        tower_y = self.screen_y / 1.775
        
        r, g, b, = box_colour_2

        # Background
        tower_surface = pygame.Surface((tower_width, tower_height), pygame.SRCALPHA)
        pygame.draw.rect(tower_surface, (r, g, b, 210), tower_surface.get_rect(), border_radius=18)
        tower_rect = tower_surface.get_rect(center=(tower_x, tower_y))
        self.screen.blit(tower_surface, tower_rect)

        # Title
        title_surface = title_font.render("Live Timing Tower", True, white)
        title_rect = title_surface.get_rect(center=(tower_x, tower_height / 4.3))
        self.screen.blit(title_surface, title_rect)

        # Headers
        header_y = tower_height / 3.55
        pos_x = tower_width / 8
        drv_x = tower_width / 3
        gap_x = tower_width / 1.2
        pos_header = header_font.render("POS", True, grey)
        drv_header = header_font.render("DRIVER", True, grey)
        gap_header = header_font.render("GAP", True, grey)
        
        pos_rect = pos_header.get_rect(center=(pos_x, header_y))
        drv_rect = drv_header.get_rect(center=(drv_x, header_y))
        gap_rect = gap_header.get_rect(center=(gap_x, header_y))

        self.screen.blit(pos_header, pos_rect)
        self.screen.blit(drv_header, drv_rect)
        self.screen.blit(gap_header, gap_rect)

        # Rows
        classification = self.cached_classification

        row_start_y = tower_height / 3.1
        row_height = tower_width / 13

        for index, entry in enumerate(classification):
            row_y = row_start_y + (index * row_height)

            if row_y > tower_y + tower_height - row_height:
                break
            
            r, g, b = red_2
            # Separator line
            pygame.draw.line(self.screen, (r,g,b, 5), (tower_x - tower_width / 2, row_y + row_height / 2), (tower_x + tower_width / 2, row_y + row_height / 2), 1)

            if entry["status"] == "dnf":
                text_colour = grey
                gap_colour = grey
            elif entry["status"] == "pit":
                text_colour = white
                gap_colour = yellow
            elif entry["gap_ahead"] == "LEADER":
                text_colour = white
                gap_colour = green
            else:
                text_colour = white
                gap_colour = white

            pos_surface = row_font.render(str(entry["position"]), True, text_colour)
            driver_surface = row_font.render(entry["driver"], True, text_colour)
            gap_surface = row_font.render(entry["gap_ahead"], True, gap_colour)
            
            pos_surface_rect = pos_surface.get_rect(center=(tower_width / 8, row_y))
            driver_surface_rect = driver_surface.get_rect(center=(tower_width / 3, row_y))
            gap_surface_rect = gap_surface.get_rect(center=(tower_width / 1.2, row_y))

            self.screen.blit(pos_surface, pos_surface_rect)
            self.screen.blit(driver_surface, driver_surface_rect)
            self.screen.blit(gap_surface, gap_surface_rect)

    def create_speed_buttons(self):
        self.speed_buttons.clear()

        button_y = self.screen_y / 1.08
        side_width = self.screen_x / 14
        middle_width = self.screen_x / 10
        button_height = self.screen_y / 18
        gap = self.screen_x / 120

        total_width = (side_width * 2) + middle_width + (gap * 2)
        start_x = (self.screen_x - total_width) / 2

        slow_rect = pygame.Rect(start_x, button_y, side_width, button_height)
        speed_rect = pygame.Rect(start_x + side_width + gap, button_y, middle_width, button_height)
        fast_rect = pygame.Rect(start_x + side_width + gap + middle_width + gap, button_y, side_width, button_height)

        self.speed_buttons.append({
            "name": "slow",
            "rect": slow_rect,
            "text": "Slow",
            "hover": False
        })

        self.speed_buttons.append({
            "name": "speed",
            "rect": speed_rect,
            "text": "",
            "hover": False
        })

        self.speed_buttons.append({
            "name": "fast",
            "rect": fast_rect,
            "text": "Fast",
            "hover": False
        })

    def format_speed_text(self):
        if float(self.sim_speed).is_integer():
            return f"{int(self.sim_speed)}x"
        return f"{self.sim_speed:.1f}x"

    def increase_speed(self):
        if self.sim_speed < 1.0:
            self.sim_speed = 1.0
            return

        if self.sim_speed < 2.0:
            self.sim_speed = 2.0
            return

        if self.sim_speed < 10.0:
            self.sim_speed = 10.0
            return

        self.sim_speed = 10.0

    def decrease_speed(self):
        if self.sim_speed > 10.0:
            self.sim_speed = 10.0
            return

        if self.sim_speed > 2.0:
            self.sim_speed = 2.0
            return

        if self.sim_speed > 1.0:
            self.sim_speed = 1.0
            return

        self.sim_speed = 1.0

    def render(self):
        self.screen.fill(background_colour)
        self.update_dots()
        self.draw_title_bar()
        self.draw_timing_tower()
        self.draw_speed_controls()

    def draw_speed_controls(self):
        button_font = pygame.font.Font(font_name, int(self.screen_y / 48))
        input_font = pygame.font.Font(font_name, int(self.screen_y / 46))

        for button in self.speed_buttons:
            rect = button["rect"]

            if button["hover"]:
                colour = box_hover_2
            else:
                colour = box_colour_2

            pygame.draw.rect(self.screen, colour, rect, border_radius=12)
            pygame.draw.rect(self.screen, white, rect, 2, border_radius=12)

            if button["name"] == "speed":
                if self.custom_speed_input_active:
                    display_text = self.custom_speed_input if self.custom_speed_input != "" else "_"
                else:
                    display_text = self.format_speed_text()

                text_surface = input_font.render(display_text, True, white)
            else:
                text_surface = button_font.render(button["text"], True, white)

            text_rect = text_surface.get_rect(center=rect.center)
            self.screen.blit(text_surface, text_rect)

    def update(self):
        mouse_pos = pygame.mouse.get_pos()

        # Resize handling
        new_w, new_h = self.screen.get_size()
        if new_w != self.screen_x or new_h != self.screen_y:
            self.screen_x, self.screen_y = new_w, new_h
            self.create_dots()
            self.create_speed_buttons()

        # Hover states
        for button in self.speed_buttons:
            button["hover"] = button["rect"].collidepoint(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.s_Mode = "Quit"

            if event.type == pygame.MOUSEBUTTONDOWN:
                clicked_speed_button = False

                for button in self.speed_buttons:
                    if button["rect"].collidepoint(mouse_pos):
                        clicked_speed_button = True

                        if button["name"] == "slow":
                            self.custom_speed_input_active = False
                            self.decrease_speed()

                        elif button["name"] == "fast":
                            self.custom_speed_input_active = False
                            self.increase_speed()

                        elif button["name"] == "speed":
                            self.custom_speed_input_active = True
                            self.custom_speed_input = ""

                        break

                if not clicked_speed_button:
                    self.custom_speed_input_active = False

            if event.type == pygame.KEYDOWN and self.custom_speed_input_active:
                if event.key == pygame.K_RETURN:
                    if self.custom_speed_input != "":
                        try:
                            entered_value = float(self.custom_speed_input)
                            if 0.5 <= entered_value <= 100:
                                self.sim_speed = entered_value
                        except ValueError:
                            pass

                    self.custom_speed_input_active = False

                elif event.key == pygame.K_BACKSPACE:
                    self.custom_speed_input = self.custom_speed_input[:-1]

                else:
                    if event.unicode.isdigit():
                        self.custom_speed_input += event.unicode
                    elif event.unicode == "." and "." not in self.custom_speed_input:
                        self.custom_speed_input += "."

        # Step simulation
        if not self.rm.race_finished:
            sim_dt = self.rm.dt * self.sim_speed
            self.rm.step_tick(sim_dt)

            if (self.rm.sim_time - self.last_timing_update) >= self.timing_update_interval:
                self.cached_classification = self.get_live_classification()
                self.last_timing_update = self.rm.sim_time

        elif not self.sim_finished:
            self.sim_finished = True
            self.rm.log_final_classification()
            self.cached_classification = self.get_live_classification()

        self.render()
        pygame.display.flip()
        fpsClock.tick(FPS)

        return self.s_Mode, self.screen