import json

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)

# ----------------------------
# Load configs
# ----------------------------

circuits = load_json("configs/circuits.json")
tyres = load_json("configs/tyres.json")["tyres"]

# ----------------------------
# Select scenario
# ----------------------------

CIRCUIT = "Bahrain Grand Prix"
TYRE = "C3"

circuit = circuits[CIRCUIT]
tyre_model = tyres[TYRE]["coefficients"]

total_laps = circuit["total_laps"]
base_lap_time = circuit["base_lap_time"]

a = tyre_model["quadratic"]
b = tyre_model["linear"]

# ----------------------------
# Simulation
# ----------------------------

lap_times = []

for lap in range(1, total_laps + 1):
    degradation = (a * lap**2) + (b * lap)
    lap_time = base_lap_time + degradation
    lap_times.append(lap_time)

total_race_time = sum(lap_times)

# ----------------------------
# Output
# ----------------------------

print(f"Circuit: {CIRCUIT}")
print(f"Tyre: {TYRE}")
print(f"Total race time: {total_race_time:.2f}s")