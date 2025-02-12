import asyncio
import hyperdiv as hd
import random
import time

ROWS = 30
COLS = 50
DELAY_TIME = 0.25  # Delay between generations in seconds


@hd.global_state
class MyState(hd.BaseState):
    did_setup = hd.Prop(hd.Bool, False)  # Whether the grid data has been initialized
    stopped = hd.Prop(hd.Bool, False)  # Whether the auto task has been stopped
    generation = hd.Prop(hd.Int, 0)  # Track the generation number
    checkboxes = hd.Prop(hd.Any, dict())  # Store the checkbox data


def initialize_grid_data(rows: int, cols: int):
    """Initialize the checkbox data once and store it in the global state."""
    state = MyState()
    if state.did_setup:
        return

    state.checkboxes = {}
    for row in range(rows):
        for col in range(cols):
            key = f"checkbox_{row}_{col}"
            start_checked = random.random() < 0.4  # % chance of being checked
            state.checkboxes[key] = {"checked": start_checked}
    state.did_setup = True


def render_grid():
    """Render the grid from the data stored in global state."""
    state = MyState()

    # The UI components are generated from the persisted data.
    with hd.table():
        with hd.tbody():
            for row in range(ROWS):
                with hd.scope(row):
                    with hd.tr():
                        for col in range(COLS):
                            with hd.scope(col):
                                key = f"checkbox_{row}_{col}"
                                # Render a checkbox with its current state.
                                checkbox = hd.checkbox(
                                    name=f"cell_{row}_{col}",
                                    checked=state.checkboxes[key]["checked"],
                                )
                                # Update in state if checkbox is clicked
                                if checkbox.changed:
                                    print("Checkbox changed")
                                    # checkboxes[key]["checked"] = checkbox.checked
                                    state.checkboxes[key]["checked"] = (
                                        not state.checkboxes[key]["checked"]
                                    )
                                    # Mark the cell as manually updated
                                    state.checkboxes[key]["locked"] = True
                                    # Update the generation to trigger a re-render
                                    state.generation += 1


def parse_coordinates(key: str):
    """
    Given a key like 'checkbox_3_5', return (3,5).
    """
    # Last two parts after splitting by underscore are row and col
    parts = key.split("_")
    row = int(parts[1])
    col = int(parts[2])
    return row, col


def get_neighbors(r, c, max_r, max_c):
    """
    Return a list of valid neighbor coordinates for cell (r, c).
    """
    neighbors = []
    for nr in range(r - 1, r + 2):
        for nc in range(c - 1, c + 2):
            # Exclude the cell itself and out-of-bounds
            if (nr, nc) != (r, c) and 0 <= nr < max_r and 0 <= nc < max_c:
                neighbors.append((nr, nc))
    return neighbors


def next_generation():
    """
    Compute the next generation based on Conway's Game of Life rules:
      1. Any live cell with 2 or 3 live neighbors survives.
      2. Any dead cell with exactly 3 live neighbors becomes a live cell.
      3. All other live cells die, and all other dead cells stay dead.
    """
    print("Computing next generation...")
    state = MyState()

    current_state = {}
    for key, checkbox in state.checkboxes.items():
        # Parse the key to get row and col
        parts = key.split("_")
        row, col = int(parts[1]), int(parts[2])
        current_state[(row, col)] = checkbox["checked"]

    new_state = {}
    for (row, col), alive in current_state.items():
        # Calculate neighbors
        neighbors = [
            (nr, nc)
            for nr in range(row - 1, row + 2)
            for nc in range(col - 1, col + 2)
            if (nr, nc) != (row, col) and 0 <= nr < ROWS and 0 <= nc < COLS
        ]
        live_neighbors = sum(current_state[(nr, nc)] for (nr, nc) in neighbors)
        if alive:
            new_state[(row, col)] = live_neighbors in [2, 3]
        else:
            new_state[(row, col)] = live_neighbors == 3

    # Update the checkbox states for cells that are not locked.
    for (row, col), alive in new_state.items():
        key = f"checkbox_{row}_{col}"
        # Only update if the cell wasn't manually toggled
        if not state.checkboxes[key].get("locked", False):
            state.checkboxes[key]["checked"] = alive

    # Unlock all cells that are currently locked.
    # (Changing the default to False ensures we only unlock cells that were explicitly locked.)
    for key in state.checkboxes.keys():
        if state.checkboxes[key].get("locked", False):
            state.checkboxes[key]["locked"] = False

    return True


async def next_generation_loop():
    state = MyState()

    while True:
        if state.stopped:
            break
        print("LOOP")
        next_generation()
        state.generation += 1
        await asyncio.sleep(DELAY_TIME)


def main():
    # Initialize grid data once at startup.
    state = MyState()

    if not state.checkboxes:
        initialize_grid_data(ROWS, COLS)

    task = hd.task()
    auto_task = hd.task()

    hd.markdown("## Conway's Game of Life")
    hd.markdown(f"Generation: `{state.generation}`")  # Shows current generation
    render_grid()

    # Update the global state when checkboxes are clicked
    # for key in checkboxes.keys():
    #     print(key)
    # with hd.scope(key):
    #     if hd.checkbox(name=key).changed:
    #         checkboxes[key]["checked"] = hd.checkbox(name=key).checked

    hd.divider(spacing=2, thickness=0)
    with hd.hbox(gap=1):
        next_button = hd.button("Next Generation", disabled=task.running)
        hd.divider(vertical=True, spacing=1)
        auto_button = hd.button("Auto", disabled=auto_task.running)
        stop_button = hd.button("Stop", disabled=not auto_task.running)
        hd.divider(vertical=True, spacing=1)
        reset_button = hd.button("Reset")

        if next_button.clicked:
            task.rerun(next_generation)
        if auto_button.clicked:
            state.stopped = False
            auto_task.rerun(next_generation_loop)
        if stop_button.clicked:
            state.stopped = True
        if reset_button.clicked:
            state.checkboxes = {}
            state.did_setup = False
            state.stopped = True
            state.generation = 0
            loc = hd.location()
            loc.path = "/"

        if auto_task.running:
            hd.markdown("Running...")
        if auto_task.done:
            hd.markdown("Done")


if __name__ == "__main__":
    hd.run(main)
