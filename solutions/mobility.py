import math
import sys
import time

import chess

MAX_DEPTH = 64  # we stop here even if there is still time left
DEFAULT_BUDGET = 3.0  # seconds to think when `go` arrives without a clock
SAFETY = 0.95  # never use quite all of the time we are given

# Flat allowance for everything outside the search: process startup, writing
# the move out, the GUI reading it. Losing on time by 30ms still loses.
MOVE_OVERHEAD = 0.05

# Nodes between two reads of the clock. Bigger is cheaper but overshoots the
# budget by more: python searches on the order of 10k nodes a second, so 64
# nodes is a handful of milliseconds of slack.
CLOCK_CHECK_INTERVAL = 64

# A mate is worth more than any material advantage you could ever have.
MATE_SCORE = 100_000

MOBILITY_WEIGHT = 3  # centipawns per extra legal move

# Below this much non-pawn material on the board, the king stops hiding and
# starts helping.
ENDGAME_MATERIAL = 2600

NODES = 0  # how many positions the last search looked at
DEADLINE = math.inf  # time.monotonic() value at which we must stop


class TimeUp(Exception):
    """Raised deep inside the search when the clock runs out."""


PIECE_TYPE_COST = {
    chess.KING: 0,  # both kings are always on the board, so they always cancel out
    chess.QUEEN: 900,
    chess.ROOK: 500,
    chess.BISHOP: 300,
    chess.KNIGHT: 300,
    chess.PAWN: 100,
}


def _table(rows: str) -> list[int]:
    """Read a table written rank 8 first, as an a1-indexed list of 64."""
    values = [int(v) for v in rows.split()]
    assert len(values) == 64, len(values)
    return [
        values[(7 - chess.square_rank(sq)) * 8 + chess.square_file(sq)]
        for sq in chess.SQUARES
    ]


# Where each piece would rather stand, in centipawns, from white's side.
PAWN_PST = _table("""
  0   0   0   0   0   0   0   0
 50  50  50  50  50  50  50  50
 10  10  20  30  30  20  10  10
  5   5  10  25  25  10   5   5
  0   0   0  20  20   0   0   0
  5  -5 -10   0   0 -10  -5   5
  5  10  10 -20 -20  10  10   5
  0   0   0   0   0   0   0   0
""")

KNIGHT_PST = _table("""
-50 -40 -30 -30 -30 -30 -40 -50
-40 -20   0   0   0   0 -20 -40
-30   0  10  15  15  10   0 -30
-30   5  15  20  20  15   5 -30
-30   0  15  20  20  15   0 -30
-30   5  10  15  15  10   5 -30
-40 -20   0   5   5   0 -20 -40
-50 -40 -30 -30 -30 -30 -40 -50
""")

BISHOP_PST = _table("""
-20 -10 -10 -10 -10 -10 -10 -20
-10   0   0   0   0   0   0 -10
-10   0   5  10  10   5   0 -10
-10   5   5  10  10   5   5 -10
-10   0  10  10  10  10   0 -10
-10  10  10  10  10  10  10 -10
-10   5   0   0   0   0   5 -10
-20 -10 -10 -10 -10 -10 -10 -20
""")

ROOK_PST = _table("""
  0   0   0   0   0   0   0   0
  5  10  10  10  10  10  10   5
 -5   0   0   0   0   0   0  -5
 -5   0   0   0   0   0   0  -5
 -5   0   0   0   0   0   0  -5
 -5   0   0   0   0   0   0  -5
 -5   0   0   0   0   0   0  -5
  0   0   0   5   5   0   0   0
""")

QUEEN_PST = _table("""
-20 -10 -10  -5  -5 -10 -10 -20
-10   0   0   0   0   0   0 -10
-10   0   5   5   5   5   0 -10
 -5   0   5   5   5   5   0  -5
  0   0   5   5   5   5   0  -5
-10   5   5   5   5   5   0 -10
-10   0   5   0   0   0   0 -10
-20 -10 -10  -5  -5 -10 -10 -20
""")

KING_MIDDLEGAME_PST = _table("""
-30 -40 -40 -50 -50 -40 -40 -30
-30 -40 -40 -50 -50 -40 -40 -30
-30 -40 -40 -50 -50 -40 -40 -30
-30 -40 -40 -50 -50 -40 -40 -30
-20 -30 -30 -40 -40 -30 -30 -20
-10 -20 -20 -20 -20 -20 -20 -10
 20  20   0   0   0   0  20  20
 20  30  10   0   0  10  30  20
""")

KING_ENDGAME_PST = _table("""
-50 -40 -30 -20 -20 -30 -40 -50
-30 -20 -10   0   0 -10 -20 -30
-30 -10  20  30  30  20 -10 -30
-30 -10  30  40  40  30 -10 -30
-30 -10  30  40  40  30 -10 -30
-30 -10  20  30  30  20 -10 -30
-30 -30   0   0   0   0 -30 -30
-50 -30 -30 -30 -30 -30 -30 -50
""")

PST_BY_PIECE_TYPE = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
}


