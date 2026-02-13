# screens/simulation.py

from API.imports import *

class Siumulation:
    def __init__(self, s_Mode, screen):
        self.s_Mode = s_Mode
        self.screen = screen
        self.screen_x, self.screen_y = screen.get_size()
        self.title_text = "GP name"
        self.dots = []
        self.dot_spacing = 40
        self.influence_radius = 150
        self.create_dots()


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
        
    # Update Loop
    def update(self):
        mouse_pos = pygame.mouse.get_pos()
        
        # Recalculate card layout when resizing
        new_w, new_h = self.screen.get_size()
        if new_w != self.screen_x or new_h != self.screen_y:
            self.screen_x, self.screen_y = new_w, new_h


        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.s_Mode = "Quit"
        
        self.render()
        pygame.display.flip()
        fpsClock.tick(FPS)

        return self.s_Mode, self.screen