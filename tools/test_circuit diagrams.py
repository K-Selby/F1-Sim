import json
from pathlib import Path

import pygame


# -------------------------
# config
# -------------------------

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
FPS = 60

JSON_DIR = Path("data/circuit_json")
BACKGROUND = (20, 20, 24)
PANEL = (32, 32, 40)
WHITE = (245, 245, 245)
GREY = (170, 170, 180)
RED = (220, 60, 60)
GREEN = (80, 200, 120)


# -------------------------
# helpers
# -------------------------

def load_circuit_files():
    if not JSON_DIR.exists():
        print(f"[ERROR] JSON folder not found: {JSON_DIR.resolve()}")
        return []

    files = sorted(
        [p for p in JSON_DIR.glob("*.json") if p.name != "_index.json"],
        key=lambda p: p.stem.lower()
    )

    print(f"[DEBUG] Found {len(files)} circuit json files")
    for f in files:
        print(f"  - {f.name}")

    return files


def load_circuit_data(json_path: Path):
    print(f"[DEBUG] Loading file: {json_path.name}")

    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    points = data.get("track_points", [])
    print(f"[DEBUG] Circuit: {data.get('circuit_name', 'Unknown')}")
    print(f"[DEBUG] Point count: {len(points)}")

    return data


def scale_points_to_panel(track_points, panel_rect, padding=40):
    if not track_points:
        return []

    xs = [p["x"] for p in track_points]
    ys = [p["y"] for p in track_points]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    track_width = max(max_x - min_x, 1e-9)
    track_height = max(max_y - min_y, 1e-9)

    usable_width = panel_rect.width - (padding * 2)
    usable_height = panel_rect.height - (padding * 2)

    scale = min(usable_width / track_width, usable_height / track_height)

    offset_x = panel_rect.left + (panel_rect.width / 2)
    offset_y = panel_rect.top + (panel_rect.height / 2)

    centre_x = (min_x + max_x) / 2
    centre_y = (min_y + max_y) / 2

    scaled = []
    for point in track_points:
        x = (point["x"] - centre_x) * scale + offset_x
        y = (point["y"] - centre_y) * scale + offset_y

        # pygame y-axis goes downward, so flip it
        y = offset_y - ((point["y"] - centre_y) * scale)

        scaled.append((x, y))

    return scaled


def draw_info(screen, font, small_font, data, file_index, total_files):
    title = data.get("circuit_name", "Unknown Circuit")
    official_name = data.get("official_event_name", "Unknown Event")
    year_source = data.get("year_source", "Unknown")
    rotation = data.get("rotation_applied_deg", 0.0)
    point_count = data.get("point_count", 0)

    title_surface = font.render(title, True, WHITE)
    screen.blit(title_surface, (30, 20))

    info_lines = [
        f"Official name: {official_name}",
        f"Year source: {year_source}",
        f"Rotation applied: {rotation}°",
        f"Point count: {point_count}",
        f"File: {file_index + 1}/{total_files}",
        "Controls: Left/Right = change circuit | R = reload | ESC = quit"
    ]

    y = 70
    for line in info_lines:
        surf = small_font.render(line, True, GREY)
        screen.blit(surf, (30, y))
        y += 28


def draw_track(screen, scaled_points):
    if len(scaled_points) < 2:
        return

    # main line
    pygame.draw.lines(screen, WHITE, True, scaled_points, 4)

    # start point marker
    start_x, start_y = scaled_points[0]
    pygame.draw.circle(screen, RED, (int(start_x), int(start_y)), 7)

    # direction hint using second point
    if len(scaled_points) > 1:
        second_x, second_y = scaled_points[1]
        pygame.draw.circle(screen, GREEN, (int(second_x), int(second_y)), 5)


# -------------------------
# main
# -------------------------

def main():
    print("[DEBUG] Starting circuit viewer")

    files = load_circuit_files()
    if not files:
        print("[ERROR] No circuit json files found")
        return

    pygame.init()
    pygame.display.set_caption("Circuit JSON Viewer")
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    clock = pygame.time.Clock()

    title_font = pygame.font.SysFont(None, 42)
    info_font = pygame.font.SysFont(None, 30)

    panel_rect = pygame.Rect(260, 120, 1080, 720)

    current_index = 0
    current_data = load_circuit_data(files[current_index])

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_RIGHT:
                    current_index = (current_index + 1) % len(files)
                    current_data = load_circuit_data(files[current_index])

                elif event.key == pygame.K_LEFT:
                    current_index = (current_index - 1) % len(files)
                    current_data = load_circuit_data(files[current_index])

                elif event.key == pygame.K_r:
                    current_data = load_circuit_data(files[current_index])

        screen.fill(BACKGROUND)
        pygame.draw.rect(screen, PANEL, panel_rect, border_radius=18)

        draw_info(screen, title_font, info_font, current_data, current_index, len(files))

        track_points = current_data.get("track_points", [])
        scaled_points = scale_points_to_panel(track_points, panel_rect)
        draw_track(screen, scaled_points)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    print("[DEBUG] Viewer closed")


if __name__ == "__main__":
    main()