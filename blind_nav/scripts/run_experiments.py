import sys, os, argparse
sys.path.insert(0, os.path.dirname(__file__))
from experiments.benchmark import run
def main():
    ap = argparse.ArgumentParser("Blind Nav — Experiment Runner")
    ap.add_argument("--graph", default=None, help="Pre-downloaded graph .pkl")
    ap.add_argument("--trials", type=int, default=50)
    args = ap.parse_args()
    run(args.graph, args.trials)
if __name__ == "__main__":
    main()