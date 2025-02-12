import asyncio
import hyperdiv as hd
import random
import numpy as np
from rslog import rslog
from scipy.signal import convolve2d  # Make sure SciPy is installed.

ROWS = 20
COLS = 30
DELAY_TIME = 0.25  # Delay between generations in seconds
NEIGHBOR_OFFSETS = [
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
]


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

    # Use tuple keys: (row, col)
    state.checkboxes = {}
    for row in range(rows):
        for col in range(cols):
            key = (row, col)
            start_checked = random.random() < 0.5  # 50% chance of being checked
            state.checkboxes[key] = {"checked": start_checked}

    state.did_setup = True


def render_grid():
    state = MyState()

    with hd.table():
        with hd.tbody():
            for row in range(ROWS):
                with hd.scope(row):
                    with hd.tr():
                        for col in range(COLS):
                            with hd.scope(col):
                                key = (row, col)  # tuple key now
                                checkbox = hd.checkbox(
                                    name=f"cell_{row}_{col}",  # name can remain a string
                                    checked=state.checkboxes[key]["checked"],
                                )
                                if checkbox.changed:
                                    rslog("Checkbox changed")
                                    new_cell = {
                                        **state.checkboxes[key],
                                        "checked": checkbox.checked,
                                    }
                                    # Update state immutably:
                                    state.checkboxes = {
                                        **state.checkboxes,
                                        key: new_cell,
                                    }
                                    state.generation += 1


# Original next_generation function
def next_generation():
    """
    Compute the next generation based on Conway's Game of Life rules:
      1. Any live cell with 2 or 3 live neighbors survives.
      2. Any dead cell with exactly 3 live neighbors becomes a live cell.
      3. All other live cells die, and all other dead cells stay dead.
    """
    rslog("Computing next generation...")
    state = MyState()

    # Build a snapshot of the current state.
    current_state = {}
    for key, cell in state.checkboxes.items():
        # key is already a (row, col) tuple
        current_state[key] = cell["checked"]

    new_state = {}
    # Use tuple keys and precomputed neighbor offsets.
    for (row, col), alive in current_state.items():
        live_neighbors = 0
        for dr, dc in NEIGHBOR_OFFSETS:
            nr, nc = row + dr, col + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                # get() returns 0 (False) if key not found
                live_neighbors += current_state.get((nr, nc), 0)
        new_state[(row, col)] = (alive and live_neighbors in [2, 3]) or (
            not alive and live_neighbors == 3
        )

    # Build a new checkboxes dict immutably.
    new_checkboxes = {}
    for (row, col), alive in new_state.items():
        key = (row, col)
        cell = state.checkboxes[key]
        new_cell = {**cell, "checked": alive}
        new_checkboxes[key] = new_cell

    state.checkboxes = new_checkboxes
    return True


def next_generation_numpy():
    rslog("Computing next generation (numpy version)...")
    state = MyState()

    # 1. Convert the current state (a dict with tuple keys) to a NumPy array.
    #    We'll assume a grid shape of (ROWS, COLS).
    grid = np.zeros((ROWS, COLS), dtype=np.int32)
    for row in range(ROWS):
        for col in range(COLS):
            key = (row, col)
            # Convert the boolean to int (1 for True, 0 for False)
            grid[row, col] = 1 if state.checkboxes[key]["checked"] else 0

    # 2. Compute the number of live neighbors using convolution.
    #    The kernel below sums the 8 surrounding cells.
    kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=np.int32)

    neighbor_count = convolve2d(grid, kernel, mode="same", boundary="fill", fillvalue=0)

    # 3. Apply the Game of Life rules:
    #    - A live cell (1) survives if it has 2 or 3 live neighbors.
    #    - A dead cell (0) becomes live if it has exactly 3 live neighbors.
    new_grid = np.where(
        ((grid == 1) & ((neighbor_count == 2) | (neighbor_count == 3)))
        | ((grid == 0) & (neighbor_count == 3)),
        1,
        0,
    )

    # 4. Convert the new grid back to the dictionary format.
    new_checkboxes = {}
    for row in range(ROWS):
        for col in range(COLS):
            key = (row, col)
            cell = state.checkboxes[key]
            # Update the "checked" state based on new_grid (casting to bool)
            new_cell = {**cell, "checked": bool(new_grid[row, col])}
            new_checkboxes[key] = new_cell

    state.checkboxes = new_checkboxes
    return True


async def next_generation_loop():
    state = MyState()

    while True:
        if state.stopped:
            break
        # next_generation()
        next_generation_numpy()
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

    hd.divider(spacing=2, thickness=0)
    with hd.hbox(gap=1):
        next_button = hd.button("Next Generation", disabled=task.running)
        hd.divider(vertical=True, spacing=1)
        auto_button = hd.button("Auto", disabled=auto_task.running)
        stop_button = hd.button("Stop", disabled=not auto_task.running)
        hd.divider(vertical=True, spacing=1)
        reset_button = hd.button("Reset")

        if next_button.clicked:
            task.rerun(next_generation_numpy)
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
