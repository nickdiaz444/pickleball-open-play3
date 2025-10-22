import streamlit as st
import json
from pathlib import Path
import random

# ────────────────────────────── FILES ──────────────────────────────
DATA_FILE = Path("pickleball_data.json")
CONFIG_FILE = Path("pickleball_config.json")

# ────────────────────────────── DEFAULTS ──────────────────────────────
DEFAULT_MAX_PLAYERS = 20
DEFAULT_NUM_COURTS = 3

# ────────────────────────────── HELPERS ──────────────────────────────
def load_json(path, default):
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def rerun_app():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ────────────────────────────── LOAD CONFIG & DATA ──────────────────────────────
config = load_json(CONFIG_FILE, {"max_players": DEFAULT_MAX_PLAYERS, "num_courts": DEFAULT_NUM_COURTS})
data = load_json(DATA_FILE, {
    "players": [],
    "queue": [],
    "courts": [[] for _ in range(config["num_courts"])],
    "streaks": {},
    "history": []
})

# ────────────────────────────── LOGIC ──────────────────────────────
def initialize_queue():
    if not data["players"]:
        st.warning("Add players first.")
        return
    data["queue"] = data["players"][:]
    random.shuffle(data["queue"])
    save_json(DATA_FILE, data)
    rerun_app()

def assign_all_courts():
    for i in range(config["num_courts"]):
        if len(data["queue"]) < 4:
            break
        data["courts"][i] = [data["queue"].pop(0) for _ in range(4)]
        for p in data["courts"][i]:
            data["streaks"][p] = 1
    save_json(DATA_FILE, data)
    rerun_app()

def process_court_result(court_index, winning_team, rerun=True):
    court = data["courts"][court_index]
    if len(court) < 4:
        st.warning("Not enough players on this court.")
        return

    winners = court[:2] if winning_team == "Team 1" else court[2:]
    losers = court[2:] if winning_team == "Team 1" else court[:2]

    # Update streaks
    for w in winners:
        data["streaks"][w] = data["streaks"].get(w, 0) + 1
    for l in losers:
        data["streaks"][l] = 0

    # Winners stay on (split), max 2 games
    staying = []
    for w in winners:
        if data["streaks"][w] < 3:
            staying.append(w)
        else:
            data["streaks"][w] = 0
            data["queue"].append(w)

    # Build new court: split winners into opposing teams
    new_court = []
    if len(staying) == 2:
        # First winner Team 1, second winner Team 2
        team1_partner = data["queue"].pop(0) if data["queue"] else staying[0]
        team2_partner = data["queue"].pop(0) if data["queue"] else staying[1]
        new_court = [staying[0], team1_partner, team2_partner, staying[1]]
    else:
        # Fill from queue if fewer than 2 winners
        new_court = staying[:]
        while len(new_court) < 4 and data["queue"]:
            new_court.append(data["queue"].pop(0))

    # Add losing players back to queue if not already on court
    for l in losers:
        if l not in new_court:
            data["queue"].append(l)

    data["courts"][court_index] = new_court
    data["history"].append({
        "court": court_index + 1,
        "winners": winners,
        "losers": losers
    })
    save_json(DATA_FILE, data)
    
    if rerun:
        rerun_app()

def reset_all_data():
    if DATA_FILE.exists():
        DATA_FILE.unlink()
    st.session_state.clear()
    rerun_app()

def reset_streaks():
    for p in data["streaks"]:
        data["streaks"][p] = 0
    save_json(DATA_FILE, data)
    st.success("All player streaks have been reset to 0.")
    rerun_app()

# ────────────────────────────── UI ──────────────────────────────
st.set_page_config(page_title="🏓 Pickleball Open Play Scheduler", layout="wide")
st.title("🏓 Pickleball Open Play Scheduler")

