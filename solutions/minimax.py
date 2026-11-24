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

    # Same two branches as the depth 1 chapter, only now each move is scored by
    # a search instead of a single call to evaluate().
    if board.turn == chess.WHITE:
        best_score = -math.inf
        for move in board.legal_moves:
            board.push(move)
            score = minimax(board, DEPTH - 1)
            board.pop()

            if score > best_score:
                best_score = score
                best_move = move
    else:
        best_score = math.inf
        for move in board.legal_moves:
            board.push(move)
            score = minimax(board, DEPTH - 1)
            board.pop()

            if score < best_score:
                best_score = score
                best_move = move

    if best_move is None:
        raise ValueError("choose_move is called on board without legal moves")

    # UCI wants the score from the point of view of the side to move.
    side = 1 if board.turn == chess.WHITE else -1
    print(f"info depth {DEPTH} nodes {NODES} score cp {int(side * best_score)} pv {best_move.uci()}")

    return best_move


def minimax(board: chess.Board, depth: int) -> float:
    """Score `board` from white's point of view, looking `depth` moves ahead."""
    global NODES
    NODES += 1

    # The game can end in the middle of the search, and `evaluate` would not
    # notice: a checkmate looks like an ordinary pile of pieces to it.
    outcome = board.outcome()
    if outcome is not None:
        if outcome.winner is None:
            return 0  # stalemate, dead position, repetition
        return MATE_SCORE if outcome.winner == chess.WHITE else -MATE_SCORE

    if depth == 0:
        return evaluate(board)

    if board.turn == chess.WHITE:
        best = -math.inf
        for move in board.legal_moves:
            board.push(move)
            best = max(best, minimax(board, depth - 1))
            board.pop()
    else:
        best = math.inf
        for move in board.legal_moves:
            board.push(move)
            best = min(best, minimax(board, depth - 1))
            board.pop()

    return best


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