def uci() -> None:
    board = chess.Board()

    while True:
        line = sys.stdin.readline()
        if not line:  # stdin closed
            break
        command = line.strip()

        if command == "uci":
            print("id name python-chess-starter")
            print("id author your-name-here")
            print("uciok")
        elif command == "isready":
            print("readyok")
        elif command == "ucinewgame":
            board.reset()
        elif command.startswith("position"):
            board = parse_position(command)
        elif command.startswith("go"):
            budget, max_depth = parse_go(command, board)
            move = choose_move(board, budget, max_depth)
            print(f"bestmove {move.uci()}")
        elif command == "quit":
            break

        sys.stdout.flush()


def parse_go(command: str, board: chess.Board) -> tuple[float, int]:
    """Work out how long we may think for, and how deep we may go.

    Understands the forms a GUI actually sends:

        go
        go depth 4
        go movetime 1000
        go wtime 300000 btime 300000 winc 2000 binc 2000

    Anything else (`go infinite`, `go ponder`) falls through to the default
    budget, because we have no `stop` command to end it with.
    """
    tokens = command.split()

    def value(name: str, default: int = 0) -> int:
        if name in tokens:
            return int(tokens[tokens.index(name) + 1])
        return default

    if "depth" in tokens:
        return math.inf, value("depth")

    if "movetime" in tokens:
        return budget_for(value("movetime")), MAX_DEPTH

    # The clock is given for both players; only ours matters.
    if board.turn == chess.WHITE:
        remaining, increment = value("wtime"), value("winc")
    else:
        remaining, increment = value("btime"), value("binc")

    if remaining == 0:  # a bare `go`, with no clock at all
        return DEFAULT_BUDGET, MAX_DEPTH

    # Assume the game still has about 20 moves to go, and that we get the
    # increment back after this move. Never bet more than we actually have.
    return budget_for(remaining / 20 + increment * 0.8, remaining), MAX_DEPTH


def budget_for(want: float, remaining: float | None = None) -> float:
    """Turn a wanted number of milliseconds into seconds we can safely use."""
    if remaining is not None:
        want = min(want, remaining * SAFETY)
    return max(0.01, want / 1000 - MOVE_OVERHEAD)


def choose_move(board: chess.Board, budget: float, max_depth: int) -> chess.Move:
    """Search depth 1, then 2, then 3... until the clock runs out.

    Throwing away each finished search and starting over is not free: the extra
    work is exactly the cost of every earlier depth added together, which
    measures at roughly 10% on top of going straight to depth 5 (and less the
    deeper you go, since each depth dwarfs the one before it).

    What that 10% buys is the ability to stop at any moment and still have a
    complete answer. A fixed-depth search gives you nothing at all if the clock
    runs out halfway, and you cannot know in advance which depth fits the time
    you were given, it depends on the position.
    """
    global NODES, DEADLINE

    NODES = 0
    start = time.monotonic()
    DEADLINE = start + budget

    # An abandoned search leaves half-played moves behind, so work on a copy
    # and leave the caller's board alone.
    board = board.copy()

    moves = order_moves(board, list(board.legal_moves))
    if not moves:
        raise ValueError("choose_move is called on board without legal moves")

    best_move = moves[0]  # so we always have something legal to play

    for depth in range(1, max_depth + 1):
        try:
            move, score = search_root(board, depth, moves)
        except TimeUp:
            break  # this depth never finished, so keep the last complete answer

        best_move = move

        # Try the winner first next time round. Here it is nearly free and
        # nearly pointless, captures-first ordering usually found that move
        # already, but it is the seed of the real technique: once every node
        # remembers its best move, and not just the root, this is what makes
        # deep searches affordable.
        moves.remove(move)
        moves.insert(0, move)

        elapsed = time.monotonic() - start
        print(
            f"info depth {depth} nodes {NODES} time {int(elapsed * 1000)} "
            f"score cp {int(score)} pv {move.uci()}"
        )

        if abs(score) >= MATE_SCORE - max_depth:
            break  # a forced mate; nothing deeper left to learn

        # The next depth costs several times this one, so do not even start it
        # unless a good chunk of the budget is still unspent.
        if elapsed > budget * 0.5:
            break

    return best_move


def search_root(
    board: chess.Board, depth: int, moves: list[chess.Move]
) -> tuple[chess.Move, float]:
    """One complete iteration: the best move at exactly `depth`."""
    best_move = moves[0]
    best_score = -math.inf
    alpha = -math.inf

    for move in moves:
        board.push(move)
        score = -alphabeta(board, depth - 1, -math.inf, -alpha)
        board.pop()

        if score > best_score:
            best_score = score
            best_move = move
            alpha = score

    return best_move, best_score