# ────────────────────────────── SIDEBAR CONFIG ──────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    # Session settings
    st.write("### Session Settings")
    max_players = st.slider("Max Players", 8, 30, config["max_players"], 1)
    num_courts = st.slider("Number of Courts", 1, 5, config["num_courts"], 1)
    if st.button("💾 Save Config"):
        config["max_players"] = max_players
        config["num_courts"] = num_courts
        save_json(CONFIG_FILE, config)
        data["courts"] = [[] for _ in range(config["num_courts"])]
        save_json(DATA_FILE, data)
        rerun_app()

    st.divider()

    # Add multiple players
    st.write("### Add Players (one per line)")
    new_players_text = st.text_area("Enter player names:", height=150)
    if st.button("Add / Update Players"):
        new_players = [p.strip() for p in new_players_text.splitlines() if p.strip()]
        for p in new_players:
            if p not in data["players"]:
                data["players"].append(p)
                data["queue"].append(p)
                data["streaks"][p] = 0
        save_json(DATA_FILE, data)
        rerun_app()

    st.write("### Active Players")
    active_cols = st.columns(2)
    for i, p in enumerate(data["players"]):
        col = active_cols[i % 2]
        active = col.checkbox(f"{p}", value=(p in data["queue"]))
        if active and p not in data["queue"]:
            data["queue"].append(p)
        elif not active and p in data["queue"]:
            data["queue"].remove(p)
    save_json(DATA_FILE, data)

    st.divider()
    if st.button("Initialize Queue"):
        initialize_queue()
    if st.button("Assign all courts"):
        assign_all_courts()
    if st.button("Reset everything"):
        reset_all_data()
    if st.button("🔄 Reset All Player Streaks"):
        reset_streaks()

# ────────────────────────────── DISPLAY QUEUE ──────────────────────────────
st.subheader("🎯 Player Queue")
if data["queue"]:
    st.write(", ".join(data["queue"]))
else:
    st.write("Queue is empty — add players or initialize.")

# ────────────────────────────── DISPLAY COURTS ──────────────────────────────
st.subheader("🏟️ Courts")
cols = st.columns(config["num_courts"])

for i, col in enumerate(cols):
    with col:
        st.markdown(f"### Court {i+1}")
        court = data["courts"][i]
        
        if not court or len(court) < 4:
            st.info("No game assigned or incomplete court.")
        else:
            # Display teams
            st.write(f"**Team 1:** {court[0]} & {court[1]}")
            st.write(f"**Team 2:** {court[2]} & {court[3]}")

            # Persist winner selection
            key_name = f"winner_{i}"
            if key_name not in st.session_state:
                st.session_state[key_name] = "None"

            st.session_state[key_name] = st.radio(
                f"Select winner for Court {i+1}",
                ["None", "Team 1", "Team 2"],
                index=["None", "Team 1", "Team 2"].index(st.session_state[key_name]),
                key=f"radio_{i}"
            )

            # Individual court submit button
            if st.button(f"Submit result for Court {i+1}", key=f"submit_{i}"):
                if st.session_state[key_name] != "None":
                    process_court_result(i, st.session_state[key_name])
                    st.session_state[key_name] = "None"
                    st.success(f"Court {i+1} result processed!")

# -------------------------
# Submit All Winners Button
# -------------------------
if st.button("Submit All Court Winners"):
    any_selected = False
    for i in range(config["num_courts"]):
        key_name = f"winner_{i}"
        winner = st.session_state.get(key_name, "None")
        if winner in ["Team 1", "Team 2"]:
            process_court_result(i, winner, rerun=False)
            st.session_state[key_name] = "None"
            any_selected = True
    if any_selected:
        save_json(DATA_FILE, data)
        rerun_app()  # Single rerun at the end
        st.success("All selected court results processed!")
    else:
        st.warning("No winners selected for any courts.")

# ────────────────────────────── MATCH HISTORY ──────────────────────────────
st.subheader("📜 Match History")
if data["history"]:
    for match in reversed(data["history"][-10:]):
        st.write(
            f"**Court {match['court']}** — Winners: {', '.join(match['winners'])} | "
            f"Losers: {', '.join(match['losers'])}"
        )
else:
    st.write("No matches played yet.")
