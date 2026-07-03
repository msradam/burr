"""Generate a synthetic Burr app with a large graph and log it to ~/.burr for UI benchmarking.

Usage: python gen_large_app.py --nodes 150 --extra-edges 2
Creates project ui-perf-bench with app id bench-<nodes>n.
"""

import argparse

from burr.core import ApplicationBuilder, State, action, default, expr


@action(reads=["counter"], writes=["counter"])
def step(state: State) -> State:
    return state.update(counter=state["counter"] + 1)


def build(n_nodes: int, extra_edges: int):
    names = [f"step_{i:03d}" for i in range(n_nodes)]
    transitions = []
    for i in range(n_nodes - 1):
        transitions.append((names[i], names[i + 1], default))
    for i in range(n_nodes):
        for k in range(1, extra_edges + 1):
            j = (i * 7 + k * 13 + 3) % n_nodes
            if j != i and j != i + 1:
                transitions.append((names[i], names[j], expr("counter < 0")))
    return names, transitions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=int, default=150)
    parser.add_argument("--extra-edges", type=int, default=2)
    args = parser.parse_args()

    names, transitions = build(args.nodes, args.extra_edges)
    app = (
        ApplicationBuilder()
        .with_actions(**{name: step for name in names})
        .with_transitions(*transitions)
        .with_state(counter=0)
        .with_entrypoint(names[0])
        .with_identifiers(app_id=f"bench-{args.nodes}n")
        .with_tracker("local", project="ui-perf-bench")
        .build()
    )
    app.run(halt_after=[names[-1]])
    print(f"done: {args.nodes} nodes, {len(transitions)} edges, {args.nodes} steps logged")


if __name__ == "__main__":
    main()