def alphabeta(board: chess.Board, depth: int, alpha: float, beta: float) -> float:
    """Negamax, but stop searching a node once it cannot affect the result.

    `alpha` is the best score we have already secured somewhere else in the tree,
    `beta` is the best the opponent has already secured. If we find a move worth
    `beta` or more, the opponent will never let us get here, they had a better
    option earlier, so the exact value no longer matters and we can stop.
    """
    global NODES
    NODES += 1

    # Reading the clock is not free, so only do it every so often.
    if NODES % CLOCK_CHECK_INTERVAL == 0 and time.monotonic() > DEADLINE:
        raise TimeUp

    outcome = board.outcome()
    if outcome is not None:
        return 0 if outcome.winner is None else -MATE_SCORE

    if depth == 0:
        return quiescence(board, alpha, beta)

    best = -math.inf
    for move in order_moves(board, list(board.legal_moves)):
        board.push(move)
        # The window belongs to the side to move too, so it flips and swaps
        # exactly like the score does.
        score = -alphabeta(board, depth - 1, -beta, -alpha)
        board.pop()

        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break  # cutoff: the opponent would never allow this position

    return best


def quiescence(board: chess.Board, alpha: float, beta: float) -> float:
    """Search captures only until the position goes quiet, then evaluate.

    `evaluate` is only honest about quiet positions: in the middle of an
    exchange it counts pieces that are about to disappear. So where the search
    used to evaluate at depth 0, it now keeps playing captures, and only
    captures, until the fight burns itself out.
    """
    global NODES
    NODES += 1

    if NODES % CLOCK_CHECK_INTERVAL == 0 and time.monotonic() > DEADLINE:
        raise TimeUp

    outcome = board.outcome()
    if outcome is not None:
        return 0 if outcome.winner is None else -MATE_SCORE

    # Standing pat: the side to move is never forced to keep capturing, so the
    # position as it stands is a floor on its score.
    best: float = evaluate_relative(board)
    if best > alpha:
        alpha = best
    if alpha >= beta:
        return best

    for move in order_moves(board, list(board.generate_legal_captures())):
        board.push(move)
        score = -quiescence(board, -beta, -alpha)
        board.pop()

        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break  # cutoff: the opponent would never allow this position

    return best


def order_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    """Try captures first, grabbing the biggest piece with the smallest one.

    Cutoffs only happen once a good move has been found, so the sooner we find
    it the more of the tree we get to skip. This never changes which move the
    search picks, only how long it takes to get there.
    """

    def score(move: chess.Move) -> int:
        victim = board.piece_type_at(move.to_square)
        if victim is None:
            return 0
        attacker = board.piece_type_at(move.from_square)
        assert attacker is not None
        return 10 * PIECE_TYPE_COST[victim] - PIECE_TYPE_COST[attacker]

    return sorted(moves, key=score, reverse=True)


def is_endgame(board: chess.Board) -> bool:
    """True once there is little enough left that the king should walk out."""
    heavy = sum(
        PIECE_TYPE_COST[piece.piece_type]
        for piece in board.piece_map().values()
        if piece.piece_type not in (chess.KING, chess.PAWN)
    )
    return heavy <= ENDGAME_MATERIAL


def mobility(board: chess.Board) -> int:
    """Legal moves for white minus legal moves for black.

    A null move (passing the turn) is how you ask python-chess for the other
    side's moves without playing anything. It is illegal while in check, so
    skip it there; the search is about to look at that check anyway.
    """
    if board.is_check():
        return 0

    ours = board.legal_moves.count()
    board.push(chess.Move.null())
    theirs = board.legal_moves.count()
    board.pop()

    return ours - theirs if board.turn == chess.WHITE else theirs - ours


def evaluate(board: chess.Board) -> int:
    """Material, plus where the pieces stand, plus how much they can do.

    Positive means white is ahead, negative means black is ahead.
    """
    endgame = is_endgame(board)
    score = 0

    for square, piece in board.piece_map().items():
        # The tables are written from white's side, so black reads them upside
        # down: what is a8 for white is a1 for black.
        seen_from = square if piece.color == chess.WHITE else chess.square_mirror(square)

        if piece.piece_type == chess.KING:
            place = (KING_ENDGAME_PST if endgame else KING_MIDDLEGAME_PST)[seen_from]
        else:
            place = PST_BY_PIECE_TYPE[piece.piece_type][seen_from]

        value = PIECE_TYPE_COST[piece.piece_type] + place
        score += value if piece.color == chess.WHITE else -value

    return score + MOBILITY_WEIGHT * mobility(board)


def evaluate_relative(board: chess.Board) -> int:
    """The same score, from the point of view of whoever is to move."""
    return evaluate(board) if board.turn == chess.WHITE else -evaluate(board)


def parse_position(command: str) -> chess.Board:
    """Build a board from a UCI ``position`` command.

    Handles the two forms the protocol allows:

        position startpos moves e2e4 e7e5
        position fen r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 1
    """
    tokens = command.split()
    moves_index = tokens.index("moves") if "moves" in tokens else len(tokens)

    if tokens[1] == "startpos":
        board = chess.Board()
    else:  # everything between `fen` and `moves` is the position itself
        board = chess.Board(" ".join(tokens[2:moves_index]))

    for uci in tokens[moves_index + 1 :]:
        board.push_uci(uci)

    return board


if __name__ == "__main__":
    uci()
