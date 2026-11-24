import math
import sys

import chess

DEPTH = 3

# A mate is worth more than any material advantage you could ever have.
MATE_SCORE = 100_000

NODES = 0  # how many positions the last search looked at


PIECE_TYPE_COST = {
    chess.KING: 0,  # both kings are always on the board, so they always cancel out
    chess.QUEEN: 900,
    chess.ROOK: 500,
    chess.BISHOP: 300,
    chess.KNIGHT: 300,
    chess.PAWN: 100,
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
            move = choose_move(board)
            print(f"bestmove {move.uci()}")
        elif command == "quit":
            break

        sys.stdout.flush()


def choose_move(board: chess.Board) -> chess.Move:
    global NODES
    NODES = 0

    best_move = None
    best_score = -math.inf

    # `alpha` is the best score we have already secured. Every move we try after
    # this one only has to be compared against it.
    alpha = -math.inf

    for move in order_moves(board, list(board.legal_moves)):
        board.push(move)
        score = -alphabeta(board, DEPTH - 1, -math.inf, -alpha)
        board.pop()

        if score > best_score:
            best_score = score
            best_move = move
            alpha = score

    if best_move is None:
        raise ValueError("choose_move is called on board without legal moves")

    print(f"info depth {DEPTH} nodes {NODES} score cp {int(best_score)} pv {best_move.uci()}")

    return best_move


def alphabeta(board: chess.Board, depth: int, alpha: float, beta: float) -> float:
    """Negamax, but stop searching a node once it cannot affect the result.

    `alpha` is the best score we have already secured somewhere else in the tree,
    `beta` is the best the opponent has already secured. If we find a move worth
    `beta` or more, the opponent will never let us get here, they had a better
    option earlier, so the exact value no longer matters and we can stop.
    """
    global NODES
    NODES += 1

    outcome = board.outcome()
    if outcome is not None:
        return 0 if outcome.winner is None else -MATE_SCORE

    if depth == 0:
        return evaluate_relative(board)

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


def evaluate(board: chess.Board) -> int:
    """Material balance, always from white's point of view.

    Positive means white is ahead, negative means black is ahead.
    """
    white_score = 0
    black_score = 0

    for square in chess.SQUARES:
        if piece := board.piece_at(square):
            if piece.color == chess.WHITE:
                white_score += PIECE_TYPE_COST[piece.piece_type]
            else:
                black_score += PIECE_TYPE_COST[piece.piece_type]

    return white_score - black_score


def evaluate_relative(board: chess.Board) -> int:
    """The same score, from the point of view of whoever is to move."""
    return evaluate(board) if board.turn == chess.WHITE else -evaluate(board)


def parse_position(command: str) -> chess.Board:
    """Build a board from a UCI ``position`` command.

    Handles the two forms the protocol allows:

        position startpos
        position startpos moves e2e4 e7e5
    """
    tokens = command.split()

    if tokens[1] == "startpos":
        board = chess.Board()
        moves_index = 2
    else:
        raise ValueError("Only `startpos` implemented")

    if len(tokens) > moves_index and tokens[moves_index] == "moves":
        for uci in tokens[moves_index + 1 :]:
            board.push_uci(uci)

    return board


if __name__ == "__main__":
    uci()
