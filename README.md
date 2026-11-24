# Python Chess Starter

A minimal [UCI](https://en.wikipedia.org/wiki/Universal_Chess_Interface) chess
engine you can fork to build your own [machineplay](https://machineplay.org)
bot. Out of the box it plays the first legal move — your job is to make it play
better.

**New to chess engines?** The [engine tutorial](https://machineplay.org/docs/engine-tutorial)
starts from this repo and builds it up to an alpha-beta searcher, one working
engine per chapter. Every chapter's finished engine is in [`solutions/`](solutions).

## What's here

- `main.py` — the whole engine: a small UCI loop plus a `choose_move` function.
- `solutions/` — the finished engine from each chapter of the tutorial.
- `openings.epd` — opening positions for local matches with fastchess.
- `pyproject.toml` — dependencies (just [python-chess](https://python-chess.readthedocs.io)),
  managed with [uv](https://docs.astral.sh/uv/).

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv sync
uv run python main.py
```

The engine now waits for UCI commands on stdin. Try a quick conversation
(type the lines without the `>`):

```
> uci
id name python-chess-starter
id author your-name-here
uciok
> position startpos
> go
bestmove g1h3
```

`g1h3` is the first legal move from the starting position. Type `quit` to exit.

## Make it your own

All of the chess "thinking" lives in one function in `main.py`:

```python
def choose_move(board: chess.Board) -> chess.Move:
    return next(iter(board.legal_moves))
```

`board` is a [`chess.Board`](https://python-chess.readthedocs.io/en/latest/core.html#board).
Return any legal `chess.Move` and the engine plays it. Some ideas, roughly in
order of difficulty:

1. **Random mover** — `random.choice(list(board.legal_moves))`.
2. **Greedy** — prefer captures, or the move that wins the most material.
3. **Minimax** — search a few moves ahead with a simple evaluation function.

The [tutorial](https://machineplay.org/docs/engine-tutorial) walks through all
three and well past them.

## Packaging with Docker

machineplay runs your engine as a Docker image, talking UCI over stdin/stdout.
The included `Dockerfile` builds one for you:

```sh
docker build -t my-engine .
```

Test it exactly the way machineplay will — pipe UCI commands into an
interactive container:

```sh
printf 'uci\nposition startpos\ngo\nquit\n' | docker run --rm -i my-engine
```

You should see `bestmove g1h3`.

## Uploading to machineplay

```sh
uv tool install machineplay
machineplay login      # opens machineplay.org/cli, paste the token back
machineplay upload     # builds this Dockerfile, checks it speaks UCI, pushes it
```

`upload` asks for an engine name and a version: keep the name, change the
version each time. Your engine then lives at `machineplay.org/<you>/<engine>`.
