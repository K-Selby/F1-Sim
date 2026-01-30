import json

# ----------------------------
# Load configs
# ----------------------------

with open("configs/circuits.json") as f:
    circuits = json.load(f)

with open("configs/tyres.json") as f:
    tyres = json.load(f)["tyres"]

# ----------------------------
# Configuration
# ----------------------------

CIRCUIT = "Bahrain Grand Prix"
START_TYRE = "C3"
END_TYRE = "C2"
PIT_LAP = 40

# Standing start penalty (Lap 1 only)
LAP1_START_PENALTY = 3.0  # seconds (temporary global value)

# ----------------------------
# Circuit data
# ----------------------------

circuit = circuits[CIRCUIT]
total_laps = circuit["total_laps"]
base_lap_time = circuit["base_lap_time"]
pit_loss = circuit["pit_loss"]

# ----------------------------
# Tyre model
# ----------------------------

def tyre_delta(tyre_name, life):
    tyre = tyres[tyre_name]

    warmup_laps = tyre["warmup_laps"]
    warmup_penalty = tyre["warmup_start_penalty"]
    peak_life = tyre["peak_life"]
    deg_linear = tyre["deg_linear"]
    deg_quadratic = tyre["deg_quadratic"]

    # ----------------------------
    # Warm-up phase
    # ----------------------------
    if life < warmup_laps:
        # Linear warm-up improvement
        progress = life / warmup_laps
        return warmup_penalty * (1 - progress)

    # ----------------------------
    # Peak window
    # ----------------------------
    if life <= peak_life:
        return 0.0

    # ----------------------------
    # Degradation phase
    # ----------------------------
    deg_life = life - peak_life
    return (
        deg_linear * deg_life +
        deg_quadratic * (deg_life ** 2)
    )

# ----------------------------
# Simulation
# ----------------------------

total_time = 0.0
tyre = START_TYRE
tyre_life = 0

print(f"\nSimulating {CIRCUIT}")
print("Formation lap complete (not timed)")
print(f"Strategy: {START_TYRE} → {END_TYRE} on lap {PIT_LAP}\n")

for lap in range(1, total_laps + 1):

    # Pit stop
    if lap == PIT_LAP:
        total_time += pit_loss
        tyre = END_TYRE
        tyre_life = 0
        print(f"Lap {lap:02d}: PIT STOP (+{pit_loss:.2f}s)")

    delta = tyre_delta(tyre, tyre_life)
    lap_time = base_lap_time + delta

    # Lap 1 standing start penalty
    if lap == 1:
        lap_time += LAP1_START_PENALTY

    total_time += lap_time

    print(
        f"Lap {lap:02d} | Tyre: {tyre:>3} | "
        f"Life: {tyre_life:02d} | "
        f"Lap time: {lap_time:.2f}s | "
        f"Total: {total_time:.2f}s"
    )

    tyre_life += 1

# ----------------------------
# Result
# ----------------------------

print("\nFinal total race time:")
print(f"{total_time:.2f}s")