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
        self.timing_update_interval = 1.0
        self.last_timing_update = 0.0
        self.cached_classification = []
        self.sim_finished = False
        self.speed_presets = [1.0, 2.0, 10.0]
        self.sim_speed = 1.0
        self.custom_speed_input_active = False
        self.custom_speed_input = ""
        self.speed_buttons = []
        self.position_history = {}
        self.last_position_history_lap = 0
        self.team_colours = {
            "Red Bull Racing": (30, 65, 255),
            "Ferrari": (220, 0, 0),
            "Mercedes": (0, 210, 190),
            "McLaren": (255, 135, 0),
            "Aston Martin": (0, 110, 70),
            "Alpine": (255, 105, 180),
            "Williams": (0, 90, 255),
            "RB": (70, 90, 255),
            "Kick Sauber": (0, 180, 70),
            "Haas F1 Team": (180, 180, 180),
        }
        self.create_dots()
        self.create_speed_buttons()
        self.rm = main(filepath)
        self.rm.write_to_log("Simulation started.")
        self.rm.broadcast_public_signals()
        for team in self.rm.teams:
            team.decide()
        
        self.gp_title = self.rm.grandprix
        self.circuit_subtitle = f"{self.rm.circuit_name} -- {self.rm.season}"
        self.lap_text = f"Lap {self.rm.lap_number + 1}/{self.rm.total_laps}"
        self.cached_classification = self.get_live_classification()
        self.initialise_position_history()

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
        title_font = pygame.font.Font(font_name, int(self.screen_y / 40))
        header_font = pygame.font.Font(font_name, int(self.screen_y / 55))
        row_font = pygame.font.Font(font_name, int(self.screen_y / 62))

        tower_width = self.screen_x / 7
        tower_height = self.screen_y / 1.225
        tower_x = self.screen_x / 13
        tower_y = self.screen_y / 1.775
        
        r, g, b, = box_colour_2

        # Background
        tower_surface = pygame.Surface((tower_width, tower_height), pygame.SRCALPHA)
        pygame.draw.rect(tower_surface, (r, g, b, 210), tower_surface.get_rect(), border_radius=18)
        tower_rect = tower_surface.get_rect(center=(tower_x, tower_y))
        self.screen.blit(tower_surface, tower_rect)

        # Title
        title_surface = title_font.render("Live Timing", True, white)
        title_surface_2 = title_font.render("Tower", True, white)
        title_rect = title_surface.get_rect(center=(tower_x, tower_height / 4.6))
        title_rect_2 = title_surface_2.get_rect(center=(tower_x, tower_height / 4.6 + int(self.screen_y/40)))
        self.screen.blit(title_surface, title_rect)
        self.screen.blit(title_surface_2, title_rect_2)

        # Headers
        header_y = tower_height / 3.55
        pos_x = tower_x - tower_width / 2.75
        drv_x = tower_x - tower_width / 20
        gap_x = tower_x + tower_width / 3
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
        row_height = tower_height / 23

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
            
            pos_surface_rect = pos_surface.get_rect(center=(tower_x - tower_width / 2.75, row_y))
            driver_surface_rect = driver_surface.get_rect(center=(tower_x - tower_width / 20, row_y))
            gap_surface_rect = gap_surface.get_rect(center=(tower_x + tower_width / 3, row_y))

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

    def initialise_position_history(self):
        self.position_history.clear()

        for car in self.rm.cars:
            self.position_history[car.car_id] = []

        self.last_position_history_lap = 0

        # Save initial starting order as lap 0
        starting_order = sorted(self.rm.cars, key=lambda car: self.rm.get_progress(car), reverse=True)

        for position, car in enumerate(starting_order, start=1):
            self.position_history[car.car_id].append((1.0, position))
        
    def update_position_history(self):
        latest_logged_lap = self.rm.last_logged_completed_lap

        while self.last_position_history_lap < latest_logged_lap:
            lap_to_store = self.last_position_history_lap + 1
            lap_rows = []

            for car in self.rm.cars:
                lap_record = self.rm.get_lap_record(car, lap_to_store)
                if lap_record is not None:
                    lap_rows.append({
                        "car": car,
                        "total_time": lap_record["total_time"]
                    })

            lap_rows.sort(key=lambda row: row["total_time"])

            for position, row in enumerate(lap_rows, start=1):
                car = row["car"]
                self.position_history[car.car_id].append((float(lap_to_store), position))

            self.last_position_history_lap = lap_to_store
           
    def draw_position_graph(self):
        graph_width = self.screen_x / 2
        graph_height = self.screen_y / 2
        graph_x = self.screen_x / 1.35
        graph_y = self.screen_y / 1.5

        title_font = pygame.font.Font(font_name, int(self.screen_y / 35))
        axis_font = pygame.font.Font(font_name, int(self.screen_y / 58))
        label_font = pygame.font.Font(font_name, int(self.screen_y / 70))

        r, g, b = box_colour_2

        graph_surface = pygame.Surface((graph_width, graph_height), pygame.SRCALPHA)
        pygame.draw.rect(graph_surface, (r, g, b, 210), graph_surface.get_rect(), border_radius=18)
        graph_rect = graph_surface.get_rect(center=(graph_x, graph_y))
        self.screen.blit(graph_surface, graph_rect)

        title_surface = title_font.render("Position Graph", True, white)
        title_rect = title_surface.get_rect(center=(graph_x, (graph_y + graph_height / 2) / 2.05))
        self.screen.blit(title_surface, title_rect)

        padding_left = graph_width * 0.05
        padding_right = graph_width * 0.025
        padding_top = graph_height * 0.125
        padding_bottom = graph_height * 0.0575

        plot_left = graph_x - graph_width / 2 + padding_left
        plot_right = graph_x + graph_width / 2 - padding_right
        plot_top = graph_y - graph_height / 2 + padding_top
        plot_bottom = graph_y + graph_height / 2 - padding_bottom

        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top

        # axes
        pygame.draw.line(self.screen, white, (plot_left, plot_top), (plot_left, plot_bottom), 2)
        pygame.draw.line(self.screen, white, (plot_left, plot_bottom), (plot_right, plot_bottom), 2)

        min_lap = 1
        max_lap = max(min_lap, self.rm.total_laps)

        # y-axis labels
        display_slots = len(self.rm.cars) + 1

        for pos in range(1, len(self.rm.cars) + 1):
            y = plot_top + ((pos - 1) / (display_slots - 1)) * plot_height

            pygame.draw.line(self.screen, grey_2, (plot_left, y), (plot_right, y), 1)

            label_surface = axis_font.render(str(pos), True, grey)
            label_rect = label_surface.get_rect(midright=(plot_left - 8, y))
            self.screen.blit(label_surface, label_rect)

        # x-axis labels
        lap_step = 5
        for lap in range(min_lap, max_lap + 1, lap_step):
            x = plot_left + ((lap - min_lap) / max(1, (max_lap - min_lap))) * plot_width

            pygame.draw.line(self.screen, grey_2, (x, plot_top), (x, plot_bottom), 1)

            label_surface = axis_font.render(str(lap), True, grey)
            label_rect = label_surface.get_rect(midtop=(x, plot_bottom + 6))
            self.screen.blit(label_surface, label_rect)

        # plot driver lines / points
        for car in self.rm.cars:
            colour = self.team_colours.get(car.team_id, white)
            history = self.position_history.get(car.car_id, [])

            if len(history) == 0:
                continue

            points = []
            for lap_x, pos in history:
                if lap_x < min_lap:
                    continue

                x = plot_left + ((lap_x - min_lap) / max(1, (max_lap - min_lap))) * plot_width
                y = plot_top + ((pos - 1) / (display_slots - 1)) * plot_height
                points.append((x, y))

            if len(points) == 0:
                continue

            if len(points) >= 2:
                pygame.draw.lines(self.screen, colour, False, points, 2)

            pygame.draw.circle(self.screen, colour, (int(points[-1][0]), int(points[-1][1])), 3)

            label_surface = label_font.render(car.car_id, True, colour)
            label_rect = label_surface.get_rect(midleft=(points[-1][0] + 6, points[-1][1]))
            self.screen.blit(label_surface, label_rect)

    def render(self):
        self.screen.fill(background_colour)
        self.update_dots()
        self.draw_title_bar()
        self.draw_timing_tower()
        self.draw_speed_controls()
        self.draw_position_graph()

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
            self.update_position_history()

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