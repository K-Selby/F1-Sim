from src.UI.API.imports import *
from src.RaceSimulator import main


class Simulation:
    def __init__(self, s_Mode, screen, filepath):
        # ===== CORE STATE =====
        self.s_Mode = s_Mode
        self.screen = screen
        self.screen_x, self.screen_y = screen.get_size()
        # ===== BACKGROUND =====
        self.dots = []
        self.dot_spacing = 40
        self.influence_radius = 150
        # ===== TOP BUTTONS =====
        self.return_text = "Return to Home"
        self.start_text = "Start Race"
        self.return_image = pygame.image.load("data/UI/Images/return.png")
        self.start_image = pygame.image.load("data/UI/Images/play_circle.png")
        self.race_started = False
        self.button = []
        # ===== TIMING / SIMULATION =====
        self.timing_update_interval = 1.0
        self.last_timing_update = 0.0
        self.cached_classification = []
        self.sim_finished = False
        # ===== SPEED CONTROLS =====
        self.sim_speed = 1.0
        self.custom_speed_input_active = False
        self.custom_speed_input = ""
        self.speed_buttons = []
        self.rewind_image = pygame.image.load("data/UI/Images/fast_rewind.png")
        self.forward_image = pygame.image.load("data/UI/Images/fast_forward.png")
        # ===== GRAPH DATA =====
        self.position_history = {}
        self.last_position_history_lap = 0
        self.graph_tabs = ["Driver Position", "Tyre Stints", "Lap Time", "Circuit Map"]
        self.active_graph_tab = "Driver Position"
        self.graph_tab_buttons = []
        self.tyre_graph_order = []
        # ===== EVENT BOX =====
        self.event_messages = []
        self.max_event_messages = 25
        self.fastest_lap_time = None
        self.fastest_lap_driver = None
        self.previous_pending_pit = {}
        self.previous_in_pit_lane = {}
        self.previous_retired = {}
        self.previous_finished = {}
        self.pit_entry_times = {}
        self.pit_exit_reported = set()
        self.winner_announced = False
        self.announced_finishers = set()
        self.final_lap_announced = False
        # ===== CIRCUIT MAP =====
        self.circuit_points = []
        self.circuit_lengths = []
        self.circuit_total_length = 0.0
        # ===== UI SETUP =====
        self.create_graph_tab_buttons()
        self.create_dots()
        self.create_speed_buttons()
        self.create_buttons()
        # ===== SIMULATOR SETUP =====
        self.rm = main(filepath)
        self.rm.write_to_log("Simulation started.")
        self.rm.broadcast_public_signals()
        self.load_circuit_points()
        self.build_circuit_lengths()
        for team in self.rm.teams:
            team.decide()
        # ===== DISPLAY TEXT =====
        self.gp_title = self.rm.grandprix
        self.circuit_subtitle = f"{self.rm.circuit_name} -- {self.rm.season}"
        # ===== INITIAL CACHED DATA =====
        self.cached_classification = self.get_live_classification()
        self.initialise_position_history()
        self.initialise_event_state()
        self.tyre_graph_order = [car.car_id for car in sorted(self.rm.cars, key=lambda car: self.rm.get_progress(car), reverse=True)]
        
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

    # ===== TITLE BAR =====
    def draw_title_bar(self):
        title_bar_height = self.screen_y / 8.5
        title_bar_width = self.screen_x / 1.25
        title_font = pygame.font.Font(font_name, int(self.screen_y / 18))
        subtitle_font = pygame.font.Font(font_name, int(self.screen_y / 48))
        lap_font = pygame.font.Font(font_name, int(self.screen_y / 42))

        r, g, b = red

        # Background bar
        bar_surface = pygame.Surface((title_bar_width, title_bar_height), pygame.SRCALPHA)
        pygame.draw.rect(bar_surface, (r, g, b, 220), bar_surface.get_rect(), border_radius=18)
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

    # ===== BUTTONS =====
    def create_buttons(self):
        self.button.clear()

        button_width = self.screen_x / 3.5
        button_height = self.screen_y / 16
        start_x = self.screen_x / 2 - button_width / 2
        y = self.screen_y / 7

        base_rect = pygame.Rect(start_x, y, button_width, button_height)

        # Start Race button
        self.button.append({
            "base_rect": base_rect.copy(),
            "rect": base_rect.copy(),
            "title": self.start_text,
            "hover": False,
            "colour": box_colour_2,
            "hover_colour": box_hover_2,
            "scale": 1.0,
            "image": self.start_image,
            "mode": "StartRace"
        })

        # Return to Home button
        self.button.append({
            "base_rect": base_rect.copy(),
            "rect": base_rect.copy(),
            "title": self.return_text,
            "hover": False,
            "colour": box_colour_2,
            "hover_colour": box_hover_2,
            "scale": 1.0,
            "image": self.return_image,
            "mode": "Home"
        })

    def update_top_buttons(self, mouse_pos):
        for button in self.button:
            button["hover"] = button["rect"].collidepoint(mouse_pos)

            if button["hover"]:
                target_scale = 1.05
                
            else:
                target_scale = 1.0

            button["scale"] += (target_scale - button["scale"]) * 0.1

            base = button["base_rect"]
            new_width = base.width * button["scale"]
            new_height = base.height * button["scale"]

            button["rect"] = pygame.Rect(
                base.centerx - new_width / 2,
                base.centery - new_height / 2,
                new_width,
                new_height
            )

    def draw_top_button(self):
        active_button = None

        if not self.race_started:
            active_button = self.button[0]   # Start Race
            
        elif self.sim_finished:
            active_button = self.button[1]   # Return to Home

        if active_button is None:
            return

        button_font = pygame.font.Font(font_name, int(self.screen_y / 22.14))
        button = active_button

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

        button_image = pygame.transform.scale(button["image"], (int(self.screen_x / 28.5), int(self.screen_y / 18.45)))
        button_image_pos = button_image.get_rect(midleft=(button["rect"].left + int(self.screen_x / 342), button["rect"].top + int(self.screen_y / 36.9)))

        self.screen.blit(button_text, text_pos)
        self.screen.blit(button_image, button_image_pos)

    # ===== SPEED CONTROLS =====
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
            "image": self.rewind_image,
            "hover": False
        })

        self.speed_buttons.append({
            "name": "speed",
            "rect": speed_rect,
            "hover": False
        })

        self.speed_buttons.append({
            "name": "fast",
            "rect": fast_rect,
            "image": self.forward_image,
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
                text_rect = text_surface.get_rect(center=rect.center)
                self.screen.blit(text_surface, text_rect)

            else:
                image = button["image"]

                image_max_width = rect.width * 0.75
                image_max_height = rect.height * 0.75

                original_width, original_height = image.get_size()
                scale = min(image_max_width / original_width, image_max_height / original_height)

                scaled_width = int(original_width * scale)
                scaled_height = int(original_height * scale)

                scaled_image = pygame.transform.smoothscale(image, (scaled_width, scaled_height))
                image_rect = scaled_image.get_rect(center=rect.center)
                self.screen.blit(scaled_image, image_rect)

    # ===== TIMING TOWER =====
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

        # Finished cars
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

        # Running cars
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

        # Pit cars
        for car in pit_cars:
            classification.append({
                "position": len(classification) + 1,
                "driver": car.car_id,
                "team": car.team_id,
                "gap_ahead": "IN PIT",
                "status": "pit"
            })

        # DNF cars
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
        tower_y = self.screen_y / 1.8

        r, g, b = box_colour_2

        # Background
        tower_surface = pygame.Surface((tower_width, tower_height), pygame.SRCALPHA)
        pygame.draw.rect(tower_surface, (r, g, b, 210), tower_surface.get_rect(), border_radius=18)
        tower_rect = tower_surface.get_rect(center=(tower_x, tower_y))
        self.screen.blit(tower_surface, tower_rect)

        # Title
        title_surface = title_font.render("Live Timing", True, white)
        title_surface_2 = title_font.render("Tower", True, white)
        title_rect = title_surface.get_rect(center=(tower_x, (tower_y + tower_height / 2) / 5.8))
        title_rect_2 = title_surface_2.get_rect(center=(tower_x, (tower_y + tower_height / 2) / 5.8 + int(self.screen_y / 40)))
        
        self.screen.blit(title_surface, title_rect)
        self.screen.blit(title_surface_2, title_rect_2)

        # Headers
        header_y = (tower_y + tower_height / 2) / 4.25
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

        row_start_y = (tower_y + tower_height / 2) / 3.8
        row_height = tower_height / 23

        for index, entry in enumerate(classification):
            row_y = row_start_y + (index * row_height)

            if row_y > tower_y + tower_height - row_height:
                break

            r, g, b = red_2
            pygame.draw.line(self.screen, (r, g, b, 5),( tower_x - tower_width / 2, row_y + row_height / 2), (tower_x + tower_width / 2, row_y + row_height / 2), 1)

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

    # ===== EVENT BOX =====
    def initialise_event_state(self):
        # Store previous car state so event changes can be detected
        for car in self.rm.cars:
            self.previous_pending_pit[car.car_id] = car.pending_pit
            self.previous_in_pit_lane[car.car_id] = car.in_pit_lane
            self.previous_retired[car.car_id] = car.retired
            self.previous_finished[car.car_id] = (car.lap_count >= self.rm.total_laps)

    def add_event_message(self, text):
        # Keep only the newest event messages
        self.event_messages.append(text)
        self.event_messages = self.event_messages[-self.max_event_messages:]

    def wrap_event_text(self, text, font, max_width):
        words = text.split()
        if not words:
            return [""]

        lines = []
        current_line = words[0]

        for word in words[1:]:
            test_line = current_line + " " + word
            if font.size(test_line)[0] <= max_width:
                current_line = test_line
                
            else:
                lines.append(current_line)
                current_line = word

        lines.append(current_line)
        return lines

    def format_lap_time(self, seconds):
        # Format a single lap time
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)

        if minutes > 0:
            return f"{minutes}:{secs:02d}.{millis:03d}"
        
        return f"{secs}.{millis:03d}"

    def format_race_time(self, seconds):
        # Format a full race time
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:06.3f}"
        
        return f"{minutes}:{secs:06.3f}"

    def update_fastest_lap_events(self):
        # Detect fastest lap changes
        for car in self.rm.cars:
            if not car.completed_laps:
                continue

            latest_lap = car.completed_laps[-1]
            lap_time = latest_lap["lap_time"]
            lap_number = latest_lap["lap"]

            if self.fastest_lap_time is None or lap_time < self.fastest_lap_time:
                if (self.fastest_lap_time is None or car.car_id != self.fastest_lap_driver or abs(lap_time - self.fastest_lap_time) > 0.001):
                    self.fastest_lap_time = lap_time
                    self.fastest_lap_driver = car.car_id
                    formatted_lap_time = self.format_lap_time(lap_time)
                    self.add_event_message(f"FASTEST LAP: {car.car_id} set a {formatted_lap_time} on Lap {lap_number}")

    def update_race_event_messages(self):
        # Update fastest lap event
        self.update_fastest_lap_events()

        # Announce final lap once
        if not self.final_lap_announced and self.rm.lap_number >= self.rm.total_laps:
            self.add_event_message("FINAL LAP")
            self.final_lap_announced = True

        newly_finished = []

        for car in self.rm.cars:
            car_id = car.car_id

            previous_pending = self.previous_pending_pit.get(car_id, False)
            previous_in_pit = self.previous_in_pit_lane.get(car_id, False)
            previous_retired = self.previous_retired.get(car_id, False)
            previous_finished = self.previous_finished.get(car_id, False)

            current_finished = (car.lap_count >= self.rm.total_laps)

            # Detect new pit call
            if not previous_pending and car.pending_pit:
                compound_text = car.pit_compound if car.pit_compound is not None else "UNKNOWN"
                self.add_event_message(f"PIT CALL: {car_id} instructed to pit for {compound_text}")

            # Detect pit entry
            if not previous_in_pit and car.in_pit_lane:
                self.pit_entry_times[car_id] = self.rm.sim_time
                self.pit_exit_reported.discard(car_id)
                self.add_event_message(f"PIT ENTRY: {car_id} has entered the pits")

            # Detect pit exit
            if previous_in_pit and not car.in_pit_lane and car_id not in self.pit_exit_reported:
                pit_entry_time = self.pit_entry_times.get(car_id)
                total_pit_time = None

                if pit_entry_time is not None:
                    total_pit_time = self.rm.sim_time - pit_entry_time
                    car.last_pit_total_time_s = total_pit_time

                stationary_time = car.last_pit_service_time_s

                if total_pit_time is not None:
                    self.add_event_message(f"PIT EXIT: {car_id} exited pits | stop {stationary_time:.2f}s | lane time {total_pit_time:.2f}s")
                    
                else:
                    self.add_event_message(f"PIT EXIT: {car_id} exited pits | stop {stationary_time:.2f}s")

                self.pit_exit_reported.add(car_id)
                self.pit_entry_times.pop(car_id, None)

            # Detect retirement
            if not previous_retired and car.retired:
                self.add_event_message(f"DNF: {car_id} is out of the race")

            # Collect newly finished cars
            if not previous_finished and current_finished and not car.retired:
                newly_finished.append(car)

            self.previous_pending_pit[car_id] = car.pending_pit
            self.previous_in_pit_lane[car_id] = car.in_pit_lane
            self.previous_retired[car_id] = car.retired
            self.previous_finished[car_id] = current_finished

        # Announce finishers in classification order
        if newly_finished:
            finished_cars = sorted([c for c in self.rm.cars if c.lap_count >= self.rm.total_laps and not c.retired], key=lambda c: c.total_time)

            for car in sorted(newly_finished, key=lambda c: c.total_time):
                if car.car_id in self.announced_finishers:
                    continue

                finish_position = finished_cars.index(car) + 1
                formatted_time = self.format_race_time(car.total_time)

                if finish_position == 1 and not self.winner_announced:
                    self.add_event_message(f"WINNER: P1 {car.car_id} wins the {self.rm.grandprix} in {formatted_time}")
                    self.winner_announced = True
                    
                else:
                    leader_time = finished_cars[0].total_time
                    gap_to_winner = car.total_time - leader_time
                    formatted_gap = f"+{gap_to_winner:.3f}s"
                    self.add_event_message(f"FLAG: P{finish_position} {car.car_id} finished in {formatted_time} ({formatted_gap})")

                self.announced_finishers.add(car.car_id)

    def draw_event_box(self):
        box_width = self.screen_x / 4.25
        box_height = self.screen_y / 1.225
        box_x = self.screen_x / 1.14
        box_y = self.screen_y / 1.8

        title_font = pygame.font.Font(font_name, int(self.screen_y / 40))
        row_font = pygame.font.Font(font_name, int(self.screen_y / 80))

        r, g, b = box_colour_2

        # Background
        box_surface = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
        pygame.draw.rect(box_surface, (r, g, b, 210), box_surface.get_rect(), border_radius=18)
        box_rect = box_surface.get_rect(center=(box_x, box_y))
        self.screen.blit(box_surface, box_rect)

        # Title
        title_surface = title_font.render("Race Events", True, white)
        title_rect = title_surface.get_rect(center=(box_x, box_y - box_height / 2 + box_height / 25))
        self.screen.blit(title_surface, title_rect)

        padding_x = box_width * 0.05
        padding_bottom = box_height * 0.02
        content_top = box_y - box_height / 2 + box_height * 0.08
        content_bottom = box_y + box_height / 2 - padding_bottom
        text_left = box_x - box_width / 2 + padding_x
        text_right = box_x + box_width / 2 - padding_x
        max_text_width = text_right - text_left

        line_height = row_font.get_height() + 2
        message_gap = 8
        current_y = content_bottom

        # Draw newest messages at the bottom
        for message in reversed(self.event_messages):
            wrapped_lines = self.wrap_event_text(message, row_font, max_text_width)

            message_height = len(wrapped_lines) * line_height
            separator_y = current_y - message_height - 4

            if separator_y < content_top:
                break

            pygame.draw.line(self.screen, grey_2, (text_left, separator_y), (text_right, separator_y), 1)

            line_y = separator_y + 6
            for wrapped_line in wrapped_lines:
                message_surface = row_font.render(wrapped_line, True, red_2)
                message_rect = message_surface.get_rect(topleft=(text_left, line_y))
                self.screen.blit(message_surface, message_rect)
                line_y += line_height

            current_y = separator_y - message_gap

    # ===== TABBED WINDOW DISPLAY =====
    def create_graph_tab_buttons(self):
        graph_width = self.screen_x / 1.8
        graph_height = self.screen_y / 1.5
        graph_x = self.screen_x / 2.2
        graph_y = self.screen_y / 1.8

        tab_height = self.screen_y / 20
        tab_y = graph_y - tab_height / 2 - graph_height / 2.25

        total_width = graph_width - graph_width / 20
        gap = 4
        tab_width = (total_width - (gap * (len(self.graph_tabs) - 1))) / len(self.graph_tabs)
        start_x = graph_x - total_width / 2

        self.graph_tab_buttons.clear()

        for index, tab_name in enumerate(self.graph_tabs):
            x = start_x + index * (tab_width + gap)
            rect = pygame.Rect(x, tab_y, tab_width, tab_height)

            self.graph_tab_buttons.append({
                "name": tab_name,
                "rect": rect,
                "hover": False
            })

    def get_shared_graph_area(self):
        # Shared graph panel size and position
        graph_width = self.screen_x / 1.8
        graph_height = self.screen_y / 1.5
        graph_x = self.screen_x / 2.2
        graph_y = self.screen_y / 1.8

        return graph_x, graph_y, graph_width, graph_height

    def draw_graph_tabs(self):
        tab_font = pygame.font.Font(font_name, int(self.screen_y / 62))

        for button in self.graph_tab_buttons:
            rect = button["rect"]

            if button["name"] == self.active_graph_tab:
                colour = red_2
                
            elif button["hover"]:
                colour = box_hover_2
                
            else:
                colour = box_colour_2

            pygame.draw.rect(self.screen, colour, rect, border_radius=10)
            pygame.draw.rect(self.screen, white, rect, 2, border_radius=10)

            text_surface = tab_font.render(button["name"], True, white)
            text_rect = text_surface.get_rect(center=rect.center)
            self.screen.blit(text_surface, text_rect)

    def draw_active_graph_panel(self):
        if self.active_graph_tab == "Driver Position":
            self.draw_position_graph()
            
        elif self.active_graph_tab == "Tyre Stints":
            self.draw_tyre_stint_graph()
            
        elif self.active_graph_tab == "Lap Time":
            self.draw_lap_time_graph()
            
        elif self.active_graph_tab == "Circuit Map":
            self.draw_circuit_map_graph()

    # ===== POSITION LINE GRAPH =====
    def initialise_position_history(self):
        self.position_history.clear()

        for car in self.rm.cars:
            self.position_history[car.car_id] = []

        self.last_position_history_lap = 0

        # Save initial starting order
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
        graph_x, graph_y, graph_width, graph_height = self.get_shared_graph_area()

        axis_font = pygame.font.Font(font_name, int(self.screen_y / 58))
        label_font = pygame.font.Font(font_name, int(self.screen_y / 70))

        r, g, b = box_colour_2

        # Draw panel background
        graph_surface = pygame.Surface((graph_width, graph_height), pygame.SRCALPHA)
        pygame.draw.rect(graph_surface, (r, g, b, 210), graph_surface.get_rect(), border_radius=18)
        graph_rect = graph_surface.get_rect(center=(graph_x, graph_y))
        self.screen.blit(graph_surface, graph_rect)

        # Define plot area
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

        # Draw axes
        pygame.draw.line(self.screen, white, (plot_left, plot_top), (plot_left, plot_bottom), 2)
        pygame.draw.line(self.screen, white, (plot_left, plot_bottom), (plot_right, plot_bottom), 2)

        min_lap = 1
        max_lap = max(min_lap, self.rm.total_laps)

        # Draw y-axis labels
        display_slots = len(self.rm.cars) + 1

        for pos in range(1, len(self.rm.cars) + 1):
            y = plot_top + ((pos - 1) / (display_slots - 1)) * plot_height

            pygame.draw.line(self.screen, grey_2, (plot_left, y), (plot_right, y), 1)

            label_surface = axis_font.render(str(pos), True, grey)
            label_rect = label_surface.get_rect(midright=(plot_left - 8, y))
            self.screen.blit(label_surface, label_rect)

        # Draw x-axis labels
        lap_step = 5
        for lap in range(min_lap, max_lap + 1, lap_step):
            x = plot_left + ((lap - min_lap) / max(1, (max_lap - min_lap))) * plot_width

            pygame.draw.line(self.screen, grey_2, (x, plot_top), (x, plot_bottom), 1)

            label_surface = axis_font.render(str(lap), True, grey)
            label_rect = label_surface.get_rect(midtop=(x, plot_bottom + 6))
            self.screen.blit(label_surface, label_rect)

        # Plot driver lines
        for car in self.rm.cars:
            colour = team_colours.get(car.team_id, white)
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

    # ===== TYRE STINT GRAPH =====
    def get_compound_colour(self, compound):
        compound_upper = str(compound).upper()

        if compound_upper == str(self.rm.compound_map["SOFT"]).upper():
            return red_3
        
        elif compound_upper == str(self.rm.compound_map["MEDIUM"]).upper():
            return yellow
        
        elif compound_upper == str(self.rm.compound_map["HARD"]).upper():
            return white

        return grey

    def build_tyre_stint_data(self, car):
        stints = []

        if not car.completed_laps:
            stints.append({
                "compound": car.tyre_state.compound,
                "start_lap": 1,
                "end_lap": 1,
                "length": 1
            })
            return stints

        current_compound = car.completed_laps[0]["compound"]
        current_stint_id = car.completed_laps[0].get("stint_id", 1)
        stint_start_lap = 1

        for lap_record in car.completed_laps[1:]:
            lap_number = lap_record["lap"]
            lap_compound = lap_record["compound"]
            lap_stint_id = lap_record.get("stint_id", current_stint_id)

            compound_changed = str(lap_compound).upper() != str(current_compound).upper()
            stint_changed = lap_stint_id != current_stint_id

            if compound_changed or stint_changed:
                previous_lap = lap_number - 1

                stints.append({
                    "compound": current_compound,
                    "start_lap": stint_start_lap,
                    "end_lap": previous_lap,
                    "length": previous_lap - stint_start_lap + 1
                })

                current_compound = lap_compound
                current_stint_id = lap_stint_id
                stint_start_lap = lap_number

        current_display_lap = max(1, self.rm.last_logged_completed_lap)

        stints.append({
            "compound": current_compound,
            "start_lap": stint_start_lap,
            "end_lap": current_display_lap,
            "length": current_display_lap - stint_start_lap + 1
        })

        return stints

    def update_tyre_graph_order(self):
        # Keep tyre graph order matched to live classification
        self.tyre_graph_order = [entry["driver"] for entry in self.cached_classification if entry["status"] != "dnf"]
        dnf_drivers = [entry["driver"] for entry in self.cached_classification if entry["status"] == "dnf"]

        self.tyre_graph_order.extend(dnf_drivers)

    def draw_tyre_stint_graph(self):
        graph_x, graph_y, graph_width, graph_height = self.get_shared_graph_area()

        axis_font = pygame.font.Font(font_name, int(self.screen_y / 70))
        row_font = pygame.font.Font(font_name, int(self.screen_y / 78))
        stint_font = pygame.font.Font(font_name, int(self.screen_y / 85))

        r, g, b = box_colour_2

        # Draw panel background
        graph_surface = pygame.Surface((graph_width, graph_height), pygame.SRCALPHA)
        pygame.draw.rect(graph_surface, (r, g, b, 210), graph_surface.get_rect(), border_radius=18)
        graph_rect = graph_surface.get_rect(center=(graph_x, graph_y))
        self.screen.blit(graph_surface, graph_rect)

        # Define plot area
        padding_left = graph_width * 0.065
        padding_right = graph_width * 0.025
        padding_top = graph_height * 0.125
        padding_bottom = graph_height * 0.0575

        plot_left = graph_x - graph_width / 2 + padding_left
        plot_right = graph_x + graph_width / 2 - padding_right
        plot_top = graph_y - graph_height / 2 + padding_top
        plot_bottom = graph_y + graph_height / 2 - padding_bottom

        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top

        pygame.draw.line(self.screen, white, (plot_left, plot_top), (plot_left, plot_bottom), 2)
        pygame.draw.line(self.screen, white, (plot_left, plot_bottom), (plot_right, plot_bottom), 2)

        current_axis_lap = max(1, self.rm.last_logged_completed_lap)

        # Show current lap marker on the right
        x = plot_right
        pygame.draw.line(self.screen, grey_2, (x, plot_top), (x, plot_bottom), 1)

        label_surface = axis_font.render(str(current_axis_lap), True, grey)
        label_rect = label_surface.get_rect(midtop=(x, plot_bottom + 6))
        self.screen.blit(label_surface, label_rect)

        car_lookup = {car.car_id: car for car in self.rm.cars}
        ordered_cars = [car_lookup[car_id] for car_id in self.tyre_graph_order if car_id in car_lookup]

        row_count = len(ordered_cars)
        if row_count == 0:
            return

        row_height = plot_height / row_count
        bar_height = row_height * 0.62

        for index, car in enumerate(ordered_cars):
            row_y = plot_top + (index * row_height) + (row_height / 2)

            pygame.draw.line(self.screen, grey_2, (plot_left, row_y + row_height / 2), (plot_right, row_y + row_height / 2), 1)

            driver_surface = row_font.render(car.car_id, True, grey)
            driver_rect = driver_surface.get_rect(midright=(plot_left - 8, row_y))
            self.screen.blit(driver_surface, driver_rect)

            stints = self.build_tyre_stint_data(car)

            for stint in stints:
                start_lap = stint["start_lap"]
                end_lap = stint["end_lap"]
                stint_length = stint["length"]
                compound = stint["compound"]

                if current_axis_lap == 1:
                    bar_x = plot_left
                    bar_width = plot_width
                    
                else:
                    bar_x = plot_left + ((start_lap - 1) / current_axis_lap) * plot_width
                    bar_end_x = plot_left + (end_lap / current_axis_lap) * plot_width
                    bar_end_x = min(bar_end_x, plot_right)
                    bar_width = max(12, bar_end_x - bar_x)

                bar_rect = pygame.Rect(bar_x, row_y - bar_height / 2, bar_width, bar_height)
                bar_colour = self.get_compound_colour(compound)

                pygame.draw.rect(self.screen, bar_colour, bar_rect, border_radius=5)
                pygame.draw.rect(self.screen, background_colour, bar_rect, 1, border_radius=5)

                stint_text = str(stint_length)
                text_colour = background_colour if bar_colour != white else black
                text_surface = stint_font.render(stint_text, True, text_colour)

                if text_surface.get_width() < bar_rect.width - 4:
                    text_rect = text_surface.get_rect(center=bar_rect.center)
                    self.screen.blit(text_surface, text_rect)

    # ===== LAP TIME GRAPH =====
    def get_lap_axis_step(self, max_lap):
        if max_lap <= 10:
            return 1
        
        elif max_lap <= 20:
            return 2
        
        elif max_lap <= 40:
            return 5
        
        return 10

    def get_lap_time_axis_range(self):
        lap_times = []

        for car in self.rm.cars:
            for lap_record in car.completed_laps:
                lap_times.append(lap_record["lap_time"])

        if not lap_times:
            return 80.0, 90.0

        raw_min = min(lap_times)
        raw_max = max(lap_times)

        padding = 0.5
        axis_min = math.floor((raw_min - padding) / 1.0) * 1.0
        axis_max = math.ceil((raw_max + padding) / 1.0) * 1.0

        return axis_min, axis_max

    def draw_lap_time_graph(self):
        graph_x, graph_y, graph_width, graph_height = self.get_shared_graph_area()

        axis_font = pygame.font.Font(font_name, int(self.screen_y / 58))
        label_font = pygame.font.Font(font_name, int(self.screen_y / 80))

        r, g, b = box_colour_2

        # Draw panel background
        graph_surface = pygame.Surface((graph_width, graph_height), pygame.SRCALPHA)
        pygame.draw.rect(graph_surface, (r, g, b, 210), graph_surface.get_rect(), border_radius=18)
        graph_rect = graph_surface.get_rect(center=(graph_x, graph_y))
        self.screen.blit(graph_surface, graph_rect)

        # Define plot area
        padding_left = graph_width * 0.11
        padding_right = graph_width * 0.025
        padding_top = graph_height * 0.125
        padding_bottom = graph_height * 0.0575

        plot_left = graph_x - graph_width / 2 + padding_left
        plot_right = graph_x + graph_width / 2 - padding_right
        plot_top = graph_y - graph_height / 2 + padding_top
        plot_bottom = graph_y + graph_height / 2 - padding_bottom

        plot_width = plot_right - plot_left
        plot_height = plot_bottom - plot_top

        pygame.draw.line(self.screen, white, (plot_left, plot_top), (plot_left, plot_bottom), 2)
        pygame.draw.line(self.screen, white, (plot_left, plot_bottom), (plot_right, plot_bottom), 2)

        raw_max_lap = self.rm.last_logged_completed_lap
        max_lap = max(1, raw_max_lap - 1)

        y_axis_min, y_axis_max = self.get_lap_time_axis_range()
        y_step = 0.5

        # Draw y-axis labels and grid
        y_value = y_axis_min
        while y_value <= y_axis_max:
            y = plot_bottom - ((y_value - y_axis_min) / max(1.0, (y_axis_max - y_axis_min))) * plot_height

            pygame.draw.line(self.screen, grey_2, (plot_left, y), (plot_right, y), 1)

            label_surface = axis_font.render(self.format_lap_time(y_value), True, grey)
            label_rect = label_surface.get_rect(midright=(plot_left - 8, y))
            self.screen.blit(label_surface, label_rect)

            y_value += y_step

        # Draw x-axis labels and grid
        lap_step = self.get_lap_axis_step(max_lap)

        for lap in range(1, max_lap + 1, lap_step):
            if max_lap == 1:
                x = plot_left
                
            else:
                x = plot_left + ((lap - 1) / max(1, (max_lap - 1))) * plot_width

            pygame.draw.line(self.screen, grey_2, (x, plot_top), (x, plot_bottom), 1)

            label_surface = axis_font.render(str(lap), True, grey)
            label_rect = label_surface.get_rect(midtop=(x, plot_bottom + 6))
            self.screen.blit(label_surface, label_rect)

        # Always show latest lap marker
        if max_lap > 1 and max_lap % lap_step != 0:
            x = plot_right
            pygame.draw.line(self.screen, grey_2, (x, plot_top), (x, plot_bottom), 1)

            label_surface = axis_font.render(str(max_lap), True, grey)
            label_rect = label_surface.get_rect(midtop=(x, plot_bottom + 6))
            self.screen.blit(label_surface, label_rect)

        # Plot driver lap times
        for car in self.rm.cars:
            colour = team_colours.get(car.team_id, white)
            points = []

            for lap_record in car.completed_laps:
                raw_lap_number = lap_record["lap"]
                lap_time = lap_record["lap_time"]

                display_lap_number = raw_lap_number - 1

                if display_lap_number < 1:
                    continue
                
                if display_lap_number > max_lap:
                    continue

                if max_lap == 1:
                    x = plot_left
                    
                else:
                    x = plot_left + ((display_lap_number - 1) / max(1, (max_lap - 1))) * plot_width

                y = plot_bottom - ((lap_time - y_axis_min) / max(1.0, (y_axis_max - y_axis_min))) * plot_height
                points.append((x, y))

            if len(points) >= 2:
                pygame.draw.lines(self.screen, colour, False, points, 2)

            if len(points) >= 1:
                pygame.draw.circle(self.screen, colour, (int(points[-1][0]), int(points[-1][1])), 3)

                label_surface = label_font.render(car.car_id, True, colour)
                label_rect = label_surface.get_rect(midleft=(points[-1][0] + 6, points[-1][1]))
                self.screen.blit(label_surface, label_rect)

    # ===== CIRCUIT DISPLAY =====
    def load_circuit_points(self):
        gp_name = self.rm.grandprix.strip()

        name_map = {
            "Bahrain Grand Prix": "Bahrain",
            "Saudi Arabian Grand Prix": "Jeddah",
            "Australian Grand Prix": "Melbourne",
            "Azerbaijan Grand Prix": "Baku",
            "Miami Grand Prix": "Miami",
            "Emilia Romagna Grand Prix": "Imola",
            "Monaco Grand Prix": "Monaco",
            "Spanish Grand Prix": "Barcelona",
            "Canadian Grand Prix": "Montreal",
            "Austrian Grand Prix": "Austria",
            "British Grand Prix": "Silverstone",
            "Hungarian Grand Prix": "Hungaroring",
            "Belgian Grand Prix": "Spa",
            "Dutch Grand Prix": "Zandvoort",
            "Italian Grand Prix": "Monza",
            "Singapore Grand Prix": "Singapore",
            "Japanese Grand Prix": "Suzuka",
            "Qatar Grand Prix": "Qatar",
            "United States Grand Prix": "COTA",
            "Mexico City Grand Prix": "Mexico",
            "São Paulo Grand Prix": "Interlagos",
            "Las Vegas Grand Prix": "LasVegas",
            "Abu Dhabi Grand Prix": "AbuDhabi",
            "French Grand Prix": "PaulRicard",
            "Portuguese Grand Prix": "Portimao",
            "Turkish Grand Prix": "Istanbul",
            "Russian Grand Prix": "Sochi",
            "Styrian Grand Prix": "Austria",
            "Tuscan Grand Prix": "Mugello",
            "70th Anniversary Grand Prix": "Silverstone",
            "Eifel Grand Prix": "Nurburgring",
        }

        circuit_name = name_map.get(gp_name, gp_name.replace(" Grand Prix", "").replace(" ", ""))
        json_path = Path("data/circuit_json") / f"{circuit_name}.json"

        self.circuit_points = []

        if not json_path.exists():
            print(f"Circuit JSON not found: {json_path}")
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.circuit_points = [(point["x"], point["y"]) for point in data.get("track_points", [])]

        except Exception as e:
            print(f"Failed to load circuit JSON: {e}")
            self.circuit_points = []

    def get_scaled_circuit_points(self):
        if not self.circuit_points:
            return []

        graph_x, graph_y, graph_width, graph_height = self.get_shared_graph_area()

        padding_x = graph_width * 0.08
        padding_y = graph_height * 0.10

        plot_width = graph_width - (padding_x * 2)
        plot_height = graph_height - (padding_y * 2)

        xs = [p[0] for p in self.circuit_points]
        ys = [p[1] for p in self.circuit_points]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        circuit_width = max(max_x - min_x, 0.001)
        circuit_height = max(max_y - min_y, 0.001)

        scale = min(plot_width / circuit_width, plot_height / circuit_height)

        centre_x = (min_x + max_x) / 2
        centre_y = (min_y + max_y) / 2

        scaled_points = []
        for x, y in self.circuit_points:
            draw_x = graph_x + ((x - centre_x) * scale)
            draw_y = graph_y - ((y - centre_y) * scale)
            scaled_points.append((draw_x, draw_y))

        return scaled_points

    def build_circuit_lengths(self):
        self.circuit_lengths = []
        self.circuit_total_length = 0.0

        if len(self.circuit_points) < 2:
            return

        self.circuit_lengths = [0.0]

        for i in range(1, len(self.circuit_points)):
            x1, y1 = self.circuit_points[i - 1]
            x2, y2 = self.circuit_points[i]
            seg_len = math.hypot(x2 - x1, y2 - y1)
            self.circuit_total_length += seg_len
            self.circuit_lengths.append(self.circuit_total_length)

        # Close the loop
        x1, y1 = self.circuit_points[-1]
        x2, y2 = self.circuit_points[0]
        self.circuit_total_length += math.hypot(x2 - x1, y2 - y1)

    def get_car_track_fraction(self, car):
        progress = float(self.rm.get_progress(car))

        # Progress already lap-based
        if progress <= (self.rm.total_laps + 1):
            return progress % 1.0

        # Progress based on track length
        if hasattr(self.rm, "track_length") and self.rm.track_length:
            return (progress % self.rm.track_length) / self.rm.track_length

        # Fallback
        return progress % 1.0

    def get_point_on_circuit(self, fraction, scaled_points):
        if not scaled_points or self.circuit_total_length <= 0:
            return None

        target_length = fraction * self.circuit_total_length

        for i in range(1, len(self.circuit_lengths)):
            if self.circuit_lengths[i] >= target_length:
                prev_len = self.circuit_lengths[i - 1]
                next_len = self.circuit_lengths[i]

                x1, y1 = scaled_points[i - 1]
                x2, y2 = scaled_points[i]

                seg_len = next_len - prev_len
                if seg_len <= 0:
                    return (x1, y1)

                t = (target_length - prev_len) / seg_len
                px = x1 + (x2 - x1) * t
                py = y1 + (y2 - y1) * t
                return (px, py)

        # Closing segment
        prev_len = self.circuit_lengths[-1]
        x1, y1 = scaled_points[-1]
        x2, y2 = scaled_points[0]

        seg_len = self.circuit_total_length - prev_len
        if seg_len <= 0:
            return (x1, y1)

        t = (target_length - prev_len) / seg_len
        px = x1 + (x2 - x1) * t
        py = y1 + (y2 - y1) * t
        return (px, py)

    def draw_circuit_map_graph(self):
        graph_x, graph_y, graph_width, graph_height = self.get_shared_graph_area()
        text_font = pygame.font.Font(font_name, int(self.screen_y / 55))
        car_font = pygame.font.Font(font_name, int(self.screen_y / 60))
        r, g, b = box_colour_2

        # Draw panel background
        graph_surface = pygame.Surface((graph_width, graph_height), pygame.SRCALPHA)
        pygame.draw.rect(graph_surface, (r, g, b, 210), graph_surface.get_rect(), border_radius=18)
        graph_rect = graph_surface.get_rect(center=(graph_x, graph_y))
        self.screen.blit(graph_surface, graph_rect)

        # Show fallback text if no circuit data exists
        if not self.circuit_points:
            info_surface = text_font.render("Circuit data not found", True, grey)
            info_rect = info_surface.get_rect(center=(graph_x, graph_y))
            self.screen.blit(info_surface, info_rect)
            return

        scaled_points = self.get_scaled_circuit_points()

        if len(scaled_points) >= 2:
            # Draw circuit outline
            pygame.draw.lines(self.screen, white, True, scaled_points, 4)

            # Draw start marker
            start_x, start_y = scaled_points[0]
            pygame.draw.circle(self.screen, green, (int(start_x), int(start_y)), 6)

            # Draw cars on track
            for car in self.rm.cars:
                if car.retired:
                    continue

                fraction = self.get_car_track_fraction(car)
                point = self.get_point_on_circuit(fraction, scaled_points)

                if point is None:
                    continue

                px, py = point
                car_colour = team_colours.get(car.team_id, white)

                pygame.draw.circle(self.screen, car_colour, (int(px), int(py)), self.screen_x / 100)
                pygame.draw.circle(self.screen, black, (int(px), int(py)), self.screen_x / 100, 3)

                label_surface = car_font.render(car.car_id, True, red_3)
                label_rect = label_surface.get_rect(midleft=(px + 10, py))
                self.screen.blit(label_surface, label_rect)

    # ===== RENDER =====
    def render(self):
        self.screen.fill(background_colour)
        self.update_dots()
        self.draw_title_bar()
        self.draw_timing_tower()
        self.draw_speed_controls()
        self.draw_active_graph_panel()
        self.draw_graph_tabs()
        self.draw_event_box()
        self.draw_top_button()

    # ===== UPDATE =====
    def update(self):
        mouse_pos = pygame.mouse.get_pos()

        # Resize handling
        new_w, new_h = self.screen.get_size()
        if new_w != self.screen_x or new_h != self.screen_y:
            self.screen_x, self.screen_y = new_w, new_h
            self.create_dots()
            self.create_speed_buttons()
            self.create_graph_tab_buttons()
            self.create_buttons()

        # Hover states
        for button in self.speed_buttons:
            button["hover"] = button["rect"].collidepoint(mouse_pos)

        for button in self.graph_tab_buttons:
            button["hover"] = button["rect"].collidepoint(mouse_pos)

        if not self.race_started or self.sim_finished:
            self.update_top_buttons(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.s_Mode = "Quit"

            if event.type == pygame.MOUSEBUTTONDOWN:
                clicked_speed_button = False

                if not self.race_started:
                    start_button = self.button[0]
                    if start_button["rect"].collidepoint(mouse_pos):
                        self.race_started = True

                elif self.sim_finished:
                    return_button = self.button[1]
                    if return_button["rect"].collidepoint(mouse_pos):
                        self.s_Mode = return_button["mode"]

                # Handle graph tab clicks
                for button in self.graph_tab_buttons:
                    if button["rect"].collidepoint(mouse_pos):
                        self.active_graph_tab = button["name"]
                        break

                # Handle speed control clicks
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

            # Handle typed custom speed input
            if event.type == pygame.KEYDOWN and self.custom_speed_input_active:
                if event.key == pygame.K_RETURN:
                    if self.custom_speed_input != "":
                        try:
                            entered_value = float(self.custom_speed_input)
                            if 0.5 <= entered_value <= 1000:
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

        # Step simulation after race has started
        if self.race_started and not self.sim_finished:
            whole_steps = int(self.sim_speed)
            fractional_step = self.sim_speed - whole_steps

            for _ in range(whole_steps):
                self.rm.step_tick(self.rm.dt)

            if fractional_step > 0:
                self.rm.step_tick(self.rm.dt * fractional_step)

            self.update_position_history()
            self.update_race_event_messages()

            if (self.rm.sim_time - self.last_timing_update) >= self.timing_update_interval:
                self.cached_classification = self.get_live_classification()
                self.update_tyre_graph_order()
                self.last_timing_update = self.rm.sim_time

            # Mark race finished only after final tick
            if self.rm.race_finished:
                self.sim_finished = True
                self.rm.log_final_classification()
                self.cached_classification = self.get_live_classification()
                self.update_race_event_messages()
                self.update_tyre_graph_order()

        self.render()
        pygame.display.flip()
        fpsClock.tick(FPS)

        return self.s_Mode, self.screen