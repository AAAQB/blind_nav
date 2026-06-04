import sys, os, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from backend.data.osm_loader import OSMLoader
from backend.config import AREA_CONFIGS
def download(area_id: str, cfg: dict, force: bool = False):
    print(f"\n{'='*50}")
    print(f"  {cfg['name']} ({area_id})  [{cfg['lat']}, {cfg['lon']}  ±{cfg['dist']}m]")
    print(f"{'='*50}")
    loader = OSMLoader()
    t0 = time.time()
    try:
        G = loader.load_area(cfg["lat"], cfg["lon"], cfg["dist"], force_reload=force)
        elapsed = time.time() - t0
        print(f"  ✓ {elapsed:.1f}s  —  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    except Exception as e:
        print(f"  ✗ {e}")
def main():
    ap = argparse.ArgumentParser(description="Download OSM data")
    ap.add_argument("--area", default="xmum", help="Area id or 'all'")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.area == "all":
        for aid, acfg in AREA_CONFIGS.items():
            download(aid, acfg, args.force)
    elif args.area in AREA_CONFIGS:
        download(args.area, AREA_CONFIGS[args.area], args.force)
    else:
        print(f"Unknown area. Available: {list(AREA_CONFIGS.keys())}")
if __name__ == "__main__":
    main()